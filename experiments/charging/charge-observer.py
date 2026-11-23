#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Private bounded recording only: never writes charger or battery controls."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path('/usr/local/lib/g965n-adc-trial')
STATE = Path('/var/lib/g965n-charge-observer')
MODULES = ('g965n-adc-v3', 'g965n-adc-board', 'g965n-charge-snapshot')
REGISTERS = ('int_ok', 'details0', 'details1', 'details2', 'cnfg0', 'cnfg1',
             'cnfg2', 'cnfg3', 'cnfg4', 'cnfg6', 'cnfg9', 'cnfg12')
STOP = False


CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)
def now_ns():return time.clock_gettime_ns(CLOCK)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop(*_):
    global STOP
    STOP = True


class Journal:
    """4 x 4MiB root-only JSONL files, with crash-useful per-record fsync."""
    def __init__(self, root, limit=4*1024*1024):
        self.root, self.limit = root, limit
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink() or root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o077:
            raise RuntimeError('Private state directory required')

    def append(self, value):
        line = json.dumps(value, separators=(',', ':'))+'\n'
        if len(line.encode()) > self.limit:
            raise ValueError('Record exceeds journal budget')
        target = self.root/'samples.jsonl'
        if target.exists() and target.stat().st_size + len(line.encode()) > self.limit:
            (self.root/'samples.3.jsonl').unlink(missing_ok=True)
            for old, new in ((2, 3), (1, 2)):
                source = self.root/f'samples.{old}.jsonl'
                if source.exists(): source.replace(self.root/f'samples.{new}.jsonl')
            target.replace(self.root/'samples.1.jsonl')
        fd = os.open(target, os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(line); stream.flush(); os.fsync(stream.fileno())


def read(path):
    try:
        return path.read_text().strip()
    except OSError as error:
        return {'error': error.errno}




def notify_ready():
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
        sock.sendto(b'READY=1',address)


def kernel_events(fd):
    """Drain this recorder's independent nonblocking kmsg reader, bounded.

    Reading /dev/kmsg does not clear the global ring or other readers' cursors.
    Raw messages stay private and are never uploaded by this service.
    """
    if fd is None: return {'error':'kernel message reader unavailable'}
    messages=[]
    for _ in range(128):
        try:
            data=os.read(fd,16384).decode('utf-8',errors='replace')
        except BlockingIOError: break
        except OSError as error:
            messages.append({'reader_error':error.errno});break
        if not data: break
        if any(key in data.lower() for key in (
                'max777','charger','charge-','battery','power_supply','serror',
                'panic','thermal','watchdog','reboot','shutdown','suspend','resume')):
            messages.append(data)
    return messages


def sample(adc, temperature):
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'time_basis':'CLOCK_BOOTTIME',
              'begin_monotonic_ns': now_ns()}
    result['power_supply'] = {}
    for name in ('max170xx_battery', 'max77705-charger'):
        node = Path('/sys/class/power_supply')/name
        result['power_supply'][name] = {key:read(node/key) for key in (
            'status','health','capacity','voltage_now','current_now','current_avg',
            'temp','online','charge_behaviour','constant_charge_current',
            'constant_charge_voltage','input_current_limit') if (node/key).exists()}
    params = Path('/sys/module/g965n_charge_snapshot/parameters')
    registers = {key:read(params/key) for key in REGISTERS}
    result['registers'] = registers
    controls=Path('/sys/class/power_supply/max77705-charger/device')
    result['charge_intent']={name:read(controls/name) for name in
        ('charge_requested','charge_enabled','charge_control_state') if (controls/name).exists()}
    # Optional diagnostics from the single owning MUIC driver, not an MCU sender.
    # Source/lease reads are sequential and remain private with the other records.
    source_device=Path('/sys/bus/i2c/devices/3-0025')
    if (source_device/'source_status').exists():
        result['input_source']={key:read(source_device/key) for key in
            ('source_status','input_policy_state')}
    # Status and config reads are serialized but not a hardware-atomic snapshot.
    if all(isinstance(registers[k], str) for k in ('details0','details1','cnfg0')):
        d0,d1,c0 = (int(registers[k]) for k in ('details0','details1','cnfg0'))
        result['decoded'] = {'charge':d1&15,'battery':(d1>>4)&7,
                             'input':(d0>>5)&3,'charge_enabled':c0&1}
    if all(isinstance(registers[k], str) for k in ('cnfg1','cnfg2','cnfg9')):
        c1,c2,c9=(int(registers[k]) for k in ('cnfg1','cnfg2','cnfg9'))
        result['configuration']={'fast_charge_timer_code':c1&7,
            'restart_code':(c1>>4)&3,'prequalification_enabled':(c1>>7)&1,
            'charge_current_ua':max(100000,(c2&63)*50000),
            'input_limit_ua':max(100000,((c9&127)+1)*25000)}
        # Compare with intended initialization, not proof of reset or root cause.
        result['source_initialization_mismatch']={k:{'observed':v,'source_expected':expected}
            for k,v,expected in (('fast_charge_timer_code',c1&7,0),
                ('restart_code',(c1>>4)&3,3),('prequalification_enabled',(c1>>7)&1,0))
            if v!=expected}
    try:
        providers = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
                     if (p/'name').read_text().strip() == 'g965n-adc-v3-trial']
        if len(providers)!=1: raise RuntimeError('ADC provider unavailable')
        rows=[]
        for i in range(5):
            row={'monotonic_ns':now_ns()}
            for channel in (4,1,3,11):
                row[str(channel)]=int((providers[0]/f'in_voltage{channel}_raw').read_text())
            rows.append(row)
            if i<4: time.sleep(.02)
        result['adc_raw']=rows
        result['temperature']=temperature.summarize(rows)
    except (OSError,ValueError,RuntimeError) as error:
        result['temperature_error']=str(error)
    result['end_monotonic_ns']=now_ns()
    return result



def wait_stable_battery(battery, clock=time.monotonic, sleep=time.sleep):
    deadline=clock()+30
    consecutive=0
    while clock()<deadline:
        if STOP:raise RuntimeError('Stop requested before module load')
        sufficient=(int((battery/'capacity').read_text())>=5 and
                    int((battery/'voltage_now').read_text())>=3500000)
        consecutive=consecutive+1 if sufficient else 0
        if consecutive>=2:return
        sleep(2)
    raise RuntimeError('Insufficient stable battery for initial module load')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-sm-g965n-backed-up-observation', required=True, action='store_true')
    parser.add_argument('--once', action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0: raise RuntimeError('Root required')
    os.umask(0o077)
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,stop)
    # No credential is part of this package. Existing guard verifies real model,
    # exact running #48/BOOT and protected partition backup manifest/live hashes.
    guard=load('guard',Path('/usr/local/lib/g965n-led-trial/led-control.py'))
    guard.preflight()
    adc=load('adc',ROOT/'adc-trial.py')
    pins=json.loads(adc.trusted(ROOT/'observer-pins.json'))
    if pins['module_symvers_sha256']!=adc.ABI or set(pins['modules'])!=set(MODULES):
        raise RuntimeError('Unqualified observation module ABI')
    for name in MODULES:
        module=ROOT/(name+'.ko')
        if hashlib.sha256(adc.trusted(module)).hexdigest()!=pins['modules'][name]:
            raise RuntimeError('Observation module changed')
        if adc.active(name): raise RuntimeError('Existing module owner preserved')
        if subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()!=os.uname().release+' SMP preempt mod_unload aarch64':
            raise RuntimeError('Module ABI changed')
    for name in ('charge-observer.py','adc-trial.py','temperature.py','thermal-policy.py','audit-controls.py'):
        if hashlib.sha256(adc.trusted(ROOT/name)).hexdigest()!=pins['scripts'][name]:
            raise RuntimeError('Observation script changed')
    battery=Path('/sys/class/power_supply/max170xx_battery')
    wait_stable_battery(battery)
    before={'clocks':adc.clocks(),'controls':adc.registers(0x14230000,(0,4,0x10)),
            'irq':(adc.registers(0x10101000,(0xc08,))[0]>>16)&3}
    if not all(v&(1<<21) for v in before['clocks'][:2]) or before['irq']&2:
        raise RuntimeError('Unqualified inherited ADC gate/IRQ state')
    if before['controls'][0]&5 or before['controls'][2]:
        raise RuntimeError('Existing ADC conversion owner preserved')
    journal=Journal(STATE)
    audit=load('audit_controls',ROOT/'audit-controls.py').configure()
    journal.append({'event':'start','utc':datetime.now(timezone.utc).isoformat(),
                    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'before':before,'pins':pins,'control_writer_attribution':audit})
    temperature=load('temperature',ROOT/'temperature.py')
    thermal=load('thermal_policy',ROOT/'thermal-policy.py').ThermalPolicy()
    attempted=[]
    kernel_fd=None
    try:
        try:
            kernel_fd=os.open('/dev/kmsg',os.O_RDONLY|os.O_NONBLOCK)
        except OSError:
            if kernel_fd is not None: os.close(kernel_fd)
            kernel_fd=None
        for name in MODULES:
            attempted.append(name)
            subprocess.run(['insmod',str(ROOT/(name+'.ko')),'enable_g965n=1'],check=True,timeout=10)
        ready=False
        while not STOP:
            started=time.monotonic()
            record=sample(adc,temperature)
            record['kernel_events']=kernel_events(kernel_fd)
            record['shadow_thermal_policy']=thermal.evaluate(record.get('temperature'))
            journal.append(record)
            if not ready:
                notify_ready();ready=True
            if args.once: break
            while not STOP and time.monotonic()-started<15: time.sleep(.2)
    finally:
        if kernel_fd is not None: os.close(kernel_fd)
        for name in reversed(attempted):
            if adc.active(name):
                subprocess.run(['rmmod',name.replace('-','_')],check=True,timeout=10)
        after={'clocks':adc.clocks(),'controls':adc.registers(0x14230000,(0,4,0x10)),
               'irq':(adc.registers(0x10101000,(0xc08,))[0]>>16)&3}
        journal.append({'event':'stop','utc':datetime.now(timezone.utc).isoformat(),
                        'modules_removed':all(not adc.active(n) for n in MODULES),
                        'before':before,'after':after,'controls_restored':before==after})
        if before!=after: raise RuntimeError('Observation cleanup changed register state')


if __name__=='__main__': main()
