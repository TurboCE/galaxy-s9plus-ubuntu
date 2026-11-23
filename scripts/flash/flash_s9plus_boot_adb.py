"""Write one boot image to a Galaxy S9+ (star2lte) from its running TWRP.

    python scripts/flash/flash_s9plus_boot_adb.py dist/uniloader/<image>.img

The image must lie under dist/. The script checks the device, the BOOT
mapping and the size, verifies the copy on the phone, writes BOOT, reads it
back and only then reboots. RECOVERY is never touched.
"""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
# adb binary: S9PLUS_ADB, else whatever is on PATH.
ADB = os.environ.get("S9PLUS_ADB", "adb")


def require(ok, message):
    """A safety check that, unlike assert, survives python -O."""
    if not ok:
        raise SystemExit(message)


def find_serial():
    """Every call names the S9+ explicitly, so no other attached phone is ever
    touched. S9PLUS_SERIAL wins; otherwise exactly one star2lte must be on adb."""
    serial = os.environ.get("S9PLUS_SERIAL")
    if serial:
        return serial
    listing = subprocess.run([str(ADB), "devices", "-l"], capture_output=True,
                             text=True, check=True).stdout.splitlines()[1:]
    hits = [line.split()[0] for line in listing if "device:star2lte" in line]
    if len(hits) != 1:
        raise SystemExit(f"{len(hits)} Galaxy S9+ (star2lte) devices on adb - "
                         "set S9PLUS_SERIAL to the one to write")
    return hits[0]


SERIAL = find_serial()
BOOT = "/dev/block/platform/11120000.ufs/by-name/BOOT"


def adb(*args, timeout=30):
    return subprocess.check_output([str(ADB), "-s", SERIAL, *args], text=True,
                                   timeout=timeout).strip()


def upload_boot(image, remote, expected, expected_loader, prefer_sync=False):
    # TWRP can finish exec-in while its transport temporarily goes offline.
    # Recover only this selected transport and recheck the model/hash before
    # fallback: a successful upload must not be retransmitted blindly.
    def matches():
        try:
            return adb('shell', f'sha256sum {remote}').split()[0] == expected
        except (subprocess.SubprocessError, IndexError):
            return False

    def recover_selected():
        failure = None
        for _ in range(2):
            try:
                try:
                    adb('reconnect', timeout=15)
                except subprocess.SubprocessError:
                    pass
                adb('wait-for-recovery', timeout=45)
                require(adb('get-state') == 'recovery', 'Selected transport is not recovery; no partition write performed')
                require(adb('shell', 'getprop ro.product.device') == 'star2lte', 'Recovery model changed; no partition write performed')
                require(adb('shell', 'getprop ro.bootloader') == expected_loader, 'Bootloader identity changed; no partition write performed')
                require(adb('shell', 'id -u') == '0', 'Recovery lost root; no partition write performed')
                return
            except subprocess.SubprocessError as error:
                failure = error
        raise RuntimeError('Selected recovery transport did not return; no partition write performed') from failure

    if matches():
        print('Reusing the checksum-verified temporary BOOT image', flush=True)
        return
    if prefer_sync:
        try:
            adb('push', '-Z', str(image), remote, timeout=90)
        except subprocess.SubprocessError:
            recover_selected()
        if matches():
            print('Uncompressed sync BOOT upload SHA256 verified', flush=True)
            return
    try:
        with image.open('rb') as stream:
            subprocess.run([str(ADB), '-s', SERIAL, 'exec-in', f'cat > {remote}'],
                           stdin=stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=True, timeout=90)
    except subprocess.SubprocessError:
        pass
    recover_selected()
    if matches():
        print('Raw temporary BOOT upload SHA256 verified', flush=True)
        return
    print('Raw upload unavailable; trying bounded legacy sync transfer', flush=True)
    try:
        adb('push', str(image), remote, timeout=90)
    except subprocess.SubprocessError:
        recover_selected()
    require(matches(), 'USB copy checksum mismatch; no partition write performed')


image = Path(sys.argv[1]).resolve()
require(image.is_relative_to((PROJECT / "dist").resolve()), "Image must be in this S9+ project")
blob = image.read_bytes()
require(blob[:8] == b"ANDROID!", "Not an Android-format boot image")
require(struct.unpack_from("<I", blob, 36)[0] == 2048, "Unexpected page size")
require(adb("get-state") == "recovery", "Samsung is not in recovery")
require(adb("shell", "getprop ro.product.device") == "star2lte", "Wrong device")
require(adb("shell", "id -u") == "0", "Recovery is not root")
require(adb("shell", f"readlink -f {BOOT}") == "/dev/block/sda10", "BOOT mapping changed")
require(len(blob) <= int(adb("shell", f"blockdev --getsize64 {BOOT}")), "Image does not fit")
expected = hashlib.sha256(blob).hexdigest()
remote = "/tmp/s9plus-native-boot.img"
upload_mode = os.environ.get('S9PLUS_BOOT_UPLOAD_TRANSPORT', 'sync')
require(upload_mode in ('sync', 'raw'), 'Unknown BOOT upload transport')
upload_boot(image, remote, expected, adb('shell', 'getprop ro.bootloader'), prefer_sync=upload_mode == 'sync')
print(adb("shell", f"dd if={remote} of={BOOT} bs=1048576 && sync", timeout=120))
actual = adb("shell", f"head -c {len(blob)} {BOOT} | sha256sum", timeout=60).split()[0]
require(actual == expected, "BOOT readback checksum mismatch; left in recovery")
print(f"BOOT_READBACK_VERIFIED sha256={expected} bytes={len(blob)}", flush=True)
print(adb("reboot"))
