# SM-G965N bounded interaction boost

New source/helpers are GPL-2.0-only. No firmware or private logs are included.
This optional input handler supplies standard CPU-frequency QoS hints, rather
than changing clocks/voltages directly. It matches MT touch devices and real
keyboard capabilities, excludes sensor/FF-only inputs, and records no key or
coordinate payloads. Input extends a500ms interval. No events means no polling,
no outstanding performance floor and no CPU governor change.

Targets are the lesser of the native CPU-info maximum and the qualified limits
1499.333MHz (little) /2327MHz (big). Existing policy MAX constraints remain
in force; targets do not latch a transient boot/thermal cap for the whole boot.
A lower-MAX qualification helper verified actual big-policy min/max1794MHz
during boost, idle min1066MHz after expiry, and previous max2327MHz after
removing the test constraint. No thermal limit was raised or disabled. Actual
high-temperature calibration and energy consumption are separate untested items.

## Evidence and limits

On native48, actual virtual-keyboard events raised minima349.916/1066→
1499.333/2327MHz and restored originals on expiry. Two qualified real DSI
24-transition comparisons improved app-grid worst dispatch28.059→19.062ms
and34.768→24.547ms. Per-opening median peak in three controls was
26.215/23.921/22.837ms; two boost runs18.280/21.199ms. Other openings still
have occasional longer frames. This is not a constant60FPS or zero-stutter claim.
Notifications in the analysis are compositor completion notifications, not
measured photons or hardware scanout cadence. Pooled p95 can swing when sample
counts61/62 cross the four-initial-frame threshold; prefer per-opening results.

The initial module's driver_info-only ID entry did not attach on the current
input core (which stops at zero flags); it was fixed to explicit EV_KEY/EV_ABS
match flags. The initial boost-labelled run is not a qualified active-boost
comparison. Production-code tests cover the actual ID table and workers,
expiry/retrigger/stale work, jiffies wrap, partial failures and shutdown.
A separate Shell-main affinity trial worsened grid latency and was restored.
No affinity, forced performance governor, GPU floor or disabled dock is adopted.

Owner considered current performance sufficient. No further tuning was done.
The owner subsequently rebooted: the guarded service auto-started/enabled,
its ownership receipt matched the new boot and original idle minima/governors
were retained. A bounded kernel uinput Shift press/release raised both minima
to1499.333/2327MHz, returned to349.916/1066MHz after expiry and left maxima
unchanged. The temporary input module/session and fallback timer were removed.
The original accepted NEON Mesa profile remains active. The separate tile32
candidate was rolled back because its synthetic gain did not improve actual
animation. Suspend/hotplug, long-term thermals and Android battery parity are
not qualified by these tests.

`neutral-keyboard-check.c` is a separate bounded QA client, not part of runtime
installation. Compile natively with `cc -O2 -Wall -Wextra -Werror`; it advertises
a keyboard but emits only Shift press/release after stdin receives `1`. It
waits at most5s and has a10s process lifetime bound. Root caller must perform
the existing model/BOOT/backup checks, verify/own a matching temporary uinput
module if needed, arm an independent cleanup timer, sample both CPU minima/
maxima and verify idle restoration, then unload only that owned input module.
It never types text or moves the pointer. A compositor-only virtual-keyboard
trial did not validate this kernel handler and is not active-boost evidence.

## Rebuild without installation

Use the qualified kernel source/output with the pinned Module.symvers ABI:

```sh
python3 experiments/interactive-boost/build.py \
  --kernel-source /path/to/qualified/source --kernel-out /path/to/qualified/out \
  --output /path/to/new-module-output
python3 experiments/interactive-boost/test_policy.py
```

`TRIAL.json` pins sources/ABI. Output must be new. Builder never loads a module,
installs a service or flashes. For the optional *lower*-MAX QA helper only, add
`--with-cap-test`. It is excluded from the ordinary build/runtime service,
disabled without an explicit board opt-in, and must be independently unloaded
after the bounded test. Never publish private build receipts or logs.

## Explicit installation and rollback

Installation is separate from building. First run the existing root-private
native48 `haptic-control.py` preflight to verify actual SM-G965N/current BOOT,
qualified ABI and original RECOVERY/EFS/CPEFS/RADIO backup hashes; preserve
previous files and require the operator's existing explicit device consent.
The lifecycle controller reuses this checked guard and deliberately refuses
unqualified kernels rather than bypassing it.

In a new root-owned mode0700 `/usr/local/lib/g965n-interactive-boost`, put only
`control.py`, `g965n-interactive-boost.ko` and the generated single-module
`pins.json`, mode0600. Verify exact reviewed source/module hashes after staging.
Install the provided service mode0644 in `/etc/systemd/system`. First guarded
start should have an independent root timed unload fallback. Observe actual
frequency bounds returning to baseline at idle, not just a successful load.
After qualification, enable `g965n-interactive-boost.service` for future starts.
No bootloader, BOOT image or protected partition write is part of installation.

Manual lifecycle requires the explicit flag:

```sh
sudo python3 /usr/local/lib/g965n-interactive-boost/control.py start \
  --confirm-sm-g965n-backed-up-interactive-trial
sudo python3 /usr/local/lib/g965n-interactive-boost/control.py stop \
  --confirm-sm-g965n-backed-up-interactive-trial
```

Controller verifies root-private paths, module checksum/ABI and current-boot
ownership receipt. Runtime receipt includes a private boot ID and is never
committed. Stop/unload removes only this module's QoS requests; other native
limits/governors remain. Rollback: stop/disable the service, remove only the
owned service/config files if desired, and keep the validated Mesa baseline.
Whole fresh-image installation of every manual service remains unverified.
