# SM-G965N location source review

## Verified outcome — native48, 2026-11-20

Two guarded normal reboots loaded the read-only diagnostic and then the new
SIPC plugin, without a kernel/image/firmware change. CP0811 returned20 LTE
records before EPS registration completed. ModemManager GetCellInfo returned20
LTE entries/1 serving; two separate rounds exactly matched the private SIPC
operator/TAC/CI/PCI/serving fields. The other19 are modem-reported nonserving
entries, not an independently verified fresh RF scan. Cell-type was LTE.
Location Setup/GetLocation returned a nonempty3gpp source. Disable cleared it;
re-enable restored it. Raw cell IDs remain private and are never journalled.

The plugin now requests validated LTE identities via the existing root-only
broker, with a15s cache limit. It updates location from only a CP-marked serving
record, clears stale/disabled location, and polls every10s only while gathering
is enabled. Unknown radio families and unqualified signal-unit fields are not
invented. EPS status was searching/2 during verification; registration-success
comparison remains pending. A camped serving cell is not proof of attachment.

Window tests while a desktop-authorized client held the receiver:181s yielded
1,699 NMEA/1,233 TPV, and180s yielded1,687 NMEA/1,225 TPV. Both mode1, no fix.
The latter raw sentence types included GGA/GSA/RMC/proprietary LOR but no GSV;
HAL satellite/fix counters also remained0. This localizes the observed absence
before GeoClue's position decoding, without proving an RF/hardware defect.
The owner could not provide open sky and explicitly confirmed this placement
cannot receive satellites. Treat the result as reception-environment-limited;
favorable-location GPS fix remains unverified. Earlier hardware fix evidence is preserved, not superseded by a
claim that the receiver can never fix. UTC/XTRA acceptance is not RF lock. Final45s observation received207 NMEA/148
TPV in mode1; standalone/start/UTC/XTRA-init results were all0. No GPS driver
repair was justified or applied from this placement.

BeaconDB hostname api.beacondb.net and submit-data=false were preserved.
No network-provider or privacy policy was changed by this work. Its IP-derived
estimate is independent of GNSS. Source/host tests and a full174-target ARM64
MM build passed; the final plugin recompile had no warning. One intermediate
recompile lacked its original cross-file mount and was rerun with that mount.

## Boundaries

Cell identity, raw modem traces/NMEA, coordinates and own-device vendor binaries
remain private. GPS tests use Wi-Fi. Camera/fingerprint and document-portal WIP
are excluded. A network/IP estimate is not a GNSS fix or cell measurement.

## Cell path

The samsung_sipc plugin provides typed status and bearer operations through the
single RIL owner. It has no cell-info/location interface implementation and
no AT serial port. Generic MM AT scans therefore cannot establish whether CP
can measure cells. Do not create a fake AT device or infer no RF detection.

The existing registration parser deliberately excluded LAC/CI. Actual SIPC0805
registration events have19-byte bodies on this handset. Own-stock NetRegState
reads LAC/CI at packet offsets11/13 (body4/6), matching the core fields in the
GPL libsamsung-ipc net.h registration layout. The diagnostic `cell-status` reports only
whether these fields are nonplaceholder, never their values, to distinguish
redaction from absence. This alone is not a usable serving location: serving
PLMN, registration state, data freshness and sentinel semantics also matter.

Own-stock IpcTxNetCellInfoList sends bodyless0811 GET. New explicit
`cell-list-request` routes that read through the existing owner, avoiding channel
races. `cell-status` retains a validated count envelope or query rejection.
Own-stock receive logic has four count groups with20/20/31/19-byte strides and
an optional matching fifth51-byte group. Unknown/truncated envelopes are errors,
not empty successful lists. Counts do not prove serving/neighbor classification.
No raw records, disassembly or proprietary binary is included in this recipe.

CEREG diagnostic now records whether bounded hexadecimal TAC/CI fields were
present, still redacting values. No extended reporting mode, network selection,
radio reset command, kernel or firmware change is introduced by the decoder.
Host tests cover placeholders, truncated lists, count/length consistency and
privacy, alongside existing radio/PDP checks. Deployment separately checks model,
BOOT/backups and changes exact RIL/config/service pins with a private rollback.

The CP-record gate was passed for the LTE subset above; GetCellInfo and the
location interface are implemented. Additional radio families still need actual
records and independent layout qualification. Do not fabricate a registered serving cell from
SIM home PLMN or expose unsupported neighbor types. Validate unregistered and
registered observations separately; if registration is unavailable, keep the
registered half pending. Generic --3gpp-scan is an operator scan, not a neighbor
cell measurement.

Reference for core registration fields: GPL-2.0-or-later libsamsung-ipc
[net.h at pinned commit](https://github.com/LineageOS/android_external_libsamsung-ipc/blob/6d244414f7c66b0d0f93ef4b34f5276023408016/include/net.h).
The newer0811 envelope is own-device protocol research, not that old header's
API guarantee. New independent helpers remain GPL-2.0-only.

## GNSS path and reproducible observation

`gpsd-summary.py --seconds 180`, run as the authorized desktop user, holds its
own GeoClue request while watching loopback GPSD2948. A GPSD observer alone does
not activate the on-demand receiver. Report message counts, GSV visible count,
maximum C/N0 and fix mode only; never coordinates or satellite IDs. Mode1 is no
fix, mode2/3 is a fix. Keep the receiver/GeoClue request alive for the whole test.
Checksum-valid NMEA delivery and UTC/XTRA injection do not demonstrate RF lock.

Use a broad open-sky placement on Wi-Fi when possible. The owner currently can
provide a window only; do not relabel that as an outdoor control. Compare HAL
satellite/fix counters with NMEA GSV/GSA and GPSD to locate loss before changing
receiver configuration or kernel. Keep historical successful fixes alongside
new failures, and mark outdoor comparison unverified if unavailable.

Preserve configured network-location provider and submit-data=false. A25km IP
estimate is independent of GNSS and does not demonstrate valid cellular data.
