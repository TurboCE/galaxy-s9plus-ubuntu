#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the SM-G965N userspace support package from repository sources."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
PACKAGE = "g965n-support"
LIB = "/usr/lib/g965n-support"
UNITS = {
    "charging": ("charge-guardian", "charge-observer"),
    "display-power": ("power-key",),
    "thermal": ("thermal-qos",),
    "interactive-boost": ("interactive-boost",),
    "pmic": ("haptic", "led", "power-leds"),
}
HELPERS = {
    "charging": ("g965n-adc-trial", ("charge-guardian", "charge-observer", "set-conservative-limits")),
    "display-power": ("g965n-display-power", ("power-key",)),
    "thermal": ("g965n-thermal-qos", ("thermal-control",)),
    "interactive-boost": ("g965n-interactive-boost", ("control",)),
    "pmic": ("g965n-led-trial", ("led-control", "power-leds")),
}
RULES = (
    "display-power/81-g965n-panel-wake.rules",
    "pmic/70-g965n-haptic.rules",
    "pmic/feedback/71-g965n-feedback.rules",
)


def stage(root):
    def copy(source, target, mode=0o644):
        dest = root / target.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / source, dest)
        dest.chmod(mode)
        return dest

    commands = {}
    for group, (local, names) in HELPERS.items():
        for name in names:
            old = f"/usr/local/lib/{local}/{name}.py"
            new = f"{LIB}/{group}/{name}.py"
            copy(f"experiments/{group}/{name}.py", new, 0o600)
            commands[old] = new
    old = "/usr/local/lib/g965n-haptic-trial/haptic-control.py"
    commands[old] = f"{LIB}/pmic/haptic-control.py"
    copy("experiments/pmic/haptic-control.py", commands[old], 0o600)

    for group, names in UNITS.items():
        for name in names:
            unit = f"g965n-{name}.service"
            dest = copy(f"experiments/{group}/{unit}", f"/etc/systemd/system/{unit}")
            data = dest.read_text()
            for old, new in commands.items():
                data = data.replace(old, new)
            dest.write_text(data)
    copy("scripts/g965n/sensor-runtime.py", f"{LIB}/sensors/sensor_runtime.py", 0o600)
    copy("scripts/g965n/start-packaged-sensors.py", f"{LIB}/sensors/start-packaged-sensors.py", 0o600)
    copy("scripts/g965n/units/50-g965n-support.conf",
         "/etc/systemd/system/g965n-sensors.service.d/50-g965n-support.conf")

    for rule in RULES:
        copy(f"experiments/{rule}", f"/etc/udev/rules.d/{Path(rule).name}")

    for config in ("etc/wireplumber/main.lua.d/51-g965n-audio-timing.lua",
                   "etc/systemd/logind.conf.d/10-s9plus.conf",
                   "etc/systemd/sleep.conf.d/10-s9plus.conf",
                   "etc/systemd/system/gdm.service.d/10-wait-for-render-node.conf",
                   "etc/udev/rules.d/70-s9plus.rules"):
        copy(f"device/base/{config}", config)
    ucm = "usr/share/alsa/ucm2"
    for config in ("G965N/G965N.conf", "G965N/HiFi.conf",
                   "conf.d/ZrnAbox/ZrnAbox.conf", "conf.d/snd-zrn-abox/snd-zrn-abox.conf"):
        copy(f"device/base/{ucm}/{config}", f"{ucm}/{config}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New .deb path")
    parser.add_argument("--version", default="1.1.0")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.suffix != ".deb":
        parser.error("Provide a new .deb path")
    subprocess.run(["dpkg", "--validate-version", args.version], check=True)
    with tempfile.TemporaryDirectory(prefix=PACKAGE + "-") as work:
        root = Path(work) / "package"
        control = root / "DEBIAN"
        control.mkdir(parents=True)
        stage(root)
        (control / "control").write_text(
            f"Package: {PACKAGE}\nVersion: {args.version}\nArchitecture: arm64\n"
            "Maintainer: Galaxy S9 Ubuntu port contributors\n"
            "Section: admin\nPriority: optional\nDepends: python3, systemd, udev\n"
            "Description: Samsung Galaxy S9+ SM-G965N userspace support\n"
            " Board-specific service entry points, udev rules and ALSA profiles.\n"
            " Requires the separately deployed G965N BOOT and guarded driver artifacts.\n",
        )
        configs = sorted("/" + str(p.relative_to(root)) for p in (root / "etc").rglob("*") if p.is_file())
        (control / "conffiles").write_text("\n".join(configs) + "\n")
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(output)],
                       env={**os.environ, "SOURCE_DATE_EPOCH": "0"}, check=True)


if __name__ == "__main__":
    main()
