# Source-qualified input-current trial — SM-G965N native #50

This is a reversible, current-boot qualification path, not a completed safety
certification, validated cold boot or full Android charging implementation.
Original source notices remain in the driver. Register/packet references are
pinned in USBC_REFERENCE.json and REFERENCE.json; no firmware is redistributed.

## Implementation

`src/soc/s9p-max77705-muic.c` now serializes MCU requests/replies with one mutex.
CURRENT_SRCCAP queries the selected fixed source PDO without selecting a new
PDO, changing roles or replacing firmware. The actual handset returned source
PDO1, 5V/3A. This is a selected source ceiling, not measured power consumption
or an independent decode of the operating-current RDO.

The driver exposes standard read-only `g965n-usbc-input` power_supply properties:
ONLINE, USB_TYPE, CURRENT_MAX and VOLTAGE_MAX. `source_status` on its I2C device
provides source/query freshness and diagnostic status. CCI, PD-ready, BC alone,
malformed/truncated replies, non-fixed PDOs and attachment changes do not grant
higher input current. Unknown/error states retain a conservative500mA ceiling.

An optional root-only `input_policy_request` accepts `<generation> 900000`,
`<generation> 1200000` or `<generation> 0` (release). It changes only input-current limit, never CHG,
450mA charge current or4.35V CV. Requests require a fresh selected fixed5V PDO
with adequate source current; only900/1200mA is accepted. Higher-current policy
is not implemented. The kernel checks the source every500ms and renews its PDO
query every2s. A heartbeat extends the input lease by15s. Expiry or invalid
source restores500mA. Module removal releases its owned higher limit.

`input_policy_state` reports generation, owned, requested_uA, last_applied_uA,
and deadline_boottime_ms. Independently read the charger's actual input limit;
this field is an ownership record, not an atomic hardware snapshot. Observed
external changes revoke ownership and stale generations cannot rearm it.
A simultaneous write through the other charger's sysfs interface has not been
proven atomic; do not run competing input controllers. Polling and I2C failures
also prevent a hard real-time fallback guarantee. Firmware/hardware protection
is not replaced by this software lease.

`charge-guardian.py` permits900/1200mA only while the live kernel lease/source remain
qualified; absence/staleness reverts its accepted ceiling to500mA. All charge
intent CAS, temperature, fault, configuration and runtime protections remain.
`input-policy.py` is a bounded trial controller, not installed autostart policy.
It checks calibrated ADC, chip status and the live guardian and renews the lease.
External generation changes or hardware/configuration faults do not automatically
rearm. A protection/source pause relinquishes only the owned lease and may
reacquire only its own release generation after safe conditions return.

Input availability is separate from battery CHG permission. The initial input
trial also stopped at battery40C/all guardian holds; during actual voice this
stranded input at500mA and increased discharge. The corrected input controller
can supply the system through qualified input while CHG remains inhibited for
swelling/full/safety-time holds. It still refuses stale/general thermal/fault
states. Input-only limits are battery0..43C, USB0..45C and charger0..50C, with
conservative recovery41/43/48C. The independent CHG41/39C gate is unchanged.
Actual40.4C/CHGoff/input900mA verified this separation without charging the pack.

## Build and deployment boundary

```sh
python3 experiments/charging/build-muic-source.py \
  --kernel-source /path/to/qualified/source \
  --kernel-out /path/to/qualified/output \
  --output /path/to/new/private/module-output
```

This pins the qualified native export ABI and builds a distinct trial driver
name. It never loads or flashes. Canonical build passed with `KCFLAGS=-Werror`;
its executable text matched the deployed module. The normal image driver-copy
script also includes the parser header. A full clean image/reboot was not tested.

Deployment requires the existing exact-model/current-BOOT/protected-backup
checks, module hash/ABI checks, private ownership receipts and a timed rollback.
The actual trial unbound only the original MUIC driver, bound the trial driver
and retained Wi-Fi control. BOOT and protected partitions were not written.
The original built-in driver can be rebound after releasing any input lease and
removing the owned trial instance. Do not merely load a second command sender
alongside the existing owner. Keep previous guardian/controller files privately.

After separately guarded deployment, a bounded trial is:

```sh
python3 /usr/local/lib/g965n-adc-trial/input-policy.py \
  --confirm-sm-g965n-backed-up-input-trial --input-limit-ua 900000 --seconds 600
```

The current-boot trial is lost on reboot. The updated guardian remains backward
compatible with the original500mA path. Boot-time loading and reboot regression
remain unqualified. A successful module build/hot bind is not a successful boot.

## Hardware evidence and remaining limits

- Selected5V/3A PDO, standard supply exposure and unchanged charge/CV limits read.
- Freeze of the input controller:900mA reverted to500mA without its cleanup;
  expired generation was rejected. External reduction to500mA revoked ownership
  and was not undone by the old controller in the normal sequential test.
- Screen OFF with app retained: approximately+420..460mA, battery38.8C.
- One-minute screen ON idle app: approximately+380..450mA, maximum39.1C.
- Two busy M3 synthetic workers plus screen ON: still net charging but battery
  reached40C in about42s; test stopped. This is not a sustained-load pass.
- Actual voice with the old coupled500mA hold: capture active, approximately
  -562mA average, voltage3.544V at36s triggered observer stop. Later43.5C/3.54V
  required graceful workload closure and cooling. This was a failed real-use
  trial, not mitigated by merely ending the observer. Application/unit cpuset
  inheritance must be checked on actual child processes; unit settings alone
  do not prove it. Personal workload configuration is not distributed.
- Native panel blanking and closing the diagnostic monitor restored cooling
  to38.1C, CHGon and approximately+450mA. Recovery with the app closed is not
  an actual voice endurance pass. Longer qualification follows separately.

Hardware charger WDT is disabled by the existing native driver, whereas the
pinned Samsung source enables and kicks it. A separately guarded current-boot
watchdog trial now has actual expiry and safe-disarm evidence; see
[HARDWARE_WATCHDOG.md](HARDWARE_WATCHDOG.md). This does not qualify a real
whole-kernel/PID1 freeze or reboot. Remaining tests include
charging from depleted cold boot, source unplug/replug, real voice endurance,
full/recharge cycles and vehicle-temperature operation remain unqualified.
