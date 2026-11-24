#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Start the packaged supervisor with the device's guarded sensor profile."""
import os
from pathlib import Path
import re
import sys

from sensor_runtime import trusted_bytes


def main():
    state = Path("/var/lib/g965n-sensors")
    pin = trusted_bytes(state / "profile.sha256", limit=256, private=True).decode("ascii").strip()
    if not re.fullmatch("[a-f0-9]{64}", pin):
        raise RuntimeError("Invalid private sensor profile fingerprint")
    supervisor = Path(__file__).with_name("sensor_runtime.py")
    argv = [sys.executable, str(supervisor), "run", "--profile", str(state / "profile.json"),
            "--profile-sha256", pin, "--model", "SM-G965N",
            "--confirm-backup-verified", "--consent-start-sensors"]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
