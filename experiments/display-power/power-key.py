#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""SM-G965N power key toggles panel power while background work stays awake.

Only the unique gpio-keys device with KEY_POWER is observed, without grabbing
input. Never suspends, shuts down, unlocks a session or changes lock policy.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import select
import socket
import stat
import struct
import time

EVENT=struct.Struct('@llHHi')

def load_wake_backend():
    if Path('/dev/uinput').exists():return
    root=Path('/usr/local/lib/g965n-display-power');module=root/'uinput.ko'
    for path in (module,root/'pins.json'):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_mode&0o077:
            raise RuntimeError('Private root-owned wake module and pins required')
    pins=json.loads((root/'pins.json').read_text())
    if pins!={'uinput.ko':hashlib.sha256(module.read_bytes()).hexdigest()}:
        raise RuntimeError('Wake module pin mismatch')
    if command(['modinfo','-F','vermagic',str(module)])!=os.uname().release+' SMP preempt mod_unload aarch64':
        raise RuntimeError('Wake module ABI mismatch')
    command(['insmod',str(module)])

class WakeInput:
    """A modifier-only local keyboard: no text, pointer, password or unlock."""
    def __init__(self):
        self.fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOFOLLOW)
        try:
            for kind in (0,1):fcntl.ioctl(self.fd,0x40045564,kind)  # UI_SET_EVBIT
            fcntl.ioctl(self.fd,0x40045565,42)  # KEY_LEFTSHIFT only
            setup=struct.pack('@HHHH80sI',6,1,0x9651,1,b'G965N panel wake',0)
            fcntl.ioctl(self.fd,0x405C5503,setup)  # UI_DEV_SETUP
            fcntl.ioctl(self.fd,0x5501)  # UI_DEV_CREATE
            command(['udevadm','settle','--timeout=3'])
            time.sleep(.3)
        except BaseException:
            os.close(self.fd);raise
    def emit(self):
        events=b''.join(EVENT.pack(0,0,*e) for e in ((1,42,1),(0,0,0),(1,42,0),(0,0,0)))
        if os.write(self.fd,events)!=len(events):raise RuntimeError('Incomplete wake input')
    def close(self):
        try:fcntl.ioctl(self.fd,0x5502)  # UI_DEV_DESTROY
        finally:os.close(self.fd)

def bitmap(text):
    value=0
    for word in text.split():value=(value<<64)|int(word,16)
    return value

def power_press(kind,code,value,last,now):
    return kind==1 and code==116 and value==1 and (last is None or now-last>=.75)

def target_mode(before):
    if before==0:return 3
    if before in (1,2,3):return 0
    raise RuntimeError('Unsupported display power mode')

def discover(root=Path('/sys/class/input')):
    found=[]
    for node in root.glob('event*'):
        if (node/'device/name').read_text().strip()!='gpio-keys':continue
        if bitmap((node/'device/capabilities/key').read_text())&(1<<116):found.append(node.name)
    if len(found)!=1:raise RuntimeError('Unique GPIO power key required')
    return Path('/dev/input')/found[0]

def command(args):
    return subprocess_run(args).stdout.strip()

def subprocess_run(args):
    import subprocess
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=5)

def session_prefix(user,uid):
    session=command(['loginctl','show-seat','seat0','--property=ActiveSession','--value'])
    values=command(['loginctl','show-session',session,'--property=User','--property=Name',
                    '--property=Type','--property=State','--property=Seat'])
    fields=dict(line.split('=',1) for line in values.splitlines() if '=' in line)
    if fields!={'User':str(uid),'Name':user,'Type':'wayland','State':'active','Seat':'seat0'}:
        raise RuntimeError('Expected active local Wayland session')
    prefix=['runuser','-u',user,'--','env',f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus',f'XDG_RUNTIME_DIR=/run/user/{uid}']
    action=command(prefix+['gsettings','get','org.gnome.settings-daemon.plugins.power','power-button-action'])
    if action!="'nothing'":raise RuntimeError('Preserve changed native power-button policy')
    return prefix

def get_mode(prefix):
    answer=command(prefix+['gdbus','call','--session','--dest','org.gnome.Mutter.DisplayConfig',
        '--object-path','/org/gnome/Mutter/DisplayConfig','--method','org.freedesktop.DBus.Properties.Get',
        'org.gnome.Mutter.DisplayConfig','PowerSaveMode'])
    match=re.search(r'<(?:(?:u?int32)\s+)?(-?\d+)>',answer)
    if not match:raise RuntimeError('Unknown display power reply')
    return int(match.group(1))

def panel_mode():
    panels=list(Path('/sys/class/drm').glob('card*-DSI-*'))
    if len(panels)!=1:return None
    value=(panels[0]/'dpms').read_text().strip()
    return {'On':0,'Off':3}.get(value)

def toggle(prefix,before=None,wake=None):
    # GNOME may wake the panel from the same key before this listener runs.
    # Use the pre-event state, never toggle that newly woken panel back off.
    target=target_mode(get_mode(prefix) if before is None else before)
    if target==0:
        # Genuine local input clears GNOME idle/blank state without test APIs.
        # A locked session remains locked; a modifier never enters a password.
        if wake is None:raise RuntimeError('Wake input required')
        wake.emit()
    else:
        command(prefix+['gdbus','call','--session','--dest','org.gnome.ScreenSaver',
            '--object-path','/org/gnome/ScreenSaver','--method','org.gnome.ScreenSaver.SetActive','true'])
    if target!=0:
        command(prefix+['gdbus','call','--session','--dest','org.gnome.Mutter.DisplayConfig',
            '--object-path','/org/gnome/Mutter/DisplayConfig','--method','org.freedesktop.DBus.Properties.Set',
            'org.gnome.Mutter.DisplayConfig','PowerSaveMode',f'<int32 {target}>'])
    panels=list(Path('/sys/class/drm').glob('card*-DSI-*'))
    if len(panels)!=1:raise RuntimeError('Unique internal panel required')
    expected='On' if target==0 else 'Off'
    for _ in range(20):
        if (panels[0]/'dpms').read_text().strip()==expected and get_mode(prefix)==target:return expected
        time.sleep(.1)
    raise RuntimeError('Panel transition not confirmed')

def notify(value):
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:s.sendto(value.encode(),address)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-backed-up-power-key',required=True,action='store_true')
    p.add_argument('--user',default='ubuntu');p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    if os.geteuid()!=0 or EVENT.size!=24:raise RuntimeError('Root/qualified ARM64 input ABI required')
    s=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    account=pwd.getpwnam(a.user)
    if account.pw_uid!=1000:raise RuntimeError('Expected desktop account')
    path=discover()
    if a.check_only:
        get_mode(session_prefix(a.user,account.pw_uid));print('Power key and native panel/session interfaces available');return
    load_wake_backend()
    wake=WakeInput()
    before=path.lstat()
    if not stat.S_ISCHR(before.st_mode):raise RuntimeError('Expected input character device')
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_rdev!=before.st_rdev:raise RuntimeError('Input device changed')
        # EVIOCSCLOCKID changes only this reader's event timestamps.
        fcntl.ioctl(fd,0x400445A0,struct.pack('@i',time.CLOCK_MONOTONIC))
        notify('READY=1');last=None;pending=b'';cached_mode=panel_mode();press_mode=None;pressed=False
        while True:
            notify('WATCHDOG=1')
            ready,_,_=select.select([fd],[],[],.1)
            if not ready:
                cached_mode=panel_mode();continue
            chunk=os.read(fd,EVENT.size*64)
            if not chunk:raise RuntimeError('Power key input disappeared')
            pending+=chunk
            while len(pending)>=EVENT.size:
                sec,usec,kind,code,value=EVENT.unpack(pending[:EVENT.size]);pending=pending[EVENT.size:]
                now=sec+usec/1_000_000
                if power_press(kind,code,value,last,now):
                    last=now;press_mode=cached_mode;pressed=True;continue
                if not (kind==1 and code==116 and value==0 and pressed):continue
                pressed=False
                # Let GNOME process release activity before deliberately blanking.
                time.sleep(.2)
                try:
                    result=toggle(session_prefix(a.user,account.pw_uid),press_mode,wake)
                    cached_mode=0 if result=='On' else 3
                    print(json.dumps({'power_key_panel':result}),flush=True)
                except Exception as error:print(json.dumps({'power_key_deferred':str(error)}),flush=True)
    finally:
        os.close(fd);wake.close()

if __name__=='__main__':main()
