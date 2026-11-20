# Optional sensor applications on native Ubuntu

These are optional frontends, separate from the kernel/SSP transport. They do
not create a sensor backend, start lhd, load a module, apply calibration or
rotate the screen. No sensor value is synthesized.

On the owner's native Ubuntu24.04 system, install from its configured Ubuntu
package repositories:

```sh
sudo apt-get install --no-install-recommends \
  iio-sensor-proxy lm-sensors psensor qtsensors5-examples \
  qml-module-qtsensors qml-module-qtquick2 qml-module-qtquick-window2 \
  qml-module-qtquick-controls qml-module-qtquick-layouts qtwayland5 qmlscene \
  python3-gi gir1.2-gtk-4.0
sudo install -d /usr/local/share/g965n-sensor-apps
sudo install -m644 compass.py compass-feed.py /usr/local/share/g965n-sensor-apps/
sudo install -m644 g965n-*.desktop /usr/local/share/applications/
sudo install -m644 g965n-compass@.service /etc/systemd/system/
sed "s/@DESKTOP_USER@/$(id -un)/" g965n-compass.socket.in |
  sudo tee /etc/systemd/system/g965n-compass.socket >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now g965n-compass.socket
sudo update-desktop-database /usr/local/share/applications
```

Run those copy commands from this directory on the handset. The launcher paths
target Ubuntu24.04 arm64 Qt5 package locations. No build script runs this recipe
or writes a device automatically. Packages retain their original licensing and
notices in `/usr/share/doc/`. The locally written Compass frontend and launchers are
GPL-2.0-only; they contain no upstream application source or artwork.

- **Sensor Explorer** is Ubuntu's Qt sensor explorer example.
- **Tilt, Light and Proximity** is Ubuntu's QtSensors demonstration.
- **Psensor** is the repository's hardware-monitor frontend. It requires hwmon
  data; it does not read the proprietary SSP transport directly.
- **Compass** is a local GTK 4 frontend. Its on-demand relay claims magnetic
  heading through the stock Sensor Proxy using the existing GeoClue account.
  Only the selected desktop user can open the private socket. The application
  clears the display while readings are unavailable or the relay disconnects.
  Directions are magnetic and labelled experimental until calibration.

Qt launchers use per-app software rendering without changing the desktop's GPU
configuration. These programs run as the ordinary desktop user. Their source
installation preserves normal desktop/package configurations.

## Initial native#25 checkpoint (superseded below)

On native#25, package installation and desktop-entry validation passed. Compass,
Sensor Explorer and the sensor demonstration remained active in the real
Wayland user session. This is application-launch evidence only. IIO has no
sensor devices; iio-sensor-proxy starts and exits normally without devices,
so DBus property queries can lose their recipient. This is not a proxy crash.
`lm-sensors` finds no hwmon sensors, so Psensor has no newly qualified readings.
Do not run bus-probing discovery to fabricate support.

At that checkpoint, qualified raw sensor-hub responses were not a standard
Ubuntu sensor backend. GNOME orientation/brightness, Qt compass data and
hardware-monitor integration had not yet been implemented. The frontend's waiting state is
intentional. GNOME rotation settings and existing screen-only power policy are
not changed by this installation. Personal Tailscale/ChatGPT installations are
not included.


Native#27 follow-up: the real IIO acceleration/illuminance bridge now supplies
stock SensorProxy. GNOME normal/photo-landscape rotation and touch, including
reboot persistence, are owner-confirmed. An ordinary-user Qt LightSensor read
actual272/271/270lux; the initial Qt cache0 was not counted as a real sample.
Light/tilt sensor consumers can now use this standard backend. Compass still
requires real qualified heading support and stays waiting; hwmon/Psensor and
brightness dimming are not implemented by the acceleration/ALS bridge.

## Native #47 Qt 5 hardware backend

This optional plug-in connects `QTiltSensor`, `QProximitySensor`,
`QGyroscope`, `QPressureSensor` and `QCompass` to the G965N sensors. It
uses the installed IIO nodes and, for compass, the private socket from
the setup above. Keep the socket enabled for the desktop user. Light
and orientation continue to use the distribution's Qt plug-ins.

Build on Ubuntu 24.04 arm64 from this directory:

```sh
sudo apt-get install --no-install-recommends qtbase5-dev libqt5sensors5-dev
source_dir="$PWD/qt-backend"
build_dir=$(mktemp -d)
(
  cd "$build_dir"
  qmake -qt=5 "$source_dir/g965n-sensors.pro"
  make -j2
)
```

After verifying the G965N model, recovery backup and consent for device
writes, install the plug-in and default settings on the handset:

```sh
plugin_dir=$(qmake -qt=5 -query QT_INSTALL_PLUGINS)
sudo install -D -m644 "$build_dir/libqtsensors_g965n.so" \
  "$plugin_dir/sensors/libqtsensors_g965n.so"
# If this file already exists, merge the five entries under [Default]
# rather than overwriting it. The example command is for a fresh setup.
if [ ! -e /etc/xdg/QtProject/Sensors.conf ]; then
  sudo install -D -m644 "$source_dir/Sensors.conf" /etc/xdg/QtProject/Sensors.conf
fi
```

Reopen Qt apps after installation. **Tilt, Light and Proximity** shows
angles and Near/Far after pressing **Start** for each sensor. In
**Sensor Explorer**, select the `g965n.*` row, press **Start** and scroll
to the bottom of **Properties**. The compass takes a few seconds to
show its first reading. The example's **Running** column may stay
`false` even while the timestamp and values update. The Qt backends are `g965n.tilt`, `g965n.proximity`, `g965n.gyroscope`,
`g965n.pressure` and `g965n.compass`.

The plug-in applies the kernel acceleration mount matrix for Qt tilt,
compares proximity to the IIO near threshold, and converts pressure to
Pa and die temperature to °C. The gyroscope uses the stock G965N Android
HAL conversion for the same signed 32-bit SSP stream, 0.035°/s per 1000
counts, retaining the stock axis order. The IIO readers poll at 5 Hz.
Compass headings are magnetic. Qt calibration confidence is reported
as unknown (0) because the existing relay carries only azimuth.

The backend follows the [Qt 5 sensor plug-in API][qt-plugin] and the
standard [Qt tilt axis conventions][qt-tilt]. This repository distributes
its own source and configuration under GPL-2.0-only.

[qt-plugin]: https://github.com/qt/qtsensors/blob/5.15/src/sensors/qsensorplugin.h
[qt-tilt]: https://github.com/qt/qtsensors/blob/5.15/src/sensors/qtiltsensor.cpp


Native #48 follow-up adds `QAccelerometer=g965n.accelerometer` to
the Qt 5 default settings. The backend reads the actual acceleration
scale and mount matrix and returns X/Y/Z in m/s². The standard Qt
`generic.rotation` and `generic.tilt` backends can also consume this
acceleration source. The generic rotation backend derives pitch and
roll from gravity and does not supply a measured compass yaw.
Rebuild and install the same plug-in, merge the accelerometer entry,
and reopen Qt applications. The actual Sensor Explorer displayed
live three-axis acceleration and generic rotation on #48.
