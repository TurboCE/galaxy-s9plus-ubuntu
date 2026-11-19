# SM-G965N hardware validation

Evidence updated: 2026-11-20. One Korean SM-G965N rev26 / 256GB,
original firmware G965NKSU5FVA2. Target is parity with the hardware features
supported by the reference LineageOS build, not just desktop startup.
A build or a driver node is not sufficient evidence of a working function.

Owner-confirmed baseline: audio output, microphone, Wi-Fi, Wi-Fi Direct and
Bluetooth have already worked in actual use, as clarified by the owner. Retain
that evidence separately from historical experiment failures and untested
specific profiles/endurance cases. Recent post-modem cleanup checks inspect
service return and basic connectivity; they do not mean those five functions
had never been verified. This clarification changes no approved work scope or
priority; LTE remains the current focus.

| Feature | Actual evidence | State |
|---|---|---|
| TWRP and recovery | 3.3.1-0 root; nine partitions backed up with device hash checks | Verified |
| Source build and installation | Own G965N firmware; rootfs and BOOT readback hashes passed | First installation verified |
| CPU / RAM | 8 online cores; 5523MiB usable RAM | Verified |
| Native builds / Git | Git clone+pull; real fixdep C source compiled on each CPU, 8 identical object hashes | Short test passed |
| Storage | USERDATA mounted as root and grew to 230GiB | Verified |
| Display / touch | Owner confirmed desktop/touch; 2x desktop scaling persisted at 720x1480 logical pixels | #30 scoped post-power controller reset passed initial native boot and3warmboots;#31/#32 initial boots also passed with first input registration~5.29s and no initial-110; previous delay-only#29 failed; basic interaction previously owner verified; apps wider than 720 minimum still need adaptations |
| GPU | #21 isolated patched Mesa with nocrc,noafbc: exact128x128 readback100, full33 positive scene rows, fullscreen1440x2960 U-tiled presentation and FIFO61/61/61fps;0 new matching GPU faults/timeouts; actual private-library maps verified | Bounded isolated rendering passed.100us IRQ generation-check rejections +1 with40ms completion wait failures0; frame impact unconfirmed. Native43 coherent per-user Mesa now accepted after full33/readback100/fullscreen FIFO60/61/61,0newGPUfault and freshSSH/DSO/environment evidence; persisted distinct warm boot. Visible Firefox120-frame/31,457,280-byte checks pass with0mismatch/context loss; temporary prefs audit empty, headed/focused/visible. Post-warm FIFO11/11/11 is a retained FAIL; later single scene60 without policy changes. Intermittent animation/presentation, video/endurance and CRC/AFBC-enabled operation remain unqualified |
| Wi-Fi | Native#25 HTTPS204 explicitly bound to Wi-Fi after policy correction; earlier NTP/connection observations | Data path verified; long reconnect tests pending |
| Wi-Fi Direct / roaming | #24 policy5 and rawBADOPTION(-3) identified; #25 scoped product-profile preservation removes legacy-trigger initialization failure | Initialization correction hardware verified; Native35 passed2create/start/scan/stop/delete cycles with primary identity and HTTPS204 preserved. Native36 explicit build opt-in auto-creates P2P device across initial+warm boot without IF_ADD timeout; native NetworkManager found Fold7 and owner confirmed reverse discovery. Native36 Fold7 group negotiation + dedicated IPv4 succeeded; source-bound 1MiB transfers in both directions matched SHA256; primary HTTPS204 and cleanup passed. Native37 passed two groups with bidirectional 1MiB hash-checked transfer, active channel query and cleanup with primary HTTPS204 preserved; teardown chanspec errors0, action-frame retry batch1 remains. Endurance and real AP handover remain unqualified |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| CPU cache topology | Native42 one-shot architectural reads on all8 cores, selectors restored/probe unloaded; explicit measured DT cache graph candidate compiles and passes positive/negative artifact checks | Native43 all8 CPU sysfs geometry/ownership matches measured graph; cache warning absent in full early ring (error0/warning63), services/feeds/HTTPS pass. Distinct normal warm boot repeats all8 geometry/graph, services/feeds/HTTPS and error0/warning63. Scheduler debug-domain files unavailable. No CPU-feature masking or performance claim |
| System services | Native44 distinct cleanup boot: three driver services active, accel/ALS readable, Wi-Fi-bound HTTPS204, failed units0, full ring errors0/warnings63/CallTrace0/SError0; earlier SSP retries remain intermittent. Latest43 LTE cold-data cleanup distinct boot: full early ring error1 (initial SSP zero-write retry)/warning63, CallTrace0/SError0, failedunits0; three driver services active, varying accel/readable ALS. Latest43 RFS-trial cleanup boot full ring error0/warning63 (header present), varying accel/three active services/HTTPS204/failedunits0. Loaded RFS-trial ring406errors/88warnings lacks boot header;91IPC-not-open events after RIL closes remain unresolved. Previous43 modem-cleanup reboot retains two initial SSP zero-ACK retry lines; strictY/faultN, fresh accel, three services/HTTPS204/failedunits0. Loaded-modem observation has136error-priority lines/67warnings including ECT/QoS gaps and vendor diagnostics, not a clean-kernel claim. #43 initial+distinct normal warm boots: corrected measured cache hierarchy persists on8CPUs, ring error0/warning63, audio counters0, fresh accel, three services/HTTPS204 and failed units0. #42 initial native boot with matching guarded drivers passed, full ring error0/warning64; isolated legacy DSM state restore emits0 write ioctls (native41:1), state file unchanged; bounded silent playback/exact1s capture passes with0 retries/stalls/codec errors, Wi-Fi HTTPS204 and failed units0. Distinct normal warm boot also passed matching services, zero audio retry/stall/codec counters, full ring error0/warning64, HTTPS204 and failed units0. Bounded startup evidence only. #41 actual boot/driver startup/IIO/HTTPS passed, failed units0, ring error2 from ABOX startup and warning65; present silent playback/exact1s capture pass with no new IPC retry, audio initialization remains under investigation. #38 initial+normal warm boots verify checked sensor rail readback, varying accel/ALS, three driver services and primary HTTPS204, failed units0/full error-priority kernel0; #37 actual boot/BOOT/profile pins, audio/BT/sensor start and changing IIO accel/ALS passed; initial failed units0/full error-priority log0; #36 initial+warm boots failed units0 and full error-priority log0; remaining warning classes documented in KERNEL_WARNINGS.md. #25 initramfs/pinctrl/CLKOUT/phantom charger/roam-trigger errors absent; earlier SO_PASSSEC/Dbusmenu fixes retained | Bounded observation; RGB/haptic/P2P and CPU-feature limitations remain; cache metadata is now corrected |
| Desktop driver trial / rollback | Private Shell loaded coherent EGL/Gallium/GBM/dri_gbm; first rollback needed manual clean-session recovery; corrected second natural300s rollback returned actual stock Shell, original environment and screen-off/locked state with0 new GPU faults | Native43 optional exact login PAN migration gives coherent private Shell + manager environment; fullscreen targeted3/3 and FIFO61/61/61 pass,0 new GPU faults. Natural300s recovery restores original login bytes/metadata, all4 files, manager environment and stock Shell; post ring error0/warning63, failedunits0. Subsequent mesa43-full accepted after full33/readback100/FIFO60/61/61 and exact native evidence; distinct warm boot preserves coherent private libraries/settings. Visible browser pixel/policy check now passes; post-warm FIFO11 regression remains unresolved despite later60fps repeat. Endurance/animation stability pending |
| LTE / voice / SMS | Owner confirms Android LTE on this exact S9+; current personal KT SIM. Corrected IPv4 attach protocol home/roam fields to2, consistent with owner IP->internal1->wire2 mapping. Native43 candidate registers EPS1 and activeCID1 with modem IPv4/DNS/MTU. Fresh online trial verifies modem-only DNS and certificate-verified TLS/HTTPS204, source+device bound to rmnet0: RX10/TX9 packets,0interface errors, temporary state restored. Early/late boot completion and library-loader trials remain documented in CHANGELOG | LTE IPv4 data path verified in a bounded hardware trial. A distinct cold trial repeats modem DNS/TLS204 with0errors and restores network state; completed CGATT query false→true observed. A separate native43 cold trial repeats modem DNS/TLS204 with the same running sensor service, readable accel/ALS feeds, and verified separate mount/device views through cleanup. A further native43 trial restarts the dedicated sensor service while the same RIL/PDP session carries DNS/TLS204 before and after; accel/ALS feeds recover and both probes restore the route state. Specific already-attached/no-SET-ACK alternate gate remains host-tested only. Default modem remains opt-in/off; persistent auto-connect/reconnect/ordered shutdown, IPv6, voice/SMS and other modes pending. Native44 exposes IPv4/IPv6 policy rules and verified IPv4 modem DNS/TLS204 over a separate source-selected table while preserving the Wi-Fi default; temporary state restored. Opt-in held PDP repeated modem DNS/TLS204 in the same session 27.1 s after qualification with a 20 s activation limit. A subsequent native44 trial observed release result 0x8000 and CID state 3 before the separate RF low-power handshake. Native44 requested one same-RIL reconnection and verified DNS/TLS204 independently in both contexts, release 0x8000/state3, zero interface errors and unchanged Wi-Fi. Native44 unbound nonroot IPv4 HTTPS204 worked via preferred Wi-Fi, then LTE during an intentional Wi-Fi disconnect (uncached system DNS over rmnet0, zero interface errors), then Wi-Fi after restoration. A separate native44 lease-driven route process repeated unbound Wi-Fi/LTE/Wi-Fi HTTPS204, applied and reverted LTE DNS itself, and removed/reapplied its route across a controlled PDP cycle. Native44 also verified systemd ExecStopPost cleanup of owned route, address, link and DNS after actual route-worker SIGKILL while modem and sensors stayed alive. An explicitly armed native44 one-shot unit also started LTE from a distinct boot, passed unbound HTTPS204 and system DNS with Wi-Fi down, and cleaned up after stop. The native44 300 s one-shot also passed three actual modem DNS/TLS probes (26.0, 135.7, 270.7 s), shared sensor/RIL continuity and natural release/cleanup. Stock Ubuntu ModemManager installed/enabled but enumerates no internal modem, so native GNOME WWAN controls remain open. An opt-in native44 module associated umts_router and rmnet0 with the actual shared platform modem and repeated DNS/TLS204, with zero interface errors; stock MM still reported no modems during traffic. A root-private typed RIL broker returned actual EPS/attach/RSSI during separate verified native44 LTE data and removed its socket on stop. Desktop control and bearer handoff remain open. IPv6 data, unattended radio recovery and continuous boot-service operation remain unqualified. Missing ECT/bus QoS support remains; historical vendor cause namespaces are unconfirmed |
| Ubuntu Mobile Network | Native44 root-private RIL controls verified on the same modem session: two explicit IPv4 connects passed LTE DNS and certificate-verified HTTPS204. Both releases qualified, removed the lease and returned to idle. Real SIM readiness and normal radio state remained true across both releases. A later trial rejected a mismatched APN and stale cancel, canceled a queued connect, then confirmed LTE-only traffic on generations 2 and 3. | Isolated ARM64 ModemManager on native44 exported the physical rmnet0 and ready SIM, then connected an IPv4 bearer. Modem-only DNS and HTTPS204 passed through it and ModemManager released it. Separate bounded system-bus trial passed stock NetworkManager GSM activation, rmnet0 route, LTE-only DNS and HTTPS204, teardown and Wi-Fi preservation. Stock ModemManager was restored and enumerates no device. A distinct one-shot boot automatically started desktop LTE. NetworkManager WWAN off/on/off released, automatically reconnected and released the real bearer, with two LTE-bound HTTPS204 data generations and the second repeated after 30s. Supervisor-bound RIL and CBD carried system LTE through 306.5 seconds on the same bearer. An enabled native44 service automatically connected on two ordinary boots with real LTE DNS and HTTPS204. Verified normal stop, modem low power, temporary route/profile cleanup and stock manager restoration between boots. A later native44 SIPC probe module passed automatic LTE DNS and HTTPS204, Wi-Fi HTTPS204 and sensor reads. A separate forced supervisor-only exit qualified graceful child teardown, modem low power, lease/mount/profile/route cleanup and stock-manager restoration with Wi-Fi active. Abrupt RIL-only exit also cleared stale lease/socket and restored Wi-Fi and the stock manager. Modem release was unconfirmed on that fault; LTE worked after reboot. Direct GNOME interaction and spontaneous radio-outage recovery pending. |
| Speakers / microphone / headset | Owner heard speaker tones and short recorded playback; #11 MICBIAS1 readback8065 confirms bypass cleared; GNOME input/output nodes persist | Initial speech replay failed with robotic/crackling sound. ABOX timing rule removed repeated resyncs; subsequent cue-assisted10s spoken recording/replay confirmed clear without crackling by owner. Short acoustic and owner-confirmed voice recognition/response tests pass; long quality pending. Full audio quality, headset/call paths, multi-mic and processing parity unverified |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; exact-BOOT startup and hci0 persisted on#13; pairing/audio pending |
| Accelerometer / gyroscope | Raw motion response verified; #25 actual8G and six-pose signed-axis qualification; #27 real IIO accel/scale/matrix | Acceleration system integration verified; gyroscope remains raw-only and accuracy/endurance unqualified |
| Automatic screen rotation / sensor service | #27 SensorProxy sees real accel/ALS; GNOME normal→transform0, left-up→transform1; owner confirms rotation and correct touch before and after reboot; service auto-starts. Owner found native Auto Rotate button and confirmed disabling it prevents rotation; live orientation-lock=true | Normal/photo-landscape rotation, reboot persistence and native rotation lock verified. #28 reboot preserves lock setting=true; other poses/endurance/power pending; #28 real room-light ON/OFF drives standard GNOME duty-backlight levels4→16→3; sensor/backlight auto-start and level3 restoration passed a further#28 reboot; optical/color/flicker parity pending |
| SSP startup transport | Native44 4–5 ms first-write settle trial loaded on the phone; a zero-byte acknowledgment still occurred. Verified original profile restored on a separate boot, with active sensor service and readable acceleration and light feeds. | Startup retry remains open. The timing change was discarded. Opt-in diagnostics confirmed zero response status and credit with MCU-ready high, on transaction 455. A subsequent paired transaction completed all 36 bytes on attempt 2 with credit restored. |
| Light / proximity / compass / pressure | #23 owner light cover/uncover:204 samples/60s,68..391lux. Proximity detect0/1 with ADC118..1105. Isolated compass:200 vectors/40s,accuracy0→2. Pressure84 samples/15s. No malformed frames | Physical light/proximity/motion response verified. Light IIO/desktop integration verified on#27; #28 real room-light changes drive GNOME backlight. Heading/absolute pressure/calibration remain pending (rotation listed separately). Combined raw/calibrated compass trial had frozen calibrated vectors; default diagnostic corrected to isolated calibrated mode |
| Compass heading | #27 original cardinal comparison status1, up to~37degree disagreement with reference; private own PDC/NVM initialization trial280samples status3/overflow0. Offline tilt geometry and quality gates tested | Current production profile does not initialize/enable a compass; app remains waiting. Post-init cardinal/tilted physical reference and standard heading-backend integration pending |
| Korean text / touch input | Noto CJK/emoji font coverage passed. Native IBus physical-keycode probe commits 가나다, virtual-keycode0 rejects all letters; owner sees Latin output despite Hangul selection | Pinned local1.5.5-2build2+g965n1 native package built/installed; physical and virtual probes both commit 가나다; owner confirms real Korean touch input. Post-reboot virtual probe also commits 가나다 and standard IBus auto-starts. Fresh image rebuild pending |
| Vibration / notification RGB | Source audit found missing DT/config connections and upstream object/mask/bias errors; reviewed source fixes pass host C tests only | Not enabled or hardware-qualified; PWM clocks/supply/current limits and stock behavior parity pending |
| Cameras / flash / hardware video codecs | No full pipeline tested | Pending port/validation |
| GPS / NFC / fingerprint / other Lineage-supported sensors | No end-to-end test yet | Pending port/validation |
| Buttons / brightness / USB OTG / fast charging | #16 non-root GPIO reader/seat ACL verified; #18 four direct DPMS cycles retained background heartbeats and fresh SSH,0 new matching display/GPU errors; original state restored | Screen-only path verified; #28 opt-in duty backlight0..16 accepts seven-level sweep including off/max, GNOME brightness API available. Real room-light changes drive GNOME brightness4→16→3 on old16-level driver; native33 now uses401stock-duty levels with~4.95s full transition and owner-confirmed smooth automatic brightness; native switch off/on and3DPMS restores pass; active white-window max/min repeats correlate with~0.32A net-current change. Optical luminance/color/flicker, physical short/long button interaction, OTG and fast-charge negotiation pending |
| Charging / temperature / idle power | Native#16 input limit500000uA; inhibit → Not charging/N/A and near-zero battery current; auto → Charging/Fast restored | Charge-control field/encoding fixes hardware verified; no current increase. Fast charging negotiation, thermal endurance and screen-off drain unverified |
| Sleep / resume / warm reboot | Sleep masked; native#27/#28 warm reboots succeeded in observed trials; deep-idle issues unresolved | Bounded warm reboot observed; suspend/deep-idle and general recovery/endurance unqualified |

Software guard regressions cover recovery, transfers, filesystem status,
Wi-Fi recovery, ACPM dispatch, hub patch validation BOOT-only updates and private RFS copies.
CI never flashes or publishes blobs.
The full-function target is **not achieved**. Only the individual observations above are verified; full LTE/audio/Bluetooth/sensor support is not claimed.

GPU diagnosis: the preserved#21 timeout dump's valid fragment metadata shows
an actual1440x2896 AFBC32x8 render target, versus the reported1440x2960 window.
Its simple header/body extents fit the backing allocation. Earlier noafbc
environment-only comparisons did not verify the actual modifier, so they do
not exclude compression as a contributor. The invalid sparse-heap dump object
is not decoded or treated as valid evidence. No additional stress run or
physical light-response test is implied by this metadata inspection.
The source-only zero-initialization correction for invalid dump ranges is not
a GPU-stability fix or a claim that sparse heap capture is now supported.
The later#21 nocrc,noafbc protocol comparison still presents AFBC32x8 buffers
and incurs five glmark timeouts. Interleaved protocol output invalidated the
runner's unmodified scene-completeness check; it is a diagnostic comparison,
not another qualified rendering pass. All temporary session state was restored.
The isolated Mesa explicit-modifier candidate has passed host selector tests
and native configuration/compilation. Output hashes, coherent vendor paths and
ARM64 ELF headers verified. An isolated128x128/100-frame readback then passed
with zero pixel mismatches/new matching kernel faults and private-library load
proof. A later patched windowed native-request targeted run passed3/3 scenes
with0 new GPU faults/timeouts and actual U-tiled presentation/private-library
maps. Most windowed buffers were1440x2896. The desktop still uses system Mesa.

A separate isolated fullscreen targeted run now passes3/3 with all11772
committed buffers1440x2960/U-tiled and0 new GPU faults/timeouts. The later full33/FIFO suite also completes without new GPU journal faults,
with one internal100us IRQ-check rejection of undetermined frame impact.
Desktop and endurance qualification remain pending; system Mesa unchanged.


Boot-log maintenance checkpoint: INITRAMFS_FORCE plus pre-build embedded-init
contract passes four host tests and isolated real olddefconfig; no new Image
or native boot qualified yet. CLKOUT, pinctrl IRQ metadata, MAX77705 child
nodes and Wi-Fi warnings remain under source review. The latest desktop
profile trial failed manager-environment validation and automatically restored
the stock desktop; the mismatch cause remains unknown. Its new private
pre-rollback observation passes 26 host tests, with no subsequent native trial.


Native #22 follow-up: BOOT-only guarded write/readback and actual boot passed;
INITRAMFS_FORCE removed the external-placeholder unpack failure. Fresh USB SSH,
zero failed system units and exact audio/Bluetooth service startup confirmed.
Pinctrl/CLKOUT/MFD/Wi-Fi errors remain; raw roam firmware status is -3. No new
functional, modem, suspend or GPU desktop/endurance qualification is implied.

Pinctrl topology candidate: two inapplicable GPIO-group initializers removed
with all wakeup/bank data retained; gpa4 SPI446/447 restored from pinned stock
source. Three host sanitizer tests pass. Native boot-log verification pending.

Native #23 actual boot: guarded BOOT readback and package identity verified.
All three former pinctrl IRQ topology errors absent; initramfs failure remains
absent; zero failed system units, audio/Bluetooth startup active, no matching
new fatal/GPU/BUG/WARNING signatures in this boot window. Physical IRQ consumer
behavior/wakeup/suspend untested. CLKOUT/MFD/Wi-Fi errors remain open.


#24 sensor/clock follow-up: both thermistor factory ADC reads returned values
(2154/2220) without threshold writes, but temperature calibration/overheat
notifications remain unverified. Rotation16/17 raw packets received84each/15s;
last byte246,scaling/orientation semantics and one unparsed frame unresolved.
CLKOUT parent/probe errors absent with two registered providers; inherited
output0 unknown parent/rate0 is preserved, so output qualification remains
open. Wi-Fi policy5 read succeeded and legacy trigger still BADOPTION; fix
under source review. No new desktop sensor integration/autostart is enabled.

Sensor application checkpoint: native#25 optional Qt sensor explorer/demo,
Psensor and local Compass frontend installed; real Wayland launches verified.
No standard IIO/hwmon sensor backend exists. Proxy's no-device exit is normal.
Compass intentionally waits without a real reading; GNOME automatic screen
rotation/brightness remain unimplemented. App installation is not parity.

Standard sensor integration candidate: actual#25 E1 reports8G, but owner could
not perform mounting-pose checks. Acceleration/rotation stays disabled. New
real IIO feed module is ALS-only by default and source-tested; IIO core/module
not yet built or booted. No new system integration success claimed.


Latest native#27 integration supersedes the earlier source-only checkpoints:
real IIO acceleration and illuminance feed stock SensorProxy and Qt light.
GNOME automatic rotation/touch plus reboot auto-start are owner-confirmed.
Ordered stop removes devices/children/mounts and restart succeeds. At that
#27 checkpoint automatic brightness and compass heading were still pending.
Native#28 limited duty-only backlight command sweep and three DPMS restore
cycles passed; real room-light ON/OFF drives GNOME levels4→16→3. Repeated
white-window max/min changes correlate with~0.32A net battery-current change.
A further real#28 reboot auto-started sensor/audio/BT services and restored
backlight3/ambient=true/rotation-lock=true. Optical luminance/color/flicker
remain unqualified. Native#27
own-backup magnetic initialization raised status1→3, but cardinal/tilted
heading after initialization remains unqualified.

Current#28 full error-priority audit supersedes any broad reading of earlier
no-matching-fatal-signature observations: touch initial probe-110 (later
bound), Wi-Fi P2P timeout/-5 and three SSP initial TX retries are still logged.
Current accel/ALS reads and sensor/audio/BT services work, but recovered
startup retries are not fixes and do not establish all-module parity.

Touch#29 readiness candidate: first recovery-to-native boot passed with4s
settling, but both subsequent warm boots still timed out before binding later.
Do not label the timing change repaired; actual readiness signaling is under
investigation. SSP strict-ACK candidate is source/compile tested only, default
off and not deployed. Production29 sensor service uses the pre-candidate module.

Latest#30 touch correction supersedes the failed#29 fixed-delay candidate:
real IRQ asserted103ms after rail-on, so the I2C controller is reinitialized
once per ACPM power generation before first TSP transfer. Native initialboot
and3warmboots passed with no initial touch error; warm controller status
000a0006→00080001 was observed. Suspend/cold/endurance remain unqualified.
Native30 explicitly keeps checkedSSIACK modeN; its hardware trial is pending.
P2P required-step checks are source/C-object tested only, not in this BOOT.

CheckedSSIACK exact30 opt-in: live initial+2warmboots reached sensor readiness,
actualaccel/ALS, strictY/faultN; independent pinned-baseline recovery also
actually restoredN and rebooted in a separate timed trial. One initial0/36
retry remains. Defaultoff; end-to-end integrity/endurance and fullhub parity
are not qualified. Kernel31 P2P build passed, native behavior still pending.

Native31: BOOTreadback+nativeboot+sensoractualreads/audioBTstartup passed.
P2P setup0..4 succeeded but IF_ADD timed out: still failing. Two initialSSI
retries followed by strictY/faultN datafeed; all-error-free claim false.
New readonlyIFevent-mask diagnostic is not yet hardware-qualified.

Latest#32 initial+warm boot: touch reset before first access/no-110, sensor/
audio/BT auto-start and realaccel/ALS; strictY/faultN, failedsystemunits0.
P2P still fails with actual event-mask IFbit1; one initialSSI retry on warmboot.
These observations do not establish all-modules-working or error-free kernel.

Native32 Control Center Power Automatic Screen Brightness checkbox is visible;
actual native toggle changed ambient-enabled true→false→true. Finalon.
401stock-duty/asynchronous-output-ramp candidate passes hostC tests only;
optical smoothness, newlevelhardware and DPMS regressions pending newboot.

Native33: smoother401level output and owner physical assessment passed; standard
native ambient toggle verified. SPI ID/OF warning absent with real sensor data.
P2P realfirmwareBSS2 query succeeded but IF_ADD still times out; compatibility
candidate remains off/not deployed. No all-module parity claim.

Native35 bounded P2P lifecycle/scans and preserved primary HTTPS passed twice.
Peer discovery/groupdata and boot-default opt-in remain separate qualification.

Latest native36 supersedes earlier pending persistent-P2P checkpoints: boot
opt-in, one native context, standard NetworkManager peer find and owner reverse
discovery passed. Peer group negotiation/transfer remains unqualified. Initial+
warm boot error-priority0/failedunits0; warnings still present and not hidden.

Native38: sensor PMIC error propagation/readback passes actual-C fault
injection and the new module normal enable/readback path on actual initial
boot. mcu_power1, strict SSI Y/faultN, varying accel samples/ALS0, three driver
services active, failed units0/kernel error-priority0. Hardware failure
injection, programmed-mode versus measured voltage and hub hard reset remain
unqualified. Native38 normal warm reboot also passed fresh accel/ALS,
checked supply readback, startup services, SSI Y/faultN, HTTPS204 and zero
error-priority kernel/failed units; MCU_RESP reset warning remains.

Native39/40/41 reset investigation: a held-phase observation precedes
re-enable. Both39 legacy and40 powered-CS-inactive trials still report
MCU_RESP1. The unproven functional40 control change was reverted in41; only
read-only pin observations remain. Fresh IIO feeds do not qualify hard reset.
Native41 adds two actual ABOX startup errors; preserve them as unresolved
even though the later bounded playback/capture flow and all services pass.
