# Current guarded wired charging — native #50

2026-11-23, SM-G965N only. #49 and #50 were installed through BOOT-only
backup/model/readback checks and actually booted. RECOVERY/EFS/CPEFS/RADIO
and user data were preserved. Kernel artifacts, device receipts and logs are
private and are not distributed by this repository.

## Implemented and observed

- Initializer actually reads back CV4.35V, timer0/restart3/prequal0. A guarded
  reduction helper caps input at500mA and charge current at450mA; it never
  increases a negotiated limit. Bootloader900mA inheritance was observed.
- Fifteen-second calibrated battery/USB/charger ADC and IC/control recorder;
  root-only rotated logs, owned audit watches, service startup after real first
  sample. Initial voltage qualification waits bounded stable samples without
  lowering the voltage threshold.
- Guardian uses thermal hysteresis, conservative hot-swelling stop41C/recover39C,
  cold-swelling stop5C/recover10C, general50/45C and0/5C battery gates, USB80/75C,
  stale-data inhibition, configuration/fault latches and runtime safety counters.
  This is deliberately stricter than stock adaptive voltage/current management.
- #50 `charge_control_state` returns generation/requested/policy-blocked/actual.
  Root-only `charge_policy_request` takes expected-generation and allow0/1.
  Comparison, manual intent and CHG readback use the same mutex. Policy recovery
  cannot overwrite a concurrent manual inhibit. Manual auto cannot bypass a
  protection block. These cases were checked on the handset, including stale
  generation rejection without a write.
- Actual recorder loss42s disabled charging; fresh data restored it without a
  manual write or generation change. Manual inhibit survived guardian restart.
  Warm boots restored enabled observer/guardian and retained valid limits.
- CLOCK_BOOTTIME includes suspend in freshness/runtime accounting. An owned
  sleep inhibitor exists while external power is online, keeping software
  thermal supervision awake. Physical suspend behavior is not qualified.
- Final warm boot activated a real high-temperature protection pause. This is
  not evidence of continuous net charging; observe calibrated temperatures,
  actual CHG, voltage and net current together. Do not bypass the thermal gate.

## Reproduction and operation

All scripts retain GPL-2.0-only notices; public references are pinned in
REFERENCE.json. No extracted firmware redistribution or CI publishing is added.

`build-kernel-trial.py --help` documents build-only arguments for an isolated
copy of the qualified #48 build output, its source, exact export ABI and this
charger source. Build49 was reproduced byte-identically using its recorded UTC
stamp. Build50 was compiled and installed. This incremental path requires the
qualified base outputs; it is not a clean-room public one-command full build.
`build-boot-trial.py --help` verifies the loader wrapper, Image and battery DTB,
and preserves the remaining BOOT components. Neither script flashes.

Device deployment is separate: use existing model/backup/consent checks and
`scripts/g965n/device.py`; `migrate-services.py` checks exact old/new profiles,
protected backups, current BOOT and qualified module ABI. Keep rollback files.
The flash uploader defaults to uncompressed ADB sync with SHA validation before
any BOOT write. Actual #50 raw upload failure left old BOOT untouched; physical
USB reattachment and sync upload recovered it. Never flash an incomplete stage.

Units are `g965n-charge-observer.service` and `g965n-charge-guardian.service`.
Guardian stop fails closed without changing user intent. Private live state:
`/var/lib/g965n-charge-guardian/state.json`; recorder:
`/var/lib/g965n-charge-observer/samples.jsonl`.
`soak-check.py --confirm-sm-g965n-read-only-soak --seconds 10800 --interval 15`
is guarded and read-only. A transient `g965n-charging-soak-final.service` runs this
bounded observation. Its root-only `latest-soak-path` points to result.json.
Inspect status/faults/conditions: exit0 may mean inconclusive, not passed.

## Still unqualified or incomplete

Complete physical full/recharge cycles, temperature extremes, low-SOC reboot,
physical suspend/resume, unplug/reattach under the new CAS policy, long-term
battery behavior and sustained positive net charging remain qualification work.
Full/recharge thresholds and safety-time logic have host tests, not full-cycle
hardware evidence. Stock adaptive4.15V swelling policy, cable/fast-charge
negotiation and LCD-dependent timing extensions are not implemented. The
500mA input may be insufficient under screen/CPU load. Hardware/config faults
latch; there is no periodic charger reset or unconditional enable loop.

The first fault recurred about2h59m after attachment with timer config0x91 and
no watched control write. Timer-path evidence strengthened, but the exact fault
meaning, why the previous configuration differed, and original CHG0 depletion
cause remain unresolved. Read CAUSES.md and the current G965N handoff.
