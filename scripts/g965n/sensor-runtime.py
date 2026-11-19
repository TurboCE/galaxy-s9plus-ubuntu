#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Opt-in sensor-only supervisor. No installer, modem, identity mounts or reloads."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import time
import types
from contextlib import contextmanager

BASE=Path('/run/g965n-vendor-runtime')
ROOT=BASE/'root'
OWNER=BASE/'sensor-owner.json'
LEASE=Path('/run/g965n-vendor-runtime.lock')
INSTANCE=Path('/run/g965n-sensor-service.lock')
BOOT_ID=Path('/proc/sys/kernel/random/boot_id')
PARTITIONS={'BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM'}
NODE_NAMES=('null','zero','random','urandom','ttyBCM','bbd_control','bbd_sensor','bbd_patch')
LHD='/vendor/bin/hw/lhd'
LHD_CONFIG='/vendor/etc/sensor/lhd.conf'
STOP=False
NOTIFY_ADDRESS=None
UNIT='g965n-sensors.service'


def digest(data):return hashlib.sha256(data).hexdigest()


def trusted_bytes(path,limit=16*1024*1024,private=False):
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise RuntimeError('Expected absolute trusted path')
    for parent in reversed(path.parents):
        st=parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise RuntimeError('Untrusted path ancestor')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1 or st.st_mode&(0o077 if private else 0o022) or st.st_size>limit:
            raise RuntimeError('Expected bounded root-owned ordinary file')
        data=b''
        while len(data)<=limit:
            chunk=os.read(fd,min(1024*1024,limit+1-len(data)))
            if not chunk:break
            data+=chunk
        if len(data)>limit:raise RuntimeError('Trusted file exceeds bound')
        return data
    finally:os.close(fd)


def pinned(entry,limit=16*1024*1024):
    if not {'path','sha256'}<=set(entry) or not re.fullmatch('[0-9a-f]{64}',entry.get('sha256','')):
        raise RuntimeError('Missing pinned input')
    data=trusted_bytes(entry['path'],limit)
    if digest(data)!=entry['sha256'] or ('bytes' in entry and len(data)!=entry['bytes']):
        raise RuntimeError('Pinned input changed')
    return data


def load_program(profile,name):
    entry=profile['programs'][name];data=pinned(entry)
    module=types.ModuleType(name);module.__file__=entry['path']
    exec(compile(data,entry['path'],'exec'),module.__dict__)
    return module


def validate_matrix(matrix):
    if not isinstance(matrix,list) or len(matrix)!=9 or any(type(v)is not int or v not in (-1,0,1) for v in matrix):
        raise RuntimeError('Expected signed permutation mount matrix')
    if any(sum(abs(matrix[r*3+c]) for c in range(3))!=1 for r in range(3)) or any(sum(abs(matrix[r*3+c]) for r in range(3))!=1 for c in range(3)):
        raise RuntimeError('Mount matrix is not an orthogonal axis permutation')


def validate_profile(profile):
    if profile.get('schema')!=1 or profile.get('model')!='SM-G965N':raise RuntimeError('Expected G965N profile')
    if profile.get('runtime_view', 'legacy') not in ('legacy', 'isolated-sensors'):
        raise RuntimeError('Unknown sensor runtime view')
    if set(profile['programs'])!={'supervisor','runtime','kernel_verifier','broker','ssp_probe'}:
        raise RuntimeError('Unexpected program set')
    for entry in profile['programs'].values():pinned(entry)
    if digest(trusted_bytes(Path(__file__).absolute()))!=profile['programs']['supervisor']['sha256']:
        raise RuntimeError('Supervisor source drift')
    backup=json.loads(pinned(profile['backup_manifest']))
    parts=backup.get('partitions',[]);entries={p['name']:p for p in parts}
    if backup.get('model')!='SM-G965N' or backup.get('complete')is not True or len(parts)!=9 or set(entries)!=PARTITIONS:
        raise RuntimeError('Expected verified nine-partition backup manifest')
    if not all(type(e.get('bytes'))is int and e['bytes']>0 and re.fullmatch('[0-9a-f]{64}',e.get('sha256','')) for e in entries.values()):
        raise RuntimeError('Invalid backup metadata')
    kernel=json.loads(pinned(profile['kernel_receipt']))
    if kernel.get('built_in_iio')is not True or kernel.get('boot_sha256')!=profile['expected_boot_sha256']:raise RuntimeError('BOOT selection mismatch')
    load_program(profile,'kernel_verifier').verify_kernel(kernel)
    for key,feature in (('module','sensors'),('iio_bridge','iio-bridge')):
        module=pinned(profile[key],64*1024*1024)
        entry=kernel.get('modules',{}).get(feature,{})
        if entry.get('sha256')!=digest(module) or entry.get('bytes')!=len(module):
            raise RuntimeError('Module does not match exact startup package: '+feature)
    for key in ('module','iio_bridge'):
        if type(profile[key].get('bytes'))is not int or profile[key]['bytes']<=0:raise RuntimeError('Module byte size must be pinned')
        data=pinned(profile[key],64*1024*1024)
        if len(data)<64 or data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<HH',data,16)!=(1,183):
            raise RuntimeError('Expected AArch64 kernel module')
        # Parse ABI without executing a module or trusting a filename.
        info=elf_section(data,'.modinfo')
        values=[v.decode('ascii') for v in info.split(b'\0') if v.startswith(b'vermagic=')]
        if len(values)!=1 or values[0].split('=',1)[1].split()!=[kernel['kernel_release'],'SMP','preempt','mod_unload','aarch64']:
            raise RuntimeError('Module vermagic mismatch')
    if profile['hub_patch']['path']!=str(Path('/lib/firmware/g965n/bcm4773-patch.bin').resolve()):raise RuntimeError('Expected canonical own firmware path')
    if not pinned(profile['hub_patch'],4*1024*1024):raise RuntimeError('Empty own hub firmware')
    if profile['iio_bridge'].get('device')!='/dev/g965n-iio-bridge':raise RuntimeError('Unexpected IIO bridge node')
    accel=profile.get('accel',{})
    if not isinstance(accel,dict) or type(accel.get('enabled'))is not bool:raise RuntimeError('Acceleration enable must be explicit boolean')
    if accel.get('enabled',False):
        if accel.get('range_g')!=8:raise RuntimeError('Expected qualified 8g acceleration range')
        validate_matrix(accel['mount_matrix'])
        evidence=json.loads(pinned(profile['orientation_evidence']))
        if any(evidence.get(k)!=v for k,v in {'model':'SM-G965N','range_g':8,'mount_matrix':accel['mount_matrix'],'status':'verified','geometry_validated':True}.items()):
            raise RuntimeError('Orientation evidence does not qualify selected matrix')
    elif 'mount_matrix' in accel or 'orientation_evidence' in profile:
        raise RuntimeError('ALS-only profile must not invent orientation evidence or matrix')
    optional_sensors=('pressure','proximity','gyro')
    if any(key in profile for key in ('magnetic_capture','magnetic_initialization',*optional_sensors)):
        program=load_program(profile,'broker')
        program.magnetic_capture_policy(profile)
        program.magnetic_initialization(profile)
        for name in optional_sensors:
            if name in profile:
                program.optional_sensor_enabled(profile,name)
    transport_policy(profile)
    if set(profile['identity'])!={'chip_id','firmware','sensor_mask'} or any(type(v)is not int or v<0 for v in profile['identity'].values()):
        raise RuntimeError('Expected pinned hub identity facts')
    for name in ('startup','cleanup'):
        value=profile['timeouts'][name]
        if type(value)is not int or not 1<=value<=90:raise RuntimeError('Unbounded startup/cleanup deadline')
    return kernel


def elf_section(data,wanted):
    if len(data)<64:raise RuntimeError('Truncated ELF')
    offset=struct.unpack_from('<Q',data,40)[0];size,count,strings=struct.unpack_from('<HHH',data,58)
    if size!=64 or not 0<strings<count<=4096 or offset+size*count>len(data):raise RuntimeError('Invalid ELF section table')
    def section(index):
        start,length=struct.unpack_from('<QQ',data,offset+size*index+24)
        if start+length>len(data):raise RuntimeError('ELF section exceeds file')
        return data[start:start+length]
    names=section(strings);found=[]
    for index in range(count):
        n=struct.unpack_from('<I',data,offset+size*index)[0]
        if n>=len(names):raise RuntimeError('Bad ELF string index')
        if names[n:].split(b'\0',1)[0].decode('ascii')==wanted:found.append(section(index))
    if len(found)!=1 or not found[0]:raise RuntimeError('Required module section absent')
    return found[0]


@contextmanager
def lock_file(path,operation):
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1 or st.st_mode&0o077:
            raise RuntimeError('Untrusted lock inode')
        fcntl.flock(fd,operation|fcntl.LOCK_NB)
        yield fd
    finally:os.close(fd)


def mount_fingerprint():
    entries=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        cells=line.split();point=cells[4].replace('\\040',' ')
        if point==str(BASE) or point.startswith(str(BASE)+'/'):entries.append(line)
    return sorted(entries)


def cgroup_path():
    lines=Path('/proc/self/cgroup').read_text().splitlines()
    paths=[line[3:] for line in lines if line.startswith('0::/')]
    if len(paths)!=1 or '..' in Path(paths[0]).parts:raise RuntimeError('Expected unified service cgroup')
    return paths[0]


def process_start(pid):
    try:return Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None


def cgroup_members(group):
    path=Path('/sys/fs/cgroup')/group.lstrip('/')/'cgroup.procs'
    if not path.exists():return {}
    return {pid:process_start(pid) for pid in path.read_text().split()}


def quiescent_owner(value):
    group=value.get('cgroup','')
    if not group.startswith('/') or '..' in Path(group).parts:raise RuntimeError('Invalid owned cgroup')
    allowed=value.get('baseline',{})
    for pid,start in cgroup_members(group).items():
        if pid!=str(os.getpid()) and (start is None or allowed.get(pid)!=start):
            raise RuntimeError('Owned runtime still has unconfirmed child processes; preserved')


def write_owner(profile_sha):
    group=cgroup_path()
    baseline=cgroup_members(group)
    if OWNER.exists():baseline=json.loads(trusted_bytes(OWNER))['baseline']
    value={'schema':1,'profile_sha256':profile_sha,'boot_id':BOOT_ID.read_text().strip(),
           'mounts':mount_fingerprint(),'cgroup':group,'baseline':baseline}
    temp=OWNER.with_suffix('.new')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,OWNER)
    finally:
        if temp.exists():temp.unlink()


def cleanup_owned(runtime,profile_sha):
    if not OWNER.exists():
        if mount_fingerprint():raise RuntimeError('Unowned runtime preserved')
        return
    value=json.loads(trusted_bytes(OWNER))
    if value.get('schema')!=1 or value.get('profile_sha256')!=profile_sha or value.get('boot_id')!=BOOT_ID.read_text().strip() or value.get('mounts')!=mount_fingerprint():
        raise RuntimeError('Runtime ownership changed; preserved')
    quiescent_owner(value)
    runtime.teardown()
    if mount_fingerprint():raise RuntimeError('Owned mounts remain; receipt preserved')
    OWNER.unlink()


def sensor_view(profile):
    for name in ('system','vendor'):
        path=ROOT/name
        if not os.path.ismount(path) or not os.statvfs(path).f_flag&os.ST_RDONLY:raise RuntimeError('Vendor runtime must be read-only')
    for path in (ROOT/'mnt/vendor/efs',ROOT/'mnt/vendor/cpefs',ROOT/'dev/block'):
        if path.exists() or path.is_symlink():raise RuntimeError('Identity/modem runtime is not sensor-only')
    if list((ROOT/'dev').glob('umts_*')):raise RuntimeError('Modem device in sensor runtime')
    for name in NODE_NAMES:
        host=Path('/dev')/name;node=ROOT/'dev'/name
        if not stat.S_ISCHR(node.lstat().st_mode) or node.stat().st_rdev!=host.stat().st_rdev:raise RuntimeError('Sensor device-node identity changed')
    for path,key in [(ROOT/LHD.lstrip('/'),'lhd_sha256'),(ROOT/LHD_CONFIG.lstrip('/'),'config_sha256')]:
        if digest(trusted_bytes(path))!=profile['vendor'][key]:raise RuntimeError('Own vendor program/config changed')


def bridge_policy(profile):
    enabled=profile.get('accel',{}).get('enabled',False)
    params=['enable_g965n=1','enable_accel='+str(int(enabled))]
    expected={'enable_g965n':'Y','enable_accel':'Y' if enabled else 'N'}
    if enabled:
        matrix=','.join(str(v) for v in profile['accel']['mount_matrix'])
        params.append('accel_mount_matrix='+matrix);expected['accel_mount_matrix']=matrix
    for name in ('pressure','proximity','gyro'):
        if name in profile:
            parameter='enable_'+name
            enabled=profile[name]['enabled']
            params.append(parameter+'='+str(int(enabled)))
            expected[parameter]='Y' if enabled else 'N'
    return params,expected


def ensure_module(entry,name,parameters,expected_parameters):
    data=pinned(entry,64*1024*1024)
    directory=Path('/sys/module')/name
    if directory.exists():
        if (directory/'initstate').read_text().strip()!='live':raise RuntimeError('Existing module is not fully live; preserved')
        note=directory/'notes/.note.gnu.build-id'
        if note.read_bytes()!=elf_section(data,'.note.gnu.build-id'):raise RuntimeError('Loaded module build identity differs; no reload')
        for key,value in expected_parameters.items():
            if (directory/'parameters'/key).read_text().strip()!=value:raise RuntimeError('Existing module parameters differ; preserved')
        return
    fd=os.open(entry['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or info.st_mode&0o022 or info.st_size!=len(data):
            raise RuntimeError('Module load FD changed type/ownership/size')
        if digest(os.read(fd,len(data)+1))!=digest(data):raise RuntimeError('Module changed before load')
        os.lseek(fd,0,os.SEEK_SET)
        subprocess.run(['/usr/sbin/insmod','/proc/self/fd/'+str(fd),*parameters],pass_fds=(fd,),check=True,timeout=30)
    finally:os.close(fd)
    if not directory.exists() or (directory/'initstate').read_text().strip()!='live':raise RuntimeError('Module did not become live')
    if (directory/'notes/.note.gnu.build-id').read_bytes()!=elf_section(data,'.note.gnu.build-id'):
        raise RuntimeError('Newly loaded module identity cannot be verified')
    for key,value in expected_parameters.items():
        if (directory/'parameters'/key).read_text().strip()!=value:raise RuntimeError('Newly loaded module parameters differ')


def transport_policy(profile):
    value=profile.get('transport',{'strict_tx_ack':False})
    if (not isinstance(value,dict) or not {'strict_tx_ack'} <= set(value) <= {'strict_tx_ack','tx_ack_diagnostics'}
            or any(type(item)is not bool for item in value.values())):
        raise RuntimeError('Expected explicit boolean SSI transport policy')
    info=elf_section(pinned(profile['module'],64*1024*1024),'.modinfo')
    capable=b'parmtype=strict_tx_ack:bool' in info.split(b'\0')
    if value['strict_tx_ack'] and not capable:
        raise RuntimeError('Selected transport module has no checked-ACK capability')
    parameters=['enable_g965n=1']
    expected={'enable_g965n':'Y','supply_cut':'N','bitbang':'N'}
    if capable:
        enabled=value['strict_tx_ack']
        parameters.append('strict_tx_ack='+('1' if enabled else '0'))
        expected['strict_tx_ack']='Y' if enabled else 'N'
    diagnostic = value.get('tx_ack_diagnostics', False)
    diag_capable = b'parmtype=tx_ack_diagnostics:bool' in info.split(b'\0')
    if diagnostic and (not diag_capable or not value['strict_tx_ack']):
        raise RuntimeError('ACK diagnostics require checked SSI mode on a compatible module')
    if diag_capable:
        parameters.append('tx_ack_diagnostics=' + ('1' if diagnostic else '0'))
        expected['tx_ack_diagnostics'] = 'Y' if diagnostic else 'N'
    return parameters,expected


def drop_vendor_privileges():
    libc=ctypes.CDLL(None,use_errno=True)
    def check(result):
        if result:raise OSError(ctypes.get_errno(),'Failed vendor privilege restriction')
    check(libc.prctl(38,1,0,0,0))  # PR_SET_NO_NEW_PRIVS
    # Empty bounding set prevents UID0 exec from regaining capabilities.
    last=int(Path('/proc/sys/kernel/cap_last_cap').read_text())
    for cap in range(last+1):check(libc.prctl(24,cap,0,0,0))  # PR_CAPBSET_DROP
    class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
    class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
    check(libc.capset(ctypes.byref(Header(0x20080522,0)),(Data*2)()))


def vendor_child():
    os.chroot(ROOT);os.chdir('/')
    drop_vendor_privileges()


def broker_command(profile,path,ready,stop):
    return ['/usr/bin/python3',profile['programs']['broker']['path'],'--profile',str(path),
            '--sensor-service-child','--ready-fd',str(ready),'--stop-fd',str(stop)]


def verify_service_unit():
    raw=subprocess.check_output(['systemctl','show',UNIT,'--property=Id,MainPID,ControlGroup,DevicePolicy'],text=True)
    fields=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    if fields.get('Id')!=UNIT or fields.get('MainPID')!=str(os.getpid()) or fields.get('ControlGroup')!=cgroup_path() or fields.get('DevicePolicy')!='closed':
        raise RuntimeError('Run only as the guarded service MainPID with closed device policy')


def sensor_device_allowlist(setup=False):
    result=[('/dev/sda10','r'),('/dev/sda18','r'),('/dev/sda19','r')]
    for path in [*(Path('/dev')/name for name in NODE_NAMES),Path('/dev/zrn_ssp'),Path('/dev/g965n-iio-bridge')]:
        info=path.lstat()
        if not stat.S_ISCHR(info.st_mode):raise RuntimeError('Expected exact sensor character node')
        result.append((str(path),'rwm' if setup else 'rw'))
    return result


def apply_device_policy(setup=False):
    verify_service_unit()
    allow=sensor_device_allowlist(setup=setup)
    from gi.repository import Gio,GLib
    bus=Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM,0,None,
        'org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager',None)
    bus.call_sync('SetUnitProperties',GLib.Variant('(sba(sv))',
        (UNIT,True,[('DevicePolicy',GLib.Variant('s','closed')),('DeviceAllow',GLib.Variant('a(ss)',allow))])),0,5000,None)


def notify_ready():
    address=NOTIFY_ADDRESS
    if address:
        if address.startswith('@'):address='\0'+address[1:]
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as stream:
            stream.connect(address);stream.sendall(b'READY=1')


def await_ready(broker,lhd,fd,seconds):
    deadline=time.monotonic()+seconds;data=b''
    while time.monotonic()<deadline and not STOP:
        if broker.poll()is not None or lhd.poll()is not None:raise RuntimeError('Sensor child exited before readiness')
        if select.select([fd],[],[],min(.2,max(0,deadline-time.monotonic())))[0]:
            chunk=os.read(fd,32-len(data))
            if not chunk:raise RuntimeError('Broker closed readiness pipe')
            data+=chunk
            if data==b'READY\n':return
            if not b'READY\n'.startswith(data):raise RuntimeError('Invalid broker readiness acknowledgement')
    raise RuntimeError('Sensor readiness deadline or stop')


def stop_children(broker,lhd,stop_fd,seconds):
    failures=[]
    if stop_fd is not None:
        try:os.write(stop_fd,b'STOP\n')
        except BrokenPipeError:pass
        finally:os.close(stop_fd)
    for name,child in [('broker',broker),('lhd',lhd)]:
        if child is None:continue
        try:
            if name=='lhd' and child.poll()is None:child.terminate()
            result=child.wait(timeout=seconds)
            if result and name=='broker':failures.append('broker cleanup failed')
        except subprocess.TimeoutExpired:
            child.kill()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:failures.append(name+' still alive after kill')
            failures.append(name+' exceeded cleanup deadline')
    if failures:raise RuntimeError('; '.join(failures))


def check_stop():
    if STOP:raise RuntimeError('Sensor startup cancelled; no further child/module started')


def supervise(profile,path,profile_sha):
    global BASE, ROOT, OWNER, LEASE
    verify_service_unit()
    runtime=load_program(profile,'runtime')
    if profile.get('runtime_view') == 'isolated-sensors':
        runtime.select_sensor_runtime()
        BASE, ROOT, LEASE = runtime.BASE, runtime.ROOT, runtime.RUNTIME_LOCK
        OWNER = BASE / 'sensor-owner.json'
    broker=lhd=None;stop_fd=None
    with lock_file(INSTANCE,fcntl.LOCK_EX),lock_file(LEASE,fcntl.LOCK_EX) as lease:
        if mount_fingerprint():cleanup_owned(runtime,profile_sha)
        if OWNER.exists():raise RuntimeError('Stale owner receipt without mounts; review required')
        try:
            runtime.prepare(sensor_only=True,create_devices=False)
            write_owner(profile_sha)
            # Verify fixed owner binaries before any module/firmware hardware access.
            for vendor,key in [(LHD,'lhd_sha256'),(LHD_CONFIG,'config_sha256')]:
                if digest(trusted_bytes(ROOT/vendor.lstrip('/')))!=profile['vendor'][key]:raise RuntimeError('Vendor input mismatch')
            check_stop()
            parameters,expected=transport_policy(profile)
            ensure_module(profile['module'],'zrn_bbd',parameters,expected)
            check_stop()
            params,expected=bridge_policy(profile)
            ensure_module(profile['iio_bridge'],'g965n_iio_bridge',params,expected)
            check_stop()
            apply_device_policy(setup=True)
            try:
                runtime.device_nodes(include_modem=False)
                sensor_view(profile)
                check_stop()
            finally:
                # Revoke mknod before either child, including failed setup paths.
                apply_device_policy(setup=False)
            write_owner(profile_sha)
            fcntl.flock(lease,fcntl.LOCK_SH)  # Atomic downgrade; parent retains this FD until both children exit.
            env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','G965N_SENSOR_PROFILE_SHA256':profile_sha}
            check_stop()
            lhd=subprocess.Popen([LHD,LHD_CONFIG],preexec_fn=vendor_child,env=env,stdin=subprocess.DEVNULL)
            ready_read,ready_write=os.pipe();stop_read,stop_fd=os.pipe()
            try:
                try:
                    check_stop()
                    broker=subprocess.Popen(broker_command(profile,path,ready_write,stop_read),pass_fds=(ready_write,stop_read),env=env,stdin=subprocess.DEVNULL)
                finally:os.close(ready_write);os.close(stop_read)
                await_ready(broker,lhd,ready_read,profile['timeouts']['startup'])
            finally:os.close(ready_read)
            notify_ready()
            while not STOP:
                if broker.poll()is not None or lhd.poll()is not None:raise RuntimeError('Sensor runtime child failed; no automatic restart')
                time.sleep(.2)
        finally:
            try:stop_children(broker,lhd,stop_fd,profile['timeouts']['cleanup'])
            finally:
                if any(child is not None and child.poll()is None for child in (broker,lhd)):
                    raise RuntimeError('Live sensor child preserved; no runtime teardown')
                # Never unmount while another cooperating client holds a lease.
                fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if OWNER.exists():cleanup_owned(runtime,profile_sha)
                elif mount_fingerprint():raise RuntimeError('Partial unreceipted runtime preserved for review')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['check','run'])
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--profile-sha256',required=True)
    p.add_argument('--model',choices=['SM-G965N'],required=True)
    p.add_argument('--confirm-backup-verified',action='store_true')
    p.add_argument('--consent-start-sensors',action='store_true')
    args=p.parse_args()
    global NOTIFY_ADDRESS
    NOTIFY_ADDRESS=os.environ.pop('NOTIFY_SOCKET',None)
    if os.geteuid()!=0:raise SystemExit('Run under root with a private validated profile')
    raw=trusted_bytes(args.profile,1024*1024,private=True)
    if digest(raw)!=args.profile_sha256:raise SystemExit('Explicit profile fingerprint mismatch')
    profile=json.loads(raw);validate_profile(profile)
    if args.action=='check':print('Sensor profile inputs verified; nothing started');return
    if not args.confirm_backup_verified or not args.consent_start_sensors:raise SystemExit('Explicit verified-backup and sensor-start consent required')
    os.umask(0o077)
    def stop(signum,frame):
        global STOP
        STOP=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    supervise(profile,args.profile,args.profile_sha256)


if __name__=='__main__':main()
