"""Write the Ubuntu rootfs image onto this S9+ USERDATA from its running TWRP.

TWRP's adbd accepts `exec-in` but discards the stream, so the image goes over
`adb push` (binary safe) in chunks and is written with dd. Every chunk is
compared against the partition first, which makes the whole run idempotent and
resumable after the PC's adb server drops out mid-transfer.
"""
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

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


SERIAL = None
BYNAME = "/dev/block/platform/11120000.ufs/by-name"
MB = 1 << 20
CHUNK_MB = 128
REMOTE = "/tmp/s9plus-rootfs-chunk.bin"


def adb(*args, timeout=3600, retries=3):
    last = ""
    for attempt in range(retries):
        out = subprocess.run([str(ADB), "-s", SERIAL, *args],
                             capture_output=True, text=True, timeout=timeout)
        if out.returncode == 0:
            return out.stdout.strip()
        last = f"{out.stdout}{out.stderr}".strip()
        # The Windows adb server occasionally stops answering on 127.0.0.1:5037
        # in the middle of a long transfer; restarting it keeps the phone state.
        print(f"  adb {args[0]} failed ({last.splitlines()[-1:]}), restarting server",
              flush=True)
        subprocess.run([str(ADB), "kill-server"], capture_output=True, timeout=60)
        time.sleep(3)
        subprocess.run([str(ADB), "start-server"], capture_output=True, timeout=120)
        time.sleep(2)
        subprocess.run([str(ADB), "-s", SERIAL, "wait-for-recovery"],
                       capture_output=True, timeout=300)
    raise RuntimeError(f"adb {' '.join(args)} failed after {retries} tries:\n{last}")


def main() -> int:
    global SERIAL
    SERIAL = find_serial()
    image = Path(sys.argv[1]).resolve()
    scratch = Path(sys.argv[2]) if len(sys.argv) > 2 else image.parent / "chunk.tmp"
    size = image.stat().st_size
    require(size % MB == 0, "Image size must be a whole number of MiB")
    total_mb = size // MB

    require(adb("get-state") == "recovery", "Samsung is not in TWRP recovery")
    require(adb("shell", "getprop ro.product.device") == "star2lte", "Wrong device")
    require(adb("shell", "id -u") == "0", "Recovery is not root")
    node = adb("shell", f"readlink -f {BYNAME}/USERDATA")
    require(node == "/dev/block/sda25", f"Unexpected USERDATA node: {node}")
    capacity = int(adb("shell", f"blockdev --getsize64 {node}"))
    require(size <= capacity, f"Image {size} does not fit in {capacity}")
    mounts = adb("shell", "cat /proc/mounts")
    require(node not in mounts, f"{node} is mounted:\n{mounts}")
    print(f"USERDATA={node} capacity={capacity} image={size} ({total_mb} MiB)", flush=True)

    chunks = (total_mb + CHUNK_MB - 1) // CHUNK_MB
    written = skipped = 0
    started = time.time()
    with image.open("rb") as fh:
        for index in range(chunks):
            fh.seek(index * CHUNK_MB * MB)
            blob = fh.read(CHUNK_MB * MB)
            want = hashlib.sha256(blob).hexdigest()
            count = (len(blob) + MB - 1) // MB
            have = adb("shell", f"dd if={node} bs=1048576 skip={index * CHUNK_MB} "
                                f"count={count} 2>/dev/null | sha256sum").split()[0]
            if have == want:
                skipped += 1
                print(f"  chunk {index + 1}/{chunks} already correct", flush=True)
                continue
            scratch.write_bytes(blob)
            adb("push", str(scratch), REMOTE)
            adb("shell", f"dd if={REMOTE} of={node} bs=1048576 "
                         f"seek={index * CHUNK_MB} conv=fsync")
            back = adb("shell", f"dd if={node} bs=1048576 skip={index * CHUNK_MB} "
                                f"count={count} 2>/dev/null | sha256sum").split()[0]
            require(back == want, f"chunk {index} readback mismatch")
            written += 1
            print(f"  chunk {index + 1}/{chunks} written and verified "
                  f"({(time.time() - started) / 60:.1f} min elapsed)", flush=True)
    scratch.unlink(missing_ok=True)
    adb("shell", f"rm -f {REMOTE}; sync")
    print(f"chunks written={written} already correct={skipped}", flush=True)

    digest = hashlib.sha256()
    with image.open("rb") as fh:
        for piece in iter(lambda: fh.read(8 << 20), b""):
            digest.update(piece)
    expected = digest.hexdigest()
    print("reading the whole partition back", flush=True)
    actual = adb("shell", f"dd if={node} bs=1048576 count={total_mb} 2>/dev/null "
                          f"| sha256sum").split()[0]
    require(actual == expected, f"USERDATA readback mismatch: {actual} != {expected}")
    print(f"USERDATA_READBACK_VERIFIED sha256={expected} bytes={size}", flush=True)

    # e2fsck exits 1 when it repaired something, which is not a transfer failure.
    check = subprocess.run([str(ADB), "-s", SERIAL, "shell",
                            f'e2fsck -f -y {node}; s9_fsck_status=$?; '
                            'printf "\\nS9_FSCK_EXIT=%d\\n" "$s9_fsck_status"; '
                            'exit "$s9_fsck_status"'],
                           capture_output=True, text=True, timeout=3600)
    print((check.stdout + check.stderr).strip(), flush=True)
    validate_fsck_result(check)
    print(adb("shell", f"blkid {node}"), flush=True)
    return 0


def validate_fsck_result(result):
    # An explicit marker also protects older ADB shells that mask remote exit
    # codes. Never let a subsequent successful blkid hide a failed e2fsck.
    statuses = [line.split("=", 1)[1] for line in result.stdout.splitlines()
                if line.startswith("S9_FSCK_EXIT=")]
    require(len(statuses) == 1 and statuses[0] in ("0", "1")
            and result.returncode in (0, 1),
            "Filesystem check failed or its status is unknown; leave the phone in recovery.")


if __name__ == "__main__":
    sys.exit(main())
