#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded cold screen-on/off QoS check; restores the originally off panel.

Device/UI test only, never invoked by builders. No app launch or partition write.
An independent system timer restores display-off if this process is interrupted.
"""
import argparse,importlib.util,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path('/var/lib/g965n-thermal-qos')
PREFIX=['/usr/sbin/runuser','-u','ubuntu','--','/usr/bin/env',
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','/usr/bin/gdbus','call',
        '--session','--dest','org.gnome.Mutter.DisplayConfig','--object-path','/org/gnome/Mutter/DisplayConfig']
SET=PREFIX+['--method','org.freedesktop.DBus.Properties.Set','org.gnome.Mutter.DisplayConfig','PowerSaveMode']
GET=PREFIX+['--method','org.freedesktop.DBus.Properties.Get','org.gnome.Mutter.DisplayConfig','PowerSaveMode']
UNIT='g965n-thermal-panel-restore'

def read():
    r=json.loads((ROOT/'state.json').read_text())
    r['level']=Path('/sys/module/g965n_thermal_qos/parameters/level').read_text().strip()
    r['cadence']=int(Path('/sys/devices/system/cpu/cpufreq/schedutil/rate_limit_us').read_text())
    r['limits']=[int(Path('/sys/devices/system/cpu/cpufreq/'+n+'/scaling_max_freq').read_text()) for n in ('policy0','policy4')]
    r['limits'].append(int(Path('/sys/class/devfreq/17500000.gpu/max_freq').read_text())//1000)
    return r

def wait_for(off):
    end=time.monotonic()+10
    while time.monotonic()<end:
        r=read()
        if (r.get('panel_off') is off and r.get('thermal_hot') is False and
                r.get('cooling') is off and r['level']==('1' if off else '0')):
            if off and not all(0<x<=y for x,y in zip(r['limits'],(650000,1066000,260000))):time.sleep(.2);continue
            return r
        time.sleep(.2)
    raise RuntimeError('Expected cold panel/QoS transition did not complete')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-backed-up-panel-test',action='store_true',required=True);p.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    s=importlib.util.spec_from_file_location('g','/usr/local/lib/g965n-led-trial/led-control.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    original=subprocess.check_output(GET,text=True,timeout=5).strip()
    if not re.fullmatch(r'\(<3>,\)',original):raise RuntimeError('Requires original display-off; active user display preserved')
    before=read()
    if before.get('thermal_hot') is not False or before.get('reason')!='screen_off_idle':raise RuntimeError('Requires naturally cooled screen-off state')
    if subprocess.run(['systemctl','is-active','--quiet',UNIT+'.timer']).returncode==0:raise RuntimeError('Existing restore timer preserved')
    subprocess.run(['systemd-run','--unit='+UNIT,'--on-active=30s',*SET,'<int32 3>'],check=True)
    on=None;off=None
    try:
        subprocess.run(SET+['<int32 0>'],check=True,timeout=5)
        on=wait_for(False)
    finally:
        subprocess.run(SET+['<int32 3>'],check=True,timeout=5)
        off=wait_for(True)
        subprocess.run(['systemctl','stop',UNIT+'.timer'],check=True)
    print(json.dumps({'screen_on':on,'screen_off':off,'result':'passed'}),flush=True)

if __name__=='__main__':main()
