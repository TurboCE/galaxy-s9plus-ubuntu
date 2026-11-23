# SM-G965N calibrated battery cooling overlay

GPL-2.0-only. No firmware, modules, raw logs, device identifiers or credentials
are distributed. This is a qualified partial mitigation, not complete Android
thermal/power parity or a repair of the CPU PLL lock indication.

## Confirmed problem and implementation

On actual native #50, the panel was DPMSoff/backlight0 while ChatGPT kept
submitting GPU jobs. A read-only snapshot saw changing fence sequences with
owner ChatGPT; other samples had zero jobs/busy count/PM references. Therefore
persistent GPU residency is not by itself proof of a stuck job or leaked ref.
CPU PLL timeout count grew about39.5/s even under reduced clocks. Extending
standard schedutil cadence20ms→200ms reduced growth to about4.7/s. The driver
still has its documented advisory PLL timeout and raw clock transition risks.
Do not guess a new PLL bit or enable historically unstable idle undervolting.

The previous calibrated charging guardian could stop battery charging but did
not request CPU/GPU cooling. This independent overlay adds standard CPU MAX
frequency QoS and GPU device MAX frequency QoS requests. While battery>=41C
(or until<=39C after a hot reading), caps are A55<=650MHz/M3<=1066MHz/GPU<=260MHz.
Missing/stale/invalid temperature retains cooling. Additional USB>=50C or
charger>=60C retains cooling. It never changes voltage, existing user frequency
requests, charge permission, negotiated current, bootloader or partitions.
The validated original lowest big-cluster voltage and GPU step-voltage modes
remain disabled. CPU schedutil rate cadence is lengthened while cooling;
restore ownership respects later external cadence changes.

The root-private controller verifies actual model/current BOOT/protected
backups, module hash and exact export ABI before loading. A current-boot module
ownership receipt prevents claiming an unrelated loaded module. Stop/failure
retains conservative requests. Restart reuses only its owned instance. Existing
kernel thermal caps and user/profile caps still combine with these requests.
Removing this owned module removes only its own QoS requests.

## Build, deploy and rollback boundaries

Build-only, in the ARM64 cross-build environment with qualified native output:

```sh
python3 experiments/thermal/build.py --kernel-source /qualified/source \
  --kernel-out /qualified/output --output /new/private/output
```

The builder verifies Module.symvers SHA; it neither installs nor flashes.
Public sources include all runtime code used on the device. Private .ko and
pins.json stay outside Git. This is a qualified incremental ABI path, not a
fresh image builder independent of previous kernel outputs.

Installation is separate and requires existing explicit SM-G965N consent and
fresh exact-model/current-BOOT/protected-backup guard. Preserve previous files.
Stage `thermal-control.py`, the built module and its pins.json root-owned0600
in `/usr/local/lib/g965n-thermal-qos`0700; install the supplied service0644.
Run daemon-reload, then enable/start g965n-thermal-qos.service. The controller
performs its own guard again. Check effective CPU max/GPU devfreq max, state
under `/var/lib/g965n-thermal-qos`, fresh calibrated data and actual current.
Reboot autostart is configured; it has not been physically reboot-qualified.
No reboot was attempted with the hot, depleted battery.

For rollback, first perform the same guard, stop/disable the service, verify
its loaded.json boot/module hash owns the loaded instance, then remove only
`g965n_thermal_qos`. Restore schedutil cadence only if current value equals
rate-owned.json's last request; use its original value, preserving later user
changes. Do not change charger protection or force-enable charging to obtain
an endurance pass. Private records remain private.

## Actual evidence and limits

- Guarded120s clock-cap trial, independent240s restore, actual limits readback.
  Mean discharge initially fell roughly748→450-470mA; not a controlled total
  power measurement. Battery remained hot; later discharge varied again.
- Actual module caps, root ownership, service restart and data-driven hot state
  checked on #50. Host4 tests cover hysteresis, stale/future/missing/invalid
  readings, hot spots, cadence restoration and later external requests.
- Initial GPU read-only snapshot module loaded/read/unloaded successfully.
  An owner extension initially failed to compile due to a private opaque lock
  type; the corrected optional module pins exact source-layout hashes and
  retains original Linaro/Collabora attribution for copied private layouts.
  It then read live owner/sequences and was removed. No failed binary loaded.
- `--with-gpu-snapshot` builds that optional read-only QA module; it is NOT part
  of the thermal service. It reads software counters under their owning locks,
  never GPU MMIO or PM/clock control. Use only the exact guarded kernel layout.
- Temperature cooldown, positive long-duration charging, user-perceived hot
  performance and actual reboot still require qualification. The last hot
  samples were about48C with a depleted battery; no normalization claim.

### Additional causal isolation

A20s guarded stop of only the verified ChatGPT GPU helper (independent35s
PID-start checked resume fallback) made GPU runtime actually suspended and
instantaneous battery current approach zero. The helper was resumed. No
automatic app pause is installed: background voice behavior is unqualified.
A1% CPU-budget trial failed to improve runtime sleep and was discarded; quota
and original process cgroup were restored. Thus the public runtime fix is the
calibrated cooling overlay, not an application pause/quota policy. Continued
heat/discharge after app resume remains an open problem.

The verified main ChatGPT app was subsequently closed gracefully for thermal
recovery, leaving app settings/data/autostart unchanged. GPU stayed suspended;
mean battery current approached-3mA and calibrated battery48.6→47.3C. Reopening
can reproduce the workload. This is a temporary recovery action, not a permanent
offscreen rendering fix. Native cpuidle has no registered driver/states; WFI
fallback may still occur. No speculative idle/PSCI changes were attempted.
