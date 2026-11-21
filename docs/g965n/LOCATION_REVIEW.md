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

At the start of this review, the samsung_sipc plugin provided typed status
and bearer operations through the single RIL owner, without cell-info/location
interfaces or an AT serial port. The LTE GetCellInfo/location implementation
added later is described above; an AT port is still absent. Generic MM AT scans therefore cannot establish whether CP
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

## 2026-11-21 — GNSS assistance, callback ABI and remaining work

The host now prepares a private approximate start position for the legacy HAL,
using a recent genuine GNSS cache or an HTTPS network estimate. GeoClue retains
application policy and output selection; this does not manufacture a satellite
fix. See the GNSS README for build, separate guarded installation, cache policy,
provider disclosure and rollback. Cell-only BeaconDB lookup returned HTTP404 in
this observation; permitting IP fallback returned accuracy25000m. Neither result
establishes permanent database coverage or cell-derived coordinate success.

The initial rebuilt client accepted inject_location with0 but crashed before
NMEA delivery. Numeric worker exit245 led to private GDB confirmation of SIGSEGV
in the vendor IPC callback dispatcher. The own-device HAL requests an additional
two-boolean location callback following the96-byte legacy callback prefix;
the previous client supplied only that prefix. Reading beyond it could produce
an invalid callback target when the client stack layout changed. This is not
an invalid position fix or a proven RF/kernel failure. No proprietary code,
trace, disassembly, memory dump or binary is published. The independently
written extension has a compile-time offset assertion and persistent callback
storage. Its handler counts requests without reentering GeoClue, launching
network work on the callback thread, or feeding a GNSS-derived fix back as an
independent network answer.

Negative controls are retained: early no-seed retry was blocked by five known
stale trial artifacts; these were privately preserved only with GNSS owners
stopped, no vendor/HAL process and exclusive GNSS lease. Earlier source/pins
were restored and an ordinary reboot performed. After guarded preservation of
remaining stale known state, the old-source baseline241s delivered2348 NMEA/
1706 TPV, mode1/no fix. A clean retry of the initial candidate again crashed;
the callback extension then survived an actual location request and resumed
NMEA delivery. Final counts and reboot evidence are in VALIDATION/CHANGELOG.
Unknown GPS state must still be preserved, not removed by a blanket cleanup.

The private cache service started automatically after reboot; a671s-old network
record was rejected, a fresh25km estimate was prepared in1.14s, and no mode1/IP
record created the genuine GNSS cache. Real fix cache capture and reuse need a
reception-capable placement. Native Bionic build and21 host tests pass, including
ASan/UBSan tests of the actual C seed parser and the extended callback slot.

Remaining layers:

| Layer | Present | Remaining evidence/implementation |
|---|---|---|
| GeoClue | App permission, existing network/NMEA sources, MM cell gathering | Actual cell-specific DB coordinate result and accuracy |
| Host assistance | UTC/NTP, LTO/XTRA, approximate start seed, private last-fix cache | Actual new GNSS fix capture/reuse, offline/expired-cache field tests, bounded-latency tuning |
| Vendor HAL | Start, inject_time/inject_location/XTRA, explicit own-device location-request callback | Network-only independent reply now exercised; qualified AGPS/AGPS_RIL lifecycle remains |
| SUPL transport | Vendor extension presence only | Callback/network lifecycle, compatible server/TLS, least-privilege transport across current network isolation |
| Hardware/RF | Historical genuine fix retained; current checksum-valid NMEA | Open-sky cold/warm TTFF A/B, movement and accuracy, suspend/recovery |

Do not globally remove vendor network isolation, substitute an IP estimate for
GNSS, or change the kernel without identifying a failure at that layer. The then-current environment-only explanation was later withdrawn after the
owner confirmed an Android satellite fix at the same place. See the comparison
below; Android-equivalent first-fix performance remains unqualified.

Corrected-HAL final hardware evidence:180s1688 NMEA/1225 TPV, request callback1,
no exception in that instance. Clean shutdown left no known trial artifacts.
Ordinary warm reboot preserved own HAL/pins and auto-started sensor/socket/
GPSD/cache units;91s687 NMEA/498 TPV, request callback1, GNSS exceptions0 in
that new boot. Start/standalone/UTC/position/XTRA0, XTRA124383bytes. Mode1 with
zero satellites throughout; no new fix/TTFF claim. No private identifiers,
coordinates or firmware artifacts are needed to reproduce these public checks.


## Same-place comparison supersedes environment-only interpretation

2026-11-21 owner clarification: another Android GPS diagnostic got an actual
satellite fix here, not just an IP/map location. That comparison is owner-
reported, not an independently captured side-by-side RF log. S9+300s2996 NMEA/
2177 TPV remained0sat/mode1. Filtered diagnostic180s1677/1217 likewise no fix.
Existing receiver transport/callbacks are alive; the RF/assistance path remains
under investigation and must not be labelled healthy from return0.

Request-driven network-only position reply was exercised (initial+requested
inject0),301s3018 NMEA/2193 TPV still no fix. A UTC/XTRA response candidate observed request counters0/0 and181s1699/1233,
without exercising those paths. A first-NMEA one-shot aid retry returned0 with
one XTRA init, but181s1698/1232 and receiver metadata did not improve. Both
additional candidates were removed; network-only location reply was retained.

Public receiver-status.py reproduces privacy-preserving PGLOR aggregates while
an authorized location client holds the receiver. Own version9 STA common
prefix matched; tPeF, ephemeris0 and field5=4294.967 were stable. Interpreting
these against the linked chipset-supplier version10 reference suggests time/
ephemeris aid not usable. This is an inference, not a validated Samsung field
specification or proof of the root cause. Do not use invalid NMEA time as a
measured UTC clock drift. Runtime logging was restored off; private vendor
inspection/receipts remain private. No RF register or kernel change was made.
USB was still configured in recorded tests; disconnected comparison pending.


The subsequent supplied Android screenshot directly shows4 signals/2 in use,
strength21–27 and No Fix. It supports actual RF signal reception at the site,
not a completed fix in that frame; the earlier fix is owner-reported. USB cannot
be disconnected now per owner, so that RF control is unavailable. No current
root cause is confirmed. A metadata-ptrace attempt was inconclusive and left
five known trial artifacts; verified-idle preservation restored normal receiver
startup. Handshake-only diagnostic failures are excluded from RF evidence.
