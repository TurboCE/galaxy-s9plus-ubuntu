#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded charging protection with atomic user-intent preservation on #50.

#49 fallback only inhibits. #50 policy recovery never overrides manual inhibit.
This remains a conservative wired subset, not full sec-battery parity.
"""
import argparse
import errno
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time

ROOT=Path('/var/lib/g965n-charge-guardian')
CHARGER=Path('/sys/class/power_supply/max77705-charger')
STOP=False


class HardwareWatchdog:
    """Optional current-boot trial; loading/ownership authorization is separate.

    A module-owned expiry is sticky. Never clear it or automatically disarm on
    missing measurements, service failure, SIGKILL or I2C failure.
    """
    def __init__(self):
        self.params=Path('/sys/module/g965n_charge_wdt/parameters')
        receipt=Path('/var/lib/g965n-charge-guardian/wdt-trial.json')
        if receipt.is_symlink() or receipt.stat().st_uid!=0 or receipt.stat().st_mode&0o077:
            raise RuntimeError('Private watchdog ownership receipt required')
        pins=json.loads(receipt.read_text())
        module=Path('/usr/local/lib/g965n-adc-trial/g965n-charge-wdt.ko')
        if (pins['boot']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip() or
            hashlib.sha256(module.read_bytes()).hexdigest()!=pins['module_sha256'] or
            subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()!=
                os.uname().release+' SMP preempt mod_unload aarch64'):
            raise RuntimeError('Watchdog module/boot ownership changed')
        self.status()  # Module must already have passed separate guarded setup.

    def status(self):
        state=json.loads((self.params/'status').read_text())
        for key in ('owned','wdt_enabled','charge_enabled','owned_expiry_seen'):
            if type(state.get(key)) is not int or state[key] not in (0,1):
                raise RuntimeError('Invalid watchdog status')
        if type(state.get('details1')) is not int or not 0<=state['details1']<=255:
            raise RuntimeError('Invalid watchdog chip status')
        return state

    def update(self, row, now, blocked, online):
        state=self.status()
        if state['owned_expiry_seen'] or state['details1']&15==11:
            return ['hardware_watchdog_expired']
        if bool(state['owned'])!=bool(state['wdt_enabled']):
            return ['hardware_watchdog_ownership_lost']
        # These holds may feed only with actual CHG off; all require fresh ADC
        # and configuration. Faults, malformed data and stale records never feed.
        benign={'temperature_limit','swelling_temperature_stop','swelling_cold_stop',
                'full_stop','full_hold','safety_time_expired','external_power_absent'}
        if (not 0<=now-row.get('end_monotonic_ns',-100_000_000_000)<35_000_000_000 or
                row.get('shadow_thermal_policy',{}).get('valid') is not True or
                set(blocked)-benign):
            return []  # Caller inhibits; IC is allowed to expire autonomously.
        if blocked and state['charge_enabled']:
            return ['hardware_watchdog_waiting_inhibit']
        if online!='1':return []
        if not state['owned'] and state['charge_enabled']:
            return ['hardware_watchdog_waiting_inhibit']
        (self.params/'feed').write_text('1\n')
        after=self.status()
        if not after['owned'] or not after['wdt_enabled'] or after['owned_expiry_seen']:
            raise RuntimeError('Watchdog arm/feed readback failed')
        return []


CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)
def now_seconds():return time.clock_gettime(CLOCK)
def now_ns():return time.clock_gettime_ns(CLOCK)

class SleepLease:
    """Keep software thermal supervision awake only while external power exists."""
    def __init__(self):self.process=None
    def close(self):
        if self.process is None:return
        try:os.killpg(self.process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            self.process.wait(timeout=2)
        self.process=None
    def update(self,powered):
        if not powered:self.close();return True
        if self.process is not None and self.process.poll() is None:return True
        self.close()
        try:
            self.process=subprocess.Popen(['/usr/bin/systemd-inhibit','--what=sleep','--who=G965N-charge-guardian',
                '--why=Charging thermal supervision','--mode=block','/usr/bin/sleep','infinity'],start_new_session=True)
        except OSError:return False
        time.sleep(.1)
        return self.process.poll() is None


def input_ceiling(row, now):
    """Higher input is allowed only under the live kernel's bounded 5V PD lease."""
    try:
        p = row['input_source_policy'];s = p['source'];c = p['control']
        ms = now // 1_000_000
        target=c['requested']
        if (c['owned'] == 1 and target in (900000,1200000) and c['applied'] == target and
            0 < c['deadline_ms'] - ms <= 15000 and
            s['contract_valid'] == 1 and s['source_uv'] == 5000000 and s['source_ua'] >= target and
            0 <= ms - s['sampled_ms'] <= 1500 and 0 <= ms - s['queried_ms'] <= 3000):
            return target
    except (KeyError, TypeError, ValueError):
        pass
    return 500000


def input_source_policy():
    dev = Path('/sys/bus/i2c/devices/3-0025')
    try:
        if (dev/'driver').resolve().name not in ('s9p-max77705-muic', 's9p-max77705-muic-source'):
            return {}
        source = json.loads((dev/'source_status').read_text())
        c = [int(v) for v in (dev/'input_policy_state').read_text().split()]
        if len(c) != 5:return {}
        return {'source':source,'control':dict(zip(('generation','owned','requested','applied','deadline_ms'),c))}
    except (OSError, ValueError, TypeError):
        return {}


def reasons(row,now,wall,equivalent,recharging=False):
    result=[]
    age=now-row.get('end_monotonic_ns',-100_000_000_000)
    if not 0<=age<35_000_000_000:return ['stale_or_missing_sample']
    t=row.get('shadow_thermal_policy',{})
    if t.get('valid') is not True:return ['invalid_temperature']
    if t.get('thermal_charge_permission') is not True:result.append('temperature_limit')
    # Stricter than Android's voltage/current adaptation until that path is qualified.
    if t.get('swelling_high_temperature_policy_required') is not False:result.append('swelling_temperature_stop')
    if t.get('swelling_low_temperature_policy_required',False):result.append('swelling_cold_stop')
    if 'source_initialization_mismatch' not in row:result.append('invalid_chip_configuration')
    elif row['source_initialization_mismatch']:result.append('charger_configuration_drift')
    d=row.get('decoded',{})
    if any(type(d.get(k)) is not int for k in ('charge','battery','input')):
        result.append('invalid_chip_status')  # Data loss is not a latched hardware fault.
    else:
        if d['charge'] not in (0,1,2,3,4,8):result.append('hardware_fault')
        if d['battery'] not in (1,3,4):result.append('battery_fault')
        if d['input']!=3:result.append('input_not_valid')
    try:
        battery=row['power_supply']['max170xx_battery'];supply=row['power_supply']['max77705-charger']
        voltage=int(battery['voltage_now']);soc=int(battery['capacity'])
        cc=int(supply['constant_charge_current']);ilimit=int(supply['input_current_limit']);cv=int(supply['constant_charge_voltage'])
        if voltage>4400000:result.append('battery_overvoltage')
        if not 0<cc<=450000 or not 0<ilimit<=input_ceiling(row,now) or not 4000000<=cv<=4350000:result.append('unqualified_charge_limits')
        if d.get('charge')==4 and soc>=93 and voltage>=4250000:result.append('full_stop')
    except (ValueError,KeyError,TypeError):result.append('invalid_supply_readback')
    # Pinned wired stock USB total10h and 3h equivalent at2500mA. Count all
    # enabled time conservatively: no Android LCD/discharging timer extensions.
    if wall>=(5400 if recharging else 36000) or equivalent>=(5400 if recharging else 10800):result.append('safety_time_expired')
    return result


def notify(message):
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:sock.sendto(message.encode(),address)


def preflight():
    if os.geteuid()!=0:raise RuntimeError('Root required')
    spec=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()


def inhibit(reason):
    before=(CHARGER/'charge_behaviour').read_text()
    if '[auto]' in before:
        (CHARGER/'charge_behaviour').write_text('inhibit-charge\n')
        if '[inhibit-charge]' not in (CHARGER/'charge_behaviour').read_text():raise RuntimeError('Inhibit readback failed')
        print(json.dumps({'action':'inhibit','reason':reason,'boottime_seconds':now_seconds()}),flush=True)



def control_state():
    path=CHARGER/'device/charge_control_state'
    if not path.exists():return None
    values=[int(x) for x in path.read_text().split()]
    if len(values)!=4 or values[0]<0 or any(x not in (0,1) for x in values[1:]):
        raise RuntimeError('Invalid atomic charge-control state')
    return dict(zip(('generation','requested','blocked','actual'),values))


def policy_allow(allow,reason,control=None):
    control=control_state() if control is None else control
    if control is None:
        if not allow:inhibit(reason)
        return
    desired_actual=int(bool(allow and control['requested']))
    if control['blocked']==int(not allow) and control['actual']==desired_actual:return
    try:
        (CHARGER/'device/charge_policy_request').write_text(f"{control['generation']} {int(allow)}\n")
    except OSError as error:
        if error.errno==errno.EAGAIN:return  # Concurrent manual request wins.
        raise
    print(json.dumps({'policy_allow':allow,'user_requested':control['requested'],'reason':reason}),flush=True)


def update_latches(state,row,blocked,online,control,new_boot=False):
    """Keep full/fault holds after CHG-off changes the hardware status code."""
    if state.get('last_online')=='0' and online=='1':
        state.update(wall=0,equivalent=0,hardware_fault=False,configuration_fault=False)
    state['last_online']=online
    if new_boot:state.update(hardware_fault=False,configuration_fault=False)
    if online=='1':
        if 'hardware_fault' in blocked or 'battery_fault' in blocked:state['hardware_fault']=True
        if 'charger_configuration_drift' in blocked:state['configuration_fault']=True
    if 'full_stop' in blocked:state['full_hold']=True
    try:voltage=int(row['power_supply']['max170xx_battery']['voltage_now'])
    except (KeyError,ValueError,TypeError):voltage=None
    if state.get('full_hold') and voltage is not None and voltage<=4280000:
        state.update(full_hold=False,recharging=True,wall=0,equivalent=0)
    if state.get('full_hold') and 'full_stop' not in blocked:blocked.append('full_hold')
    if state.get('hardware_fault') and 'hardware_fault' not in blocked:blocked.append('hardware_fault')
    if state.get('configuration_fault') and 'charger_configuration_drift' not in blocked:blocked.append('charger_configuration_drift')
    if control and control['requested'] and not control['blocked'] and not control['actual'] and online=='1':
        state['hardware_fault']=True
        if 'unexpected_hardware_disable' not in blocked:blocked.append('unexpected_hardware_disable')
    return blocked


def save(state):
    with tempfile.NamedTemporaryFile(mode='w',dir=ROOT,delete=False) as file:
        json.dump(state,file);file.flush();os.fsync(file.fileno());tmp=Path(file.name)
    tmp.chmod(0o600);tmp.replace(ROOT/'state.json')


def sample():
    # File capped at4MiB by the recorder. A concurrent partial final line is
    # ignored; it never becomes a valid temperature measurement.
    lines=Path('/var/lib/g965n-charge-observer/samples.jsonl').read_text().splitlines()
    for line in reversed(lines):
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        if 'end_monotonic_ns' in row:return row
    return {}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-charge-policy',action='store_true',required=True)
    p.add_argument('--hardware-watchdog',action='store_true',help='Guarded current-boot owned-module trial only')
    modes=p.add_mutually_exclusive_group();modes.add_argument('--fail-closed',action='store_true');modes.add_argument('--test-inhibit',action='store_true')
    a=p.parse_args();os.umask(0o077);preflight()
    if a.fail_closed or a.test_inhibit:
        control=control_state()
        if control and (ROOT/'state.json').exists():
            state=json.loads((ROOT/'state.json').read_text());state['user_requested']=bool(control['requested']);state['reasons']=['explicit-validation' if a.test_inhibit else 'guardian-stopped'];save(state)
        policy_allow(False,'explicit-validation' if a.test_inhibit else 'guardian-stopped',control);return
    ROOT.mkdir(mode=0o700,exist_ok=True)
    if ROOT.is_symlink() or ROOT.stat().st_uid!=0 or ROOT.stat().st_mode&0o077:raise RuntimeError('Private guardian state required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();now=now_seconds()
    state=json.loads((ROOT/'state.json').read_text()) if (ROOT/'state.json').exists() else {'wall':0,'equivalent':0}
    for key in ('wall','equivalent'):
        if type(state[key]) not in (int,float) or not math.isfinite(state[key]) or state[key]<0:
            raise RuntimeError('Invalid persisted protection budget')
    new_boot=state.get('boot')!=boot
    if new_boot:
        state['wall']+=now;state['equivalent']+=now*450000/2500000;state['last']=now
    elif state.get('last',now)>now+1:
        raise RuntimeError('Protection clock moved backwards')
    state.update(boot=boot,last=state.get('last',now))
    def stop(*_):
        global STOP
        STOP=True
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    spec=importlib.util.spec_from_file_location('thermal','/usr/local/lib/g965n-adc-trial/thermal-policy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);thermal=module.ThermalPolicy()
    for key,value in state.get('thermal',{}).items():
        if key in vars(thermal) and type(value) is bool:setattr(thermal,key,value)
    # Manual intent remains kernel-per-boot; never race a boot-time manual
    # request by replaying a stale persisted sysfs setting.
    ready=False
    previous=None
    sleep_lease=SleepLease()
    hardware=None
    try:
        if a.hardware_watchdog:
            # Never permit charging during setup or partial watchdog activation.
            policy_allow(False,'hardware-watchdog-setup')
            hardware=HardwareWatchdog()
        while not STOP:
            tick=now_seconds();row=sample();elapsed=max(0,tick-state['last'])
            # Unknown gaps or a restarted process do not reset the protection budget.
            enabled=row.get('decoded',{}).get('charge_enabled')
            online=row.get('power_supply',{}).get('max77705-charger',{}).get('online')
            if enabled==1 and online=='1' and row.get('decoded',{}).get('charge') in (0,1,2,3):
                state['wall']+=elapsed
                try:current=int(row['power_supply']['max77705-charger']['constant_charge_current'])
                except (KeyError,ValueError,TypeError):current=450000
                state['equivalent']+=elapsed*max(450000,current)/2500000
            state['last']=tick
            fresh=0<=now_ns()-row.get('end_monotonic_ns',-100_000_000_000)<35_000_000_000
            row['shadow_thermal_policy']=thermal.evaluate(row.get('temperature') if fresh else None)
            row['input_source_policy']=input_source_policy()
            state['thermal']=vars(thermal).copy()
            control=control_state()
            if control:state['user_requested']=bool(control['requested'])
            online=(CHARGER/'online').read_text().strip()
            if state.get('last_online')=='0' and online=='1':state.update(wall=0,equivalent=0)
            blocked=reasons(row,now_ns(),state['wall'],state['equivalent'],state.get('recharging',False))
            blocked=update_latches(state,row,blocked,online,control,new_boot)
            new_boot=False
            if online=='0' and 'external_power_absent' not in blocked:blocked.append('external_power_absent')
            if not sleep_lease.update(online=='1'):blocked.append('sleep_inhibitor_unavailable')
            if hardware:
                # Inhibit BEFORE a blocked-state kick or any new arm. Manual
                # requests still go through the existing generation-checked CAS.
                if blocked:policy_allow(False,blocked,control)
                extra=hardware.update(row,now_ns(),blocked,online)
                state['hardware_watchdog']=hardware.status()
                if extra:
                    blocked.extend(extra)
                    if any(x in extra for x in ('hardware_watchdog_expired','hardware_watchdog_ownership_lost')):
                        state['hardware_fault']=True
            # Do not turn an unplugged cable into a persistent manual inhibit.
            # With no external input, hardware cannot charge. Preserve CHG intent
            # so input reattachment remains usable under this live supervisor.
            if control is not None or online!='0':policy_allow(not bool(blocked),blocked,control)
            state['reasons']=blocked;save(state)
            if not ready:
                notify('READY=1');ready=True
            if blocked!=previous:print(json.dumps({'protection_reasons':blocked,'auto_enable':'preserved-user-intent-CAS' if control else False}),flush=True);previous=blocked
            notify('WATCHDOG=1')
            for _ in range(25):
                if STOP:break
                time.sleep(.2)
    finally:
        if hardware:policy_allow(False,'hardware-watchdog-supervisor-stopped')
        sleep_lease.close()


if __name__=='__main__':main()
