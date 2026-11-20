#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Hold an authorized desktop location client while the diagnostic window lives."""
import subprocess
from gi.repository import Gio, GLib
bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
service='org.freedesktop.GeoClue2';manager='/org/freedesktop/GeoClue2/Manager'
def call(path,iface,method,args=None):
    return bus.call_sync(service,path,iface,method,args,None,0,10000,None)
client=call(manager,service+'.Manager','GetClient').unpack()[0]
try:
    for key,value in [('DesktopId',GLib.Variant('s','g965n-xgps')),('RequestedAccuracyLevel',GLib.Variant('u',8))]:
        call(client,'org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',(service+'.Client',key,value)))
    call(client,service+'.Client','Start')
    subprocess.run(['/usr/bin/xgps','127.0.0.1:2948'],check=True)
finally:
    call(client,service+'.Client','Stop')
    call(manager,service+'.Manager','DeleteClient',GLib.Variant('(o)',(client,)))
