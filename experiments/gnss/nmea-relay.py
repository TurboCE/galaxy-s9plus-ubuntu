#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded NMEA relay for a private, root-owned trial directory."""
import grp
import os
from pathlib import Path
import select
import socket
import struct
import sys
import time

root=Path(sys.argv[1])
uid=int(sys.argv[2])
gid=grp.getgrnam('geoclue').gr_gid
fifo=os.open(root/'nmea.fifo',os.O_RDWR|os.O_NONBLOCK)
server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
server.bind(str(root/'nmea.sock'))
os.chown(root/'nmea.sock',0,gid)
os.chmod(root/'nmea.sock',0o660)
server.listen(4)
clients=[]
count=0
start=time.monotonic()
try:
    while time.monotonic() - start < 125:
        ready,_,_=select.select([server,fifo],[],[],.3)
        if server in ready:
            client,_=server.accept()
            _, peer_uid, _=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if peer_uid != uid:
                client.close()
            else:
                client.settimeout(.2)
                clients.append(client)
        if fifo in ready:
            data=os.read(fifo,4096)
            for client in clients[:]:
                try:
                    client.sendall(data)
                except OSError:
                    client.close()
                    clients.remove(client)
            count+=data.count(b'\n')
    print(f'Local relay forwarded {count} complete newline delimiters',flush=True)
finally:
    for client in clients:
        client.close()
    server.close()
    os.close(fifo)
