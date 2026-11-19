# Remaining native36 kernel warnings

Evidence date2026-11-19, one experimental SM-G965N rev26. Both observed native36
initial/warm boots have zero error-priority lines and zero failed system units.
This does not establish an error-free kernel or all hardware functions working.
The complete warning stream is preserved privately rather than suppressed.

| Warning class | Current evidence and limit |
|---|---|
| CPU feature sanity/unsupported variation |52 register-variation messages across heterogeneous cores in the latest warm boot. Common instruction/capability and cache semantics need SoC-specific review; no feature ID or warning mask was altered to hide them. Basic8-core/native-build proof is narrower than architecture/endurance qualification. |
| MAX77705 RGB/haptic missing OF node |One warning each. These functions remain unconfigured/unqualified; prototype source tests do not establish safe physical clock/current/supply behavior. |
| Alternate GPT |Read-only audit finds sda primary header and entries CRC valid, alternate header invalid at its expected in-range finalLBA; sdd primary/alternate headers valid. Logical sectors4096bytes. No partition-table writes. A reviewed metadata repair requires dedicated table backup/layout review and is separate from a driver fix. |
| Hub MCU_RESP reset uncertainty |One warning; real firmware readiness, pinned identity and accel/ALS feeds subsequently pass. A successful feed does not prove a hard reset or suspend/resume parity. |
| Bluetooth advertised transmit-power command unsupported |One warning from controller capability probing. Discovery/startup evidence does not establish pairing/audio or vendor-command parity. |
| Experimental module taint |Expected out-of-tree driver notice; not evidence of full functional correctness. |

Historical SSP zero-ACK retries remain in earlier boot records. Checked mode
commits only positively acknowledged bytes and latches exhausted/invalid streams;
latest observed36boots have no error-priority retry line and faultN. This does
not prove all transport modes or long-run end-to-end integrity. No kernel log
severity/filter was changed merely to achieve a clean error-priority snapshot.

Wi-Fi Direct IF_ADD timeout is separately repaired by a real firmware-backed
control context, with native boot/reboot, lifecycle/scans, existing STA HTTPS
and owner-assisted bidirectional discovery evidence in WIFI_DIAGNOSTICS.md.
A later native36 Fold7 group and source-bound 1MiB transfer in both directions
passed with matching hashes and preserved STA HTTPS204. The same boot now has
four error-priority lines: one SSP initial zero-byte write retry, two failed
action-frame retry batches while awaiting pairing, and one chanspec query -52.
Connection and cleanup eventually succeeded; these errors are not suppressed
or considered fixed by the transfer pass. No full Lineage parity is claimed.
