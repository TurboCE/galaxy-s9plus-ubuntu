# MAX77705 hardware watchdog — guarded native #50 trial

GPL-2.0-only. Samsung register facts and notices are attributed in
`g965n-charge-wdt.c` and pinned in REFERENCE.json. No binary/firmware or private
device/charging records are distributed. This is partial protection evidence,
not battery certification or full Android charging parity.

The native charger disables its hardware watchdog. The experiment accesses the
existing driver's regmap, serializes its own requests and prevents that device
from unbinding while a regmap operation runs. Native header **logical indices**
must be used: regmap adds the hardware base address itself. An earlier absolute
address candidate failed initialization reads; it did not arm or change settings.

The module refuses unsupported models/driver/ABI and a pre-enabled, unowned
watchdog. `feed=1` arms only while actual CHG is off, then force-writes the kick
command; a cached unchanged value must never suppress a watchdog kick. It
changes neither user CHG intent, charge current, CV, source contract nor firmware.
Healthy native supervision must permit CHG separately through its generation
checked policy. An armed self-reference prevents normal module unload.

Expiry is sticky within an owned instance. After a captured expiry, feeding is
refused even if CHG-off changes the hardware status code. `feed=0` refuses while
actual CHG is on: disabling WDT can clear its fault and resume a retained CHG
request. First stop/inhibit through the actual charger policy and verify CHG0;
only then disarm. Never force-remove an armed module or blindly reset faults.
Ordinary charger sysfs writers are not made atomic with this auxiliary module;
competing writers and I2C/kernel failures remain limitations.

`charge-guardian.py --hardware-watchdog` requires a separately created private
current-boot ownership receipt and an already guarded loaded module. It first
inhibits CHG, arms before allowing charging, checks state/readback, and feeds
every successful5s iteration. Thermal/full/safety holds feed only after CHG is
actually inhibited. Stale/invalid data, configuration or hardware faults never
extend the timer. Owned expiry/lost ownership adds a persistent guardian fault.
Stopping the supervisor inhibits CHG; it does not silently disarm/reset WDT.
The existing systemd45s guardian watchdog remains a separate recovery layer.

## Build and current deployment boundary

```sh
python3 experiments/charging/build-wdt.py \
  --kernel-source /path/to/qualified/source \
  --kernel-out /path/to/qualified/output \
  --output /path/to/new/private/module-output
```

The builder checks exact native headers/export ABI, compiles with `-Werror` and
never loads or flashes. Its executable text matched the live trial module.
Deployment separately requires exact model/current BOOT/protected-backup checks,
matching module hash/vermagic, private previous files and a current-boot receipt.
The receipt is root-owned0600 `wdt-trial.json` in the private guardian directory,
containing the actual boot and separately verified module SHA. It is not a
general authorization to claim arbitrary loaded modules.

The tested guardian override is **runtime-only** under `/run/systemd/system`.
There is no watchdog module boot installer. Reboot removes the trial override;
normal #50 supervision still works, but its original native watchdog state and
500mA input behavior remain. Do not claim boot or cold-start qualification.

## Actual evidence

- Intentional loss of kicks produced charger fault11 at about80s. The CHGEN
  request bit remained1: internal fault is the shutdown evidence, not a claim
  that hardware cleared that request bit. The first gauge current at expiry
  was still positive and is not an instantaneous current-cutoff measurement.
- A previous disarm with CHGEN1 cleared the fault and charging resumed. That
  unsafe cleanup path was rejected and replaced by inhibit-before-disarm.
- Corrected trial: expiry79.933s; disarm while CHGEN1 and ordinary module removal
  were refused; feed after expiry was refused. After actual CHG0 then disarm,
  WDT0/CHG0/status8 remained after3s. Normal guardian policy was preserved.
- Controlled fault recovery reloaded only this disarmed, owned module after
  checking the exact experiment result, fresh measurements and no unknown
  latched fault. No generic automatic fault-reset loop is installed.
- Integrated guardian arm/feed/charging read back on the handset;95s/48
  observations had no expiry. Ordinary reboot and longer endurance remain
  separate entries in the validation matrix.

The original spontaneous fault6 and historical CHG-disable/configuration origin
remain unproved. Controlled watchdog fault11 does not explain that first event.
Real whole-kernel hangs, physical temperature extremes, source reattachment,
full/recharge, depleted boot and sustained voice operation remain unqualified.
