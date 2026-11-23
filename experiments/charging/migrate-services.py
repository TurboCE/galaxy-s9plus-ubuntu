#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description='Migrate guarded receipts for the reviewed #48 to #49 charging BOOT trial; never flashes.')
parser.add_argument('--expected-from',type=int,choices=(48,49),default=48)
parser.add_argument('--expected-to',type=int,choices=(49,50),default=49)
parser.add_argument('--old-root', type=Path, required=True)
parser.add_argument('--new-root', type=Path, required=True)
parser.add_argument('--backup-manifest', type=Path, required=True)
parser.add_argument('--boot', type=Path, required=True)
parser.add_argument('--confirm-sm-g965n-charging-boot-only', action='store_true', required=True)
args = parser.parse_args()
if (args.expected_from,args.expected_to) not in ((48,49),(49,50)):
    raise RuntimeError('Unreviewed migration pair')
if os.geteuid() != 0 or not os.uname().version.startswith('#'+str(args.expected_to)+' '):
    raise RuntimeError('Run only on the authorized native #49 SM-G965N charging trial')
BOOT_HASH = hashlib.sha256(args.boot.read_bytes()).hexdigest()
BOOT_BYTES = args.boot.stat().st_size
os.umask(0o077)
roots = Path('/var/lib/g965n-sensors')
old_root, new_root = args.old_root, args.new_root
if old_root.parent != roots or new_root.parent != roots or old_root == new_root:
    raise RuntimeError('Expected distinct direct children of the checked sensor state root')
if old_root.is_symlink() or new_root.is_symlink():
    raise RuntimeError('Profile roots must not be symlinks')
unit_dir = Path('/etc/systemd/system')
sensor_profile = roots/'profile.json'
sensor_digest = roots/'profile.sha256'
lte_config = Path('/var/lib/g965n-lte/desktop/config.json')
features = ('sensors','audio','bluetooth','cover','desktop-lte')
units = {feature:unit_dir/f'g965n-{feature}.service' for feature in features}
backup = args.backup_manifest.read_bytes()
backup_json = json.loads(backup)
def require(condition, message='Charging trial migration preflight mismatch'):
    if not condition:
        raise RuntimeError(message)
require(backup_json['model'] == 'SM-G965N' and backup_json['complete'])
require(backup_json['bootloader'].startswith('G965N') and len(backup_json['partitions']) == 9)
require(not new_root.exists())
def digest(data):
    return hashlib.sha256(data).hexdigest()
def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def write_new(path, data, mode=0o600):
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as stream:
        stream.write(data)
def load(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def pinned(old,new,data):
    result = {**old,'path':str(new),'sha256':digest(data)}
    if 'bytes' in result:
        result['bytes'] = len(data)
    return result
def refresh(receipt):
    require(receipt['model'] == 'SM-G965N' and receipt['kernel_version'].startswith('#'+str(args.expected_from)+' '))
    require(receipt['kernel_release'] == os.uname().release)
    return {**receipt,'boot_bytes':BOOT_BYTES,'boot_sha256':BOOT_HASH,'kernel_version':os.uname().version}
def only(text, old, new, count):
    require(text.count(old) == count, 'Unexpected config pin count')
    return text.replace(old,new)
def atomic(path,data):
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        replacement=Path(tmp.name)
    shutil.copystat(path,replacement)
    replacement.replace(path)

old_startup = json.loads((old_root/'startup.json').read_bytes())
require(not (Path('/sys/module')/'g965n_modem').exists())
require(old_startup['boot_sha256'] != BOOT_HASH)
expected_labels = {e['name']:e for e in backup_json['partitions']}
with open('/dev/sda10','rb') as live:
    require(digest(live.read(BOOT_BYTES)) == BOOT_HASH)
for part,node in {'RECOVERY':'sda11','EFS':'sda3','CPEFS':'sdd1','RADIO':'sda12','DTB':'sda8','DTBO':'sda9'}.items():
    # Require the fresh protected-partition snapshot, including EFS.
    measured = subprocess.check_output(['sha256sum',f'/dev/{node}'],text=True).split()[0]
    require(measured == expected_labels[part]['sha256'], 'Protected partition changed: ' + part)

new_root.mkdir(mode=0o700)
shutil.copytree(old_root/'package',new_root/'package')
write_new(new_root/'startup.json',encoded(refresh(old_startup)))
write_new(new_root/'backup.json',backup)
guard=load(new_root/'package/p2p-control-trial.py','guard48')
guard.validate(json.loads((new_root/'startup.json').read_bytes()),backup_json,require_off=False)
raw = sensor_profile.read_bytes()
profile = json.loads(raw)
old_sensor_hash = digest(raw)
require(sensor_digest.read_text().split()[0] == old_sensor_hash)
old_sensor_path = Path(profile['kernel_receipt']['path'])
old_sensor_receipt = old_sensor_path.read_bytes()
require(digest(old_sensor_receipt) == profile['kernel_receipt']['sha256'])
sensor_receipt = encoded(refresh(json.loads(old_sensor_receipt)))
sensor_receipt_path = new_root/'sensors.json'
write_new(sensor_receipt_path,sensor_receipt)
profile['kernel_receipt'] = pinned(profile['kernel_receipt'],sensor_receipt_path,sensor_receipt)
profile['backup_manifest'] = pinned(profile['backup_manifest'],new_root/'backup.json',backup)
profile['expected_boot_sha256'] = BOOT_HASH
supervisor=load(Path(profile['programs']['supervisor']['path']),'sensor48')
supervisor.validate_profile(profile)
new_profile=encoded(profile)

old_audio_root = Path('/usr/lib/g965n-experiments')/old_startup['boot_sha256'][:16]
new_audio_root = Path('/usr/lib/g965n-experiments')/BOOT_HASH[:16]
require(not new_audio_root.exists())
shutil.copytree(old_audio_root,new_audio_root)
audio_manifest = new_audio_root/'manifest.json'
atomic(audio_manifest,encoded(refresh(json.loads(audio_manifest.read_bytes()))))
for feature in ('audio','bluetooth'):
    subprocess.run(['/usr/bin/python3',str(new_audio_root/'verify.py'),'--verify',
                    str(audio_manifest),'--feature',feature],check=True)

old_cover_root = old_audio_root.with_name(old_audio_root.name + '-cover')
new_cover_root = new_audio_root.with_name(new_audio_root.name + '-cover')
require(not new_cover_root.exists())
shutil.copytree(old_cover_root,new_cover_root)
cover_manifest = new_cover_root/'manifest.json'
atomic(cover_manifest,encoded(refresh(json.loads(cover_manifest.read_bytes()))))
subprocess.run(['/usr/bin/python3',str(new_cover_root/'verify.py'),'--verify',
                str(cover_manifest),'--feature','cover'],check=True)

old_lte_raw=lte_config.read_bytes()
lte=json.loads(old_lte_raw)
require(lte['kernel_profile'] == str(old_root))
require(lte['receipt_sha256'] == digest((old_root/'startup.json').read_bytes()))
require(lte['backup_sha256'] == digest((old_root/'backup.json').read_bytes()))
require(lte['guard_sha256'] == digest((new_root/'package/p2p-control-trial.py').read_bytes()))
lte.update(kernel_profile=str(new_root),receipt_sha256=digest((new_root/'startup.json').read_bytes()),
           backup_sha256=digest(backup))
new_lte=encoded(lte)

updates={sensor_profile:new_profile,sensor_digest:(digest(new_profile)+'\n').encode(),
         lte_config:new_lte}
sensor_unit = only(units['sensors'].read_text(),old_sensor_hash,digest(new_profile),1)
updates[units['sensors']] = sensor_unit.encode()
for feature in ('audio','bluetooth'):
    updates[units[feature]]=only(units[feature].read_text(),str(old_audio_root),str(new_audio_root),3).encode()
updates[units['cover']]=only(units['cover'].read_text(),str(old_cover_root),str(new_cover_root),3).encode()
updates[units['desktop-lte']]=only(units['desktop-lte'].read_text(),digest(old_lte_raw),digest(new_lte),2).encode()
native_bt = unit_dir / 'g965n-bluetooth.service.d/80-native-expander.conf'
if native_bt.is_file():
    updates[native_bt] = only(native_bt.read_text(), str(old_audio_root), str(new_audio_root), 2).encode()
saved = new_root/'previous-settings'
saved.mkdir(mode=0o700)
for path in updates:
    shutil.copy2(path,saved/path.name)
changed = []
try:
    for path,data in updates.items():
        atomic(path,data)
        changed.append(path)
    subprocess.run(['systemctl','daemon-reload'],check=True)
except Exception:
    for path in reversed(changed):
        atomic(path,(saved/path.name).read_bytes())
    subprocess.run(['systemctl','daemon-reload'],check=False)
    raise
subprocess.run(['systemctl','reset-failed',*(path.name for path in units.values())],check=True)
print('Charging BOOT service pins migrated; original service settings preserved.',flush=True)
subprocess.run(['systemctl','start',*(units[n].name for n in ('audio','bluetooth','cover','sensors'))],check=True)
for n in ('audio','bluetooth','cover','sensors'):
    print(units[n].name,subprocess.check_output(['systemctl','is-active',units[n].name],text=True).strip())
