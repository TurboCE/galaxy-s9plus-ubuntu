#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Report basic SM-G965N interfaces without collecting identifiers or audio."""
import json
from pathlib import Path
import subprocess

UNITS = (
    "display-manager", "NetworkManager", "ssh", "iio-sensor-proxy", "ModemManager",
    "g965n-audio", "g965n-bluetooth", "g965n-sensors", "g965n-cover",
    "g965n-desktop-lte", "g965n-charge-guardian", "g965n-charge-observer",
    "g965n-thermal-qos", "g965n-power-key", "g965n-interactive-boost",
    "g965n-haptic", "g965n-led", "g965n-power-leds",
)


def query(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=15)


def main():
    reports = {}
    for unit in UNITS:
        reports[unit] = query("systemctl", "is-active", unit).stdout.strip()
    cards = query("alsaucm", "listcards").stdout
    results = {
        "units": reports,
        "package_integrity": all((r.returncode == 0 and not r.stdout.strip()) for r in [
            query("dpkg", "--audit"), query("dpkg", "-V", "g965n-support")]),
        "wifi_connected": any(line.endswith(":wifi:connected") for line in
                              query("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device").stdout.splitlines()),
        "drm_render_nodes": len(list(Path("/dev/dri").glob("renderD*"))),
        "alsa_playback": "zrn" in query("aplay", "-l").stdout.lower(),
        "alsa_capture": "zrn" in query("arecord", "-l").stdout.lower(),
        "alsa_ucm": "Galaxy S9 speakers" in cards,
        "iio_devices": sorted(p.read_text().strip() for p in Path("/sys/bus/iio/devices").glob("iio:device*/name")),
        "backlight": bool(list(Path("/sys/class/backlight").glob("*/actual_brightness"))),
        "nfc_controllers": len(list(Path("/sys/class/nfc").glob("nfc*"))),
        "bluetooth_controllers": len(list(Path("/sys/class/bluetooth").glob("hci*"))),
        "battery": Path("/sys/class/power_supply/max170xx_battery/capacity").read_text().strip(),
        "external_power": Path("/sys/class/power_supply/max77705-charger/online").read_text().strip(),
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
