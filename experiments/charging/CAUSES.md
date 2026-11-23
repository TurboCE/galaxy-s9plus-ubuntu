# Charging incident: evidence and candidates

This is an investigation, not a concluded root cause. No raw device logs,
private identifiers, receipts, stock firmware or credentials belong here.
Public references are pinned by `REFERENCE.json`. Native source is
`src/soc/max77705_charger.c` and its qualified kernel header.

| Candidate | Evidence / comparison | What would discriminate it |
|---|---|---|
| Requested inhibition, cleanup or later CHG-bit loss | Initial depleted battery had CHG=0. Native property setter and devres cleanup can disable it. Later fault had CHG=1, so that later occurrence was not simple inhibition. | Audit watched control writes and result/process; candidate kernel logs request/result/readback and cleanup caller. A 15-second readback alone cannot capture every transient or identify its writer. |
| Initialization not taking effect, or later config change | Live CNFG_01=0x91: fast timer1, restart1, prequalification1. Native init intends 0/3/0. CNFG_09 bit7 also differs from intended initialization. Public Samsung source uses bounded unlock/readback with 20ms waits; native only writes unlock once without confirming it before configuration. | Capture config at probe and throughout operation; verify unlock and each setting in a guarded future kernel. Current mismatch alone cannot distinguish an ignored initial write from later reset/another writer. |
| Latched charging fault or incomplete input-attach recovery | CHG_DTLS6/BAT_DTLS2 with valid input and CHG1. Physical ten-second USB reattachment changed those to1/4 then1/3 and restored real net charging, without rewriting limits. Native CHGIN work only notifies userspace; Samsung has upper cable/state handling. | Record input/status/config/temperatures across the next failure. Do not assume the exact meaning of state6 from another MAX chip, or reuse Samsung recovery for states8/11 unconditionally. |
| Design rating used as float target | Native DT charge ceiling4.4V and init using design rating disagree with all three owner rev26 stock wired targets4.35V. Live IC remains4.2V, so this is not proof that the live incident was caused by overvoltage. | Candidate DT uses4.35V charge ceiling; initializer uses the charge ceiling bounded by design rating, conservative4.2V fallback, rejects unrepresentable targets and propagates write errors. Needs future kernel/device trial. |
| Missing thermal/full/recharge/safety policy | Native lacks Samsung sec-battery upper policy. Real ADC capture gave roughly38/36/40C while gauge reported22C; Samsung feeds external temperature to the gauge. | Persistent fresh calibrated battery/USB/charger measurements, hysteresis and policy verification. Missing policy is a real port gap, but not yet the proved trigger of this particular failure. |
| Input power insufficient for load | USB500mA / charge450mA; transient battery discharge exists during screen/CPU load even with Charging status. Later net average was positive, and capacity rose8→14%. | Record current averages, input limit, voltage and load; distinguish near-flat battery under load from IC NotCharging fault. Do not raise current beyond the negotiated/qualified supply. |
| Watchdog expiry | Android enables/kicks the hardware watchdog; native disables it. Observed WDTEN0 during both fault and normal charging. | Current evidence does not support an enabled-watchdog expiry as this occurrence's cause; continue recording config rather than enabling a watchdog without its servicing policy. |
| CHGPROT lock by itself | Value0 occurred during both fault and successful charging. | Lock0 is not sufficient evidence of reset or charge failure. Use complete config and chronology. |

The hardware fast/prequalification timers must **not** be blindly disabled to
make the configuration match Android: Android has upper software safety-time
and thermal policy. Fixing unlock could make previously ignored initialization
writes take effect. Review the whole resulting protection policy before a
production BOOT trial. No such change is being forced on the live IC.

## Implemented investigation improvements

- Live diagnostic register parameters now read through the bound owner's
  regmap on every read, rather than repeating module-load snapshots. Only
  non-clearing status and configuration registers are exposed, root read-only.
- Fifteen-second recorder combines actual power-supply control readback,
  twelve IC registers, decoded states, configuration differences, five-sample
  calibrated temperatures, monotonic brackets and filtered kernel messages.
  Reads are not a hardware-atomic snapshot. Missing/error temperatures stay
  errors; historical receipts cannot authorize charging.
- Private fsync'd JSONL rotates four files of4MiB each. Modules are owned by
  the service, unloaded at stop; ADC control/clock observations/IRQ type are
  compared with the start state. No unconditional charge-enable, charger
  reinitialization, configuration rewrite or thermal bypass is performed.
- Current #48 has no KPROBES/FTRACE; userspace audit watches are installed and file/process attribution was
  verified by a no-write open test using explicit audit-log input. Audit does
  not capture kernel-internal writes or every accepted sysfs text value. A candidate kernel logs accepted/requested/actual
  CHG plus setter results and caller, refuses silent write/readback mismatch,
  and propagates the previously ignored initial float-voltage error. These
  production-source improvements require a new qualified kernel/device trial;
  host tests/object compilation are not hardware qualification.
