#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract own-device ABOX firmware read-only. No driver is loaded or device written."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/g965n"))
from device import Device, digest, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    device = Device(args.adb, args.serial)
    device.inspect()
    mount = "/tmp/g965n-audio-firmware"
    require(mount not in device.shell("cat /proc/mounts"), "Export mount already exists")
    require(device.shell("readlink -f /dev/block/platform/11120000.ufs/by-name/VENDOR")
            == "/dev/block/sda19", "Unexpected VENDOR mapping")
    device.shell("mkdir -p " + mount)
    device.shell("mount -t ext4 -o ro,noload /dev/block/sda19 " + mount)
    records = []
    out = ROOT / ".local/audio-firmware"
    try:
        require(not out.exists(), "Audio firmware output already exists")
        out.mkdir(parents=True, mode=0o700)
        for name in ("calliope_sram.bin", "calliope_dram.bin", "calliope_iva.bin"):
            matches = device.shell("find " + mount + " -type f -name " + name).splitlines()
            require(len(matches) == 1, "Expected one stock file: " + name)
            remote = matches[0]
            local = out / name
            device.call("pull", remote, str(local))
            checksum = digest(local)
            require(checksum == device.shell("sha256sum " + remote).split()[0], "Transfer hash mismatch")
            records.append({"name": name, "bytes": local.stat().st_size, "sha256": checksum})
    finally:
        device.shell("umount " + mount)
    stage = ROOT / "device/base/lib/firmware"
    stage.mkdir(parents=True, exist_ok=True)
    for entry in records:
        dest = stage / entry["name"]
        require(not dest.exists(), "Firmware already staged: " + entry["name"])
        dest.write_bytes((out / entry["name"]).read_bytes())
    (out / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    print("Three own-device ABOX firmware files verified; no driver loaded.")


if __name__ == "__main__":
    main()
