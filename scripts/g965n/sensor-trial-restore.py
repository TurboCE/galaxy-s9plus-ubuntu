#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Snapshot and restore normal GNOME display APIs for a bounded sensor trial."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def display_snapshot(state):
    _serial, monitors, logical, props = state
    modes={spec[0]:next((m[0] for m in available if m[6].get('is-current')),None)
           for spec,available,_p in monitors}
    configs=[]
    for x,y,scale,transform,primary,specs,_p in logical:
        outputs=[]
        for spec in specs:
            if not modes.get(spec[0]):raise ValueError('No current monitor mode')
            outputs.append([spec[0],modes[spec[0]],{}])
        configs.append([x,y,scale,transform,primary,outputs])
    if not configs:raise ValueError('No logical display to snapshot')
    return {'logical':configs,'layout_mode':props.get('layout-mode')}


def restore_parameters(saved,current):
    serial,monitors,_logical,_props=current
    available={spec[0]:{m[0] for m in modes} for spec,modes,_p in monitors}
    expected={o[0] for config in saved['logical'] for o in config[5]}
    if expected != set(available):raise ValueError('Monitor set changed; refusing guessed restore')
    logical=[]
    for x,y,scale,transform,primary,outputs in saved['logical']:
        if not 0<=transform<=7 or not 0<scale<=8:raise ValueError('Invalid saved display geometry')
        converted=[]
        for connector,mode,_props in outputs:
            if mode not in available[connector]:raise ValueError('Saved display mode unavailable')
            converted.append((connector,mode,{}))
        logical.append((x,y,float(scale),transform,bool(primary),converted))
    return serial,logical


def session(action):
    from gi.repository import Gio,GLib
    power=Gio.Settings.new('org.gnome.settings-daemon.plugins.power')
    orientation=Gio.Settings.new('org.gnome.settings-daemon.peripherals.touchscreen')
    proxy=Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION,0,None,'org.gnome.Mutter.DisplayConfig',
        '/org/gnome/Mutter/DisplayConfig','org.gnome.Mutter.DisplayConfig',None)
    if action=='snapshot':
        state=proxy.call_sync('GetCurrentState',None,0,5000,None).unpack()
        print(json.dumps({'display':display_snapshot(state),'orientation_lock':orientation.get_boolean('orientation-lock'),
                          'ambient_enabled':power.get_boolean('ambient-enabled')}))
    elif action=='guard':
        orientation.set_boolean('orientation-lock',True);power.set_boolean('ambient-enabled',False);Gio.Settings.sync()
    elif action=='restore':
        saved=json.load(sys.stdin)
        orientation.set_boolean('orientation-lock',True);Gio.Settings.sync()
        current=proxy.call_sync('GetCurrentState',None,0,5000,None).unpack()
        serial,logical=restore_parameters(saved['display'],current)
        props={}
        if saved['display']['layout_mode'] is not None:props['layout-mode']=GLib.Variant('u',saved['display']['layout_mode'])
        proxy.call_sync('ApplyMonitorsConfig',GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})',(serial,1,logical,props)),0,10000,None)
        orientation.set_boolean('orientation-lock',saved['orientation_lock'])
        power.set_boolean('ambient-enabled',saved['ambient_enabled']);Gio.Settings.sync()
    else:raise ValueError('Unsupported desktop operation')


def desktop(action,data=None):
    command=['sudo','-u','ubuntu','env','XDG_RUNTIME_DIR=/run/user/1000',
             'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','/usr/bin/python3',str(Path(__file__).resolve()),'--session',action]
    return subprocess.check_output(command,input=json.dumps(data).encode() if data is not None else None,timeout=25)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['save','guard','restore'],nargs='?')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--session',choices=['snapshot','guard','restore'])
    args=parser.parse_args()
    if args.session:
        if os.geteuid()==0:parser.error('Desktop calls must use ordinary session user')
        session(args.session);return
    if os.geteuid()!=0 or not args.state or not args.action:parser.error('Root action and private state required')
    if args.action=='save':
        snapshot=json.loads(desktop('snapshot'))
        fd=os.open(args.state,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(snapshot,stream);stream.flush();os.fsync(stream.fileno())
    elif args.action=='guard':desktop('guard')
    else:
        # Stop real publication before restoring the old monitor/setting state.
        subprocess.run(['systemctl','stop','g965n-sensors.service'],check=True,timeout=215)
        fd=os.open(args.state,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:saved=json.load(stream)
        desktop('restore',saved)
        print('Sensor trial stopped; original display and desktop settings restored')

if __name__=='__main__':main()
