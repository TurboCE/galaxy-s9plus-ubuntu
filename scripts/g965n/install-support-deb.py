#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Adopt the reviewed runtime settings on an existing backed-up G965N."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile

PACKAGE = "g965n-support"
LIB = "/usr/lib/g965n-support/"
GUARD = "/usr/local/lib/g965n-led-trial/led-control.py"
LEGACY = {
    "charge-guardian": "g965n-adc-trial", "charge-observer": "g965n-adc-trial",
    "set-conservative-limits": "g965n-adc-trial", "power-key": "g965n-display-power",
    "thermal-control": "g965n-thermal-qos", "control": "g965n-interactive-boost",
    "haptic-control": "g965n-haptic-trial", "led-control": "g965n-led-trial",
    "power-leds": "g965n-led-trial",
}


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deb", type=Path)
    parser.add_argument("--confirm-backed-up-g965n", required=True, action="store_true")
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("device_guard", GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.preflight()
    deb = args.deb.resolve()
    name = run("dpkg-deb", "-f", str(deb), "Package", capture_output=True, text=True).stdout.strip()
    if name != PACKAGE:
        raise ValueError(f"Expected {PACKAGE}")

    with tempfile.TemporaryDirectory(prefix=PACKAGE + "-inspect-") as tmp:
        root = Path(tmp)
        run("dpkg-deb", "-x", str(deb), tmp)
        commands = {}
        existing = []
        for script in root.glob(LIB.lstrip("/") + "*/*.py"):
            old = Path("/usr/local/lib") / LEGACY[script.stem] / script.name
            if script.read_bytes() != old.read_bytes():
                raise RuntimeError(f"Installed helper differs from reviewed source: {old}")
            commands["/" + str(script.relative_to(root))] = str(old)
        for file in sorted(root.rglob("*")):
            if not file.is_file():
                continue
            path = Path("/") / file.relative_to(root)
            owner = subprocess.run(["dpkg-query", "-S", str(path)], capture_output=True, text=True)
            if owner.returncode == 0 and not owner.stdout.startswith(PACKAGE + ": "):
                raise RuntimeError(f"Path owned by a different package: {path}")
            if not path.exists():
                if not str(path).startswith(LIB):
                    raise RuntimeError(f"Missing existing device configuration: {path}")
                continue
            expected = file.read_bytes()
            if path.parent == Path("/etc/systemd/system"):
                text = expected.decode()
                for new, old in commands.items():
                    text = text.replace(new, old)
                if path.read_bytes() == text.encode():
                    existing.append(str(path.relative_to("/")))
                    continue
            if expected != path.read_bytes():
                raise RuntimeError(f"Preserve local modification at {path}")
            existing.append(str(path.relative_to("/")))
        backup = Path(tempfile.mkdtemp(prefix=PACKAGE + "-", dir="/var/backups"))
        run("tar", "-cpf", str(backup / "pre-install.tar"), "-C", "/", "--", *existing)
        print(f"Previous configuration archived in {backup}", flush=True)
        run("dpkg", "--force-confnew", "-i", str(deb))
        run("systemctl", "daemon-reload")
        run("dpkg", "-V", PACKAGE)


if __name__ == "__main__":
    main()
