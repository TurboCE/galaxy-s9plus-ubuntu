#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit bounded peer find through stock NetworkManager; never pair/connect.

Names/addresses/IEs stay in a private log; stdout contains only counts and a
generic Fold7-name match. Exact protected BOOT/model/backup inputs are required.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['SM-G965N'],required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--receipt-sha256',required=True)
    p.add_argument('--backup',type=Path,required=True)
    p.add_argument('--backup-sha256',required=True)
    p.add_argument('--log',type=Path,required=True)
    p.add_argument('--duration',type=int,choices=range(5,31),default=15)
    p.add_argument('--confirm-backup-verified',action='store_true')
    p.add_argument('--consent-peer-find',action='store_true')
    args=p.parse_args()
    if os.geteuid()!=0 or not args.confirm_backup_verified or not args.consent_peer_find:
        p.error('Root, model, verified backup and explicit peer-find consent required')
    helper=Path(__file__).with_name('p2p-control-trial.py')
    spec=importlib.util.spec_from_file_location('p2p_guard',helper)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.validate(guard.trusted_json(args.receipt,args.receipt_sha256),guard.trusted_json(args.backup,args.backup_sha256),require_off=False)
    if guard.PARAM.read_text().strip()!='Y':raise ValueError('Persistent control path must already be enabled')
    guard.protected_parent(args.log)
    if stat.S_IMODE(args.log.parent.stat().st_mode)!=0o700:raise ValueError('Log directory must be private0700')
    fd=os.open(args.log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    from gi.repository import Gio,GLib
    bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
    dest='org.freedesktop.NetworkManager';iface=dest+'.Device.WifiP2P'
    path=subprocess.check_output(['nmcli','-g','GENERAL.DBUS-PATH','device','show','p2p-dev-wlp1s0'],text=True,timeout=5).strip()
    if not re.fullmatch('/org/freedesktop/NetworkManager/Devices/[0-9]+',path):raise ValueError('Missing native P2P device')
    def call(path,interface,method,parameters=None):
        return bus.call_sync(dest,path,interface,method,parameters,None,Gio.DBusCallFlags.NONE,5000,None)
    def peers():
        return call(path,'org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',(iface,'Peers'))).unpack()[0]
    baseline=set(peers());seen={};started=False;error=None
    try:
        call(path,iface,'StartFind',GLib.Variant('(a{sv})',({'timeout':GLib.Variant('i',args.duration)},)))
        started=True;deadline=time.monotonic()+args.duration
        while time.monotonic()<deadline:
            for peer in peers():
                seen[peer]=call(peer,'org.freedesktop.DBus.Properties','GetAll',GLib.Variant('(s)',(dest+'.WifiP2PPeer',))).unpack()[0]
            time.sleep(.5)
    except Exception as exc:
        error=type(exc).__name__
        raise
    finally:
        if started:
            try:call(path,iface,'StopFind')
            except Exception as exc:error=error or type(exc).__name__
        with os.fdopen(fd,'w') as stream:json.dump({'peers':seen,'baseline':list(baseline),'error':error},stream,default=str)
        new=[v for k,v in seen.items() if k not in baseline]
        fold=any(re.search(r'(fold\s*7|폴드\s*7)',str(v.get('Name',v.get('DeviceName',''))),re.I) for v in new)
        print(json.dumps({'peer_count':len(seen),'new_peer_count':len(new),'fold7_name_match':fold,'error':error}),flush=True)


if __name__=='__main__':main()
