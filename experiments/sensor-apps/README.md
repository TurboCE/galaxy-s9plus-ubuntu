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
