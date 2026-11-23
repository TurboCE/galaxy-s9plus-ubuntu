# SM-G965N hardware validation

Evidence updated: 2026-11-21. One Korean SM-G965N rev26 / 256GB,
original firmware G965NKSU5FVA2. Target is parity with the hardware features
supported by the reference LineageOS build, not just desktop startup.
A build or a driver node is not sufficient evidence of a working function.

For the maintained latest-state summary and continuation queue, see
[STATUS.md](STATUS.md) and [HANDOFF.md](HANDOFF.md). This file retains the
chronological per-build evidence; later qualified rows supersede older pending
checkpoints only for the tested scope.

The pre-NFC-clock-fix #48 log audit found early kernel ring-buffer warnings, including
two RTC IRQ63 type warnings with traces, CPU feature variation/taint,
unsupported NFC vendor notifications and Bluetooth transmit-power commands,
missing RGB/haptic nodes and alternate-GPT fallback. The system journal
omits part of early boot. No new warning appeared in the last 15 minutes,
no unit was failed, and no real panic/Oops/BUG or matching GPU/display fault
was observed. This is a quiet runtime observation, not a clean-boot claim.
The subsequent NFC clock fix eliminated the observed vendor notification in
its verified warm boot; the RTC/CPU/GPT and other unrelated warnings are not
marked fixed by that NFC test.

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
| GPU early-boot FIFO | Native #44 accepted hardware Mesa. Full-screen, windowed and repeat full-screen runs passed nine scenes at 60–61 FPS. A distinct warm boot started at 13.25 s and passed nine scenes at 58–61 FPS, with no new matching GPU/display fault or DECON latch timeout. | Historical 11 FPS did not recur. The intermittent failure, GNOME overview stutter and video endurance remain open. |
| GNOME app-list timing | Native #44 real shortcut transitions, five opens and five closes. Opening paint p95 18.378 ms and dispatch p95 24.596 ms, with five of 65 paints over 16.7 ms. Closing paint p95 4.280 ms. Desktop restored, temporary input driver unloaded, no matching GPU/display fault. | Opening stutter is observable in compositor work despite good FIFO scenes. Remaining performance cause and physical scanout cadence are unqualified. |
| GNOME app-list clock comparison | Native #44 A/B/A of big CPU frequency, GPU floor and GNOME Shell main-thread utilization clamp. Big CPU performance lowered opening paint p95 to 17.790 ms from 21.271/22.636 ms controls, with GPU at 260 MHz. All phases retained four paints over budget. | CPU-side workload is the stronger lead. Higher GPU floor and the tested thread clamp did not consistently improve opening. Power policy restored. |
| GNOME overview versus app grid | Native #44 four opens of each phase, window picker/app grid/window picker. Paint p95 was 18.062/18.645/21.097 ms with four paints over 16.7 ms per phase. Input and paint marks outweighed swap marks in the CPU comparison. | Frame-budget pressure occurs in both overview modes. Shared compositor/input work remains under investigation. |
| GNOME overview CPU stacks | Native #44 userspace sampling of six opens per mode. Mesa byte-to-byte texture conversion was the top resolved leaf symbol in both opening windows. Standalone ARM SIMD prototype passed sanitized byte-equivalence checks and ran a synthetic buffer in 2.99 ms versus 12.19–13.49 ms scalar. | Real hotspot located and candidate primitive verified. Actual animation performance remains pending. |
| Mesa NEON texture swizzle | Native #44 isolated ARM64 Mesa candidate with matching library maps. Sanitized swizzle regression and 100 Mali-G72 RGBA/BGRA readback frames passed with 6,553,600 exact output bytes per variant. | Mesa integration and offscreen correctness verified. Real GNOME animation, wider graphics coverage and rollout remain pending. |
| Mesa NEON GNOME virtual monitor | Native #44 isolated Panfrost 1440×2960 GNOME baseline/candidate/baseline comparison. Six measured opens per mode and phase. App-grid opening paint p95 6.589/6.482/6.878 ms, picker 4.229/4.266/4.274 ms. No matching GPU/display kernel fault. | No consistent improvement in the tested transitions. Virtual output did not reproduce physical desktop stutter. Live Mesa remains on the accepted build, and physical desktop comparison is pending. |
| GPU PLL runtime resume | Native #44 kernel logged a 260 MHz lock timeout and subsequent 455 MHz rollback timeout. A later 40-run exact readback observed 442 power-ons, 4,000 correct frames, and zero new matching PLL/Panfrost errors. Each run ended at 260 MHz. | The higher-rate-to-idle failure remains intermittent. The two upper PLL tuples violate reference limits. A candidate with in-range tuples compiled as an ARM64 driver object. Hardware boot and repeated rate-transition checks remain pending. |
| GPU PLL #45 build | Linked ARM64 Image and wrapped BOOT candidate verified against #44 configs and device trees. The linked clock table contains both in-range upper tuples. The live BOOT and protected partition hashes matched the recovery inputs. | Build and recovery preflight passed. Hardware boot and rate-transition checks remain pending. |
| GPU PLL high-rate #44 baseline | Six paced GPU load bursts with default governor and runtime gating. Devfreq counted two 455→260 MHz and four 572→260 MHz transitions. After load and runtime idle, 600 RGBA/BGRA frames matched exactly. Across the test, 74 power-ons, 73 power-offs and no new matching PLL/Panfrost errors. | Both high-rate transitions were exercised on the current kernel. The historical intermittent failure did not recur in this bounded sample. #45 A/B remains pending. |
| Wi-Fi | Native#25 HTTPS204 explicitly bound to Wi-Fi after policy correction; earlier NTP/connection observations | Data path verified; long reconnect tests pending |
| Wi-Fi station scan on #48 | Explicit NetworkManager rescan succeeded; a subsequent cached listing contained 15 AP entries with signal 22–100/100 and the current connection. Wi-Fi-bound TLS HTTPS returned 204 afterward. No SSIDs/BSSIDs recorded. | Bounded live station scan and continued internet connectivity verified. Scan endurance and AP handover remain unqualified. |
| Wi-Fi manual disconnect | Native #44 with the updated guard. NetworkManager device disconnected and device autoconnect blocked for 72 s while the guard ran, then the original saved profile was manually reactivated and Wi-Fi HTTPS204 passed. No new Wi-Fi/P2P warning or failed unit. | User disconnect and manual recovery verified. Automatic RF-outage recovery and AP roaming remain unqualified. |
| Wi-Fi Direct / roaming | #24 policy5 and rawBADOPTION(-3) identified; #25 scoped product-profile preservation removes legacy-trigger initialization failure | Initialization correction hardware verified; Native35 passed2create/start/scan/stop/delete cycles with primary identity and HTTPS204 preserved. Native36 explicit build opt-in auto-creates P2P device across initial+warm boot without IF_ADD timeout; native NetworkManager found Fold7 and owner confirmed reverse discovery. Native36 Fold7 group negotiation + dedicated IPv4 succeeded; source-bound 1MiB transfers in both directions matched SHA256; primary HTTPS204 and cleanup passed. Native37 passed two groups with bidirectional 1MiB hash-checked transfer, active channel query and cleanup with primary HTTPS204 preserved; teardown chanspec errors0, action-frame retry batch1 remains. Endurance and real AP handover remain unqualified |
| Wi-Fi Direct discovery on native44 | Three 8 s NetworkManager find/stop cycles with Wi-Fi HTTPS204 during and after each, same station connection and interface index, and no new Wi-Fi/P2P kernel warnings or errors. One unconfirmed peer was seen. | Discovery and Wi-Fi coexistence verified. Native44 peer connection, transfer, and AP handover remain pending. |
| Wi-Fi Direct after Wi-Fi reconnect | Native #44, three 10 s find/stop cycles after restoring the saved station profile. Same profile and interface index, Wi-Fi HTTPS204 during and after each cycle, and zero new Wi-Fi/P2P warning/error lines. | Discovery after reconnection verified. No confirmed Fold7 in the scans; group connection and file transfer remain pending on this build. |
| Wi-Fi Direct discovery termination | Native #44, NetworkManager timeouts of 5, 8 and 12 seconds yielded wpa_supplicant FindStopped at 5.024, 8.024 and 12.028 seconds. An explicit cancellation stopped at 2.040 seconds. Same station profile and interface index, eight Wi-Fi HTTPS204 checks, no new matching kernel warning. | Automatic expiration, manual cancellation and subsequent rediscovery verified. Native #44 group negotiation and file transfer remain pending. |
| Wi-Fi Direct observer cleanup | Updated CLI on native #44 completed a six-second scan and stop with the device disconnected afterward and Wi-Fi HTTPS204. Injected StopFind failure rejected by the CLI while preserving its receipt in the host regression. | Successful device path and failure reporting verified. Native #44 pairing and file transfer remain pending. |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| CPU cache topology | Native42 one-shot architectural reads on all8 cores, selectors restored/probe unloaded; explicit measured DT cache graph candidate compiles and passes positive/negative artifact checks | Native43 all8 CPU sysfs geometry/ownership matches measured graph; cache warning absent in full early ring (error0/warning63), services/feeds/HTTPS pass. Distinct normal warm boot repeats all8 geometry/graph, services/feeds/HTTPS and error0/warning63. Scheduler debug-domain files unavailable. No CPU-feature masking or performance claim |
| System services | Native44 distinct cleanup boot: three driver services active, accel/ALS readable, Wi-Fi-bound HTTPS204, failed units0, full ring errors0/warnings63/CallTrace0/SError0; earlier SSP retries remain intermittent. Latest43 LTE cold-data cleanup distinct boot: full early ring error1 (initial SSP zero-write retry)/warning63, CallTrace0/SError0, failedunits0; three driver services active, varying accel/readable ALS. Latest43 RFS-trial cleanup boot full ring error0/warning63 (header present), varying accel/three active services/HTTPS204/failedunits0. Loaded RFS-trial ring406errors/88warnings lacks boot header;91IPC-not-open events after RIL closes remain unresolved. Previous43 modem-cleanup reboot retains two initial SSP zero-ACK retry lines; strictY/faultN, fresh accel, three services/HTTPS204/failedunits0. Loaded-modem observation has136error-priority lines/67warnings including ECT/QoS gaps and vendor diagnostics, not a clean-kernel claim. #43 initial+distinct normal warm boots: corrected measured cache hierarchy persists on8CPUs, ring error0/warning63, audio counters0, fresh accel, three services/HTTPS204 and failed units0. #42 initial native boot with matching guarded drivers passed, full ring error0/warning64; isolated legacy DSM state restore emits0 write ioctls (native41:1), state file unchanged; bounded silent playback/exact1s capture passes with0 retries/stalls/codec errors, Wi-Fi HTTPS204 and failed units0. Distinct normal warm boot also passed matching services, zero audio retry/stall/codec counters, full ring error0/warning64, HTTPS204 and failed units0. Bounded startup evidence only. #41 actual boot/driver startup/IIO/HTTPS passed, failed units0, ring error2 from ABOX startup and warning65; present silent playback/exact1s capture pass with no new IPC retry, audio initialization remains under investigation. #38 initial+normal warm boots verify checked sensor rail readback, varying accel/ALS, three driver services and primary HTTPS204, failed units0/full error-priority kernel0; #37 actual boot/BOOT/profile pins, audio/BT/sensor start and changing IIO accel/ALS passed; initial failed units0/full error-priority log0; #36 initial+warm boots failed units0 and full error-priority log0; remaining warning classes documented in KERNEL_WARNINGS.md. #25 initramfs/pinctrl/CLKOUT/phantom charger/roam-trigger errors absent; earlier SO_PASSSEC/Dbusmenu fixes retained | Bounded observation; RGB/haptic/P2P and CPU-feature limitations remain; cache metadata is now corrected |
| Sensor hub startup | Native #44 opt-in single standby, two distinct warm boots. Sensor service ready at 9.046/8.974 s versus 21.783 s baseline, all six IIO devices readable, Wi-Fi HTTPS204, no failed units. | Faster warm startup verified. MCU_RESP high and one recovered zero-ACK retry per boot. Physical reset, cold boot and suspend/resume remain pending. |
| Sensor firmware patch watchdog | Native #44 exact patched module, firmware starts 10 s watchdog and cancels at 1.272 s. Six IIO devices read 80 times each over 20 s without reset. Wi-Fi HTTPS204, no failed units. | Normal arming and cancellation verified on the handset. Forced timeout, rearm and teardown tested on the host. |
| Sensor bridge control writes | Native #44 distinct warm boot with matched module build ID. LHD armed and canceled the firmware watchdog after 1.277 s, six IIO devices passed 80 reads each, and no sensor reset request was recorded. Wi-Fi HTTPS204 and no-SIM cleanup passed; zero failed units. | Normal driver startup verified on the handset. Size, private-copy and copy-failure cases verified on the host. Modem IPC/RFS and SSP startup messages remain. |
| Sensor SPI transfer length | Native #44 distinct boot with matched build ID, no reported length or controller error, one recovered 36-byte ACK retry, and 80 reads of each of six IIO devices. Wi-Fi HTTPS204 and no-SIM cleanup passed. | Complete transfers exercised on hardware; partial completions and error propagation tested on the host. The zero ACK still occurs with the expected reported transfer length. |
| Sensor SSI ACK timing | Native #44 matched module and opt-in diagnostic boot: zero ACK during patch after a 49.249 ms gap, 39.8 us SPI call, and unchanged sampled GPIO values. Second attempt accepted all 36 bytes. Separate same-module boot verified diagnostics off, six IIO reads, Wi-Fi HTTPS204 and no-SIM cleanup. | Host-observed timing verified on hardware. The default boot still had two zero-ACK attempts; firmware state and physical SCK timing remain unverified. |
| Sensor SPI prescaler trial | Native #44 same module, requested prescaler 7 read back in the module parameter but controller clock register read zero. One zero ACK recovered. Original prescaler 3 and diagnostics-off restored on a distinct boot, with firmware, six IIO devices, Wi-Fi HTTPS204 and no-SIM cleanup passing. | Local setting did not verify a clock-rate change. Actual SCK and the CMU divider path remain unqualified. |
| Sensor CHUB clock divider | Native #44, verified USI00 divider field 0 to 1 in setup and a separate live read. Two zero ACKs on one 36-byte transaction recovered on attempt three; six IIO devices and Wi-Fi HTTPS204 passed. Distinct rollback boot verified field 0, original module, one recovered zero ACK, six IIO devices, Wi-Fi HTTPS204 and no-SIM cleanup. | Clock register write and rollback verified on hardware. No ACK improvement or verified physical SCK change. |
| Sensor SPI chip-select timing | Native #44 with a configured 25 us chip-select setup interval. The hardware transfer still produced one zero ACK before recovery; six IIO devices and Wi-Fi HTTPS204 passed. A distinct boot verified the original module and diagnostics off, with the same retry count and successful no-SIM cleanup. | The tested interval did not remove the retry. The default profile was restored. |
| Sensor firmware read and ACK timing | Native #44 exact diagnostic module. The zero ACK came 65.696 ms after the final file read; every SPI RX byte was zero. The next attempt accepted all 36 bytes. A distinct same-module boot confirmed diagnostics off, six IIO devices, Wi-Fi HTTPS204 and no-SIM cleanup. | Loader file timing and all-zero response verified on hardware. Buffered firmware transmission, physical bus state and the underlying cause remain unresolved. |
| Sensor firmware tail settle | Native #44 two timing-trial warm boots and one exact release-module warm boot with the option on and diagnostics off. All targeted 36-byte writes passed on first attempt, with no zero ACK or controller error. Each boot passed six IIO reads, Wi-Fi HTTPS204 and no-SIM cleanup. | Targeted retry avoided on the three boots. The module option defaults off and is enabled on the test handset. Cold starts and other firmware remain pending. |
| Sensor hub readiness after standby warning | On current #44, MCU_RESP stayed high during standby, but patch transfer accepted the targeted write on its first attempt and hub readiness followed at 6.461 s. Later passive GPIO read was low. The ready flag stayed set through 241 reads from each of six IIO devices and 13 Wi-Fi-bound HTTPS204 checks across 120 s. | Sensor and Wi-Fi paths remained stable in this observation. Whether the hub reset during standby and why MCU_RESP stayed high remain unverified. |
| Desktop driver trial / rollback | Private Shell loaded coherent EGL/Gallium/GBM/dri_gbm; first rollback needed manual clean-session recovery; corrected second natural300s rollback returned actual stock Shell, original environment and screen-off/locked state with0 new GPU faults | Native43 optional exact login PAN migration gives coherent private Shell + manager environment; fullscreen targeted3/3 and FIFO61/61/61 pass,0 new GPU faults. Natural300s recovery restores original login bytes/metadata, all4 files, manager environment and stock Shell; post ring error0/warning63, failedunits0. Subsequent mesa43-full accepted after full33/readback100/FIFO60/61/61 and exact native evidence; distinct warm boot preserves coherent private libraries/settings. Visible browser pixel/policy check now passes; post-warm FIFO11 regression remains unresolved despite later60fps repeat. Endurance/animation stability pending |
| LTE / voice / SMS | Owner confirms Android LTE on this exact S9+; current personal KT SIM. Corrected IPv4 attach protocol home/roam fields to2, consistent with owner IP->internal1->wire2 mapping. Native43 candidate registers EPS1 and activeCID1 with modem IPv4/DNS/MTU. Fresh online trial verifies modem-only DNS and certificate-verified TLS/HTTPS204, source+device bound to rmnet0: RX10/TX9 packets,0interface errors, temporary state restored. Early/late boot completion and library-loader trials remain documented in CHANGELOG | LTE IPv4 data path verified in a bounded hardware trial. A distinct cold trial repeats modem DNS/TLS204 with0errors and restores network state; completed CGATT query false→true observed. A separate native43 cold trial repeats modem DNS/TLS204 with the same running sensor service, readable accel/ALS feeds, and verified separate mount/device views through cleanup. A further native43 trial restarts the dedicated sensor service while the same RIL/PDP session carries DNS/TLS204 before and after; accel/ALS feeds recover and both probes restore the route state. Specific already-attached/no-SET-ACK alternate gate remains host-tested only. Default modem remains opt-in/off; persistent auto-connect/reconnect/ordered shutdown, IPv6, voice/SMS and other modes pending. Native44 exposes IPv4/IPv6 policy rules and verified IPv4 modem DNS/TLS204 over a separate source-selected table while preserving the Wi-Fi default; temporary state restored. Opt-in held PDP repeated modem DNS/TLS204 in the same session 27.1 s after qualification with a 20 s activation limit. A subsequent native44 trial observed release result 0x8000 and CID state 3 before the separate RF low-power handshake. Native44 requested one same-RIL reconnection and verified DNS/TLS204 independently in both contexts, release 0x8000/state3, zero interface errors and unchanged Wi-Fi. Native44 unbound nonroot IPv4 HTTPS204 worked via preferred Wi-Fi, then LTE during an intentional Wi-Fi disconnect (uncached system DNS over rmnet0, zero interface errors), then Wi-Fi after restoration. A separate native44 lease-driven route process repeated unbound Wi-Fi/LTE/Wi-Fi HTTPS204, applied and reverted LTE DNS itself, and removed/reapplied its route across a controlled PDP cycle. Native44 also verified systemd ExecStopPost cleanup of owned route, address, link and DNS after actual route-worker SIGKILL while modem and sensors stayed alive. An explicitly armed native44 one-shot unit also started LTE from a distinct boot, passed unbound HTTPS204 and system DNS with Wi-Fi down, and cleaned up after stop. The native44 300 s one-shot also passed three actual modem DNS/TLS probes (26.0, 135.7, 270.7 s), shared sensor/RIL continuity and natural release/cleanup. Stock Ubuntu ModemManager installed/enabled but enumerates no internal modem, so native GNOME WWAN controls remain open. An opt-in native44 module associated umts_router and rmnet0 with the actual shared platform modem and repeated DNS/TLS204, with zero interface errors; stock MM still reported no modems during traffic. A root-private typed RIL broker returned actual EPS/attach/RSSI during separate verified native44 LTE data and removed its socket on stop. Desktop control and bearer handoff remain open. IPv6 data, unattended radio recovery and continuous boot-service operation remain unqualified. Missing ECT/bus QoS support remains; historical vendor cause namespaces are unconfirmed |
| Ubuntu Mobile Network | Native44 root-private RIL controls verified on the same modem session: two explicit IPv4 connects passed LTE DNS and certificate-verified HTTPS204. Both releases qualified, removed the lease and returned to idle. Real SIM readiness and normal radio state remained true across both releases. A later trial rejected a mismatched APN and stale cancel, canceled a queued connect, then confirmed LTE-only traffic on generations 2 and 3. | Isolated ARM64 ModemManager on native44 exported the physical rmnet0 and ready SIM, then connected an IPv4 bearer. Modem-only DNS and HTTPS204 passed through it and ModemManager released it. Separate bounded system-bus trial passed stock NetworkManager GSM activation, rmnet0 route, LTE-only DNS and HTTPS204, teardown and Wi-Fi preservation. Stock ModemManager was restored and enumerates no device. A distinct one-shot boot automatically started desktop LTE. NetworkManager WWAN off/on/off released, automatically reconnected and released the real bearer, with two LTE-bound HTTPS204 data generations and the second repeated after 30s. Supervisor-bound RIL and CBD carried system LTE through 306.5 seconds on the same bearer. An enabled native44 service automatically connected on two ordinary boots with real LTE DNS and HTTPS204. Verified normal stop, modem low power, temporary route/profile cleanup and stock manager restoration between boots. A later native44 SIPC probe module passed automatic LTE DNS and HTTPS204, Wi-Fi HTTPS204 and sensor reads. A separate forced supervisor-only exit qualified graceful child teardown, modem low power, lease/mount/profile/route cleanup and stock-manager restoration with Wi-Fi active. Abrupt RIL-only exit also cleared stale lease/socket and restored Wi-Fi and the stock manager. Modem release was unconfirmed on that fault; LTE worked after reboot. Direct GNOME interaction and spontaneous radio-outage recovery pending. |
| Desktop LTE without SIM | Native #44 distinct boot. RIL delivered card-not-present 0x80 twice. Desktop unit inactive/success, child processes stopped, no private mount, lease or LTE route, stock ModemManager active, Wi-Fi HTTPS204, zero failed units. | No-SIM startup cleanup verified. SIM-present reconnect on this build and hot reinsertion remain pending. |
| Desktop LTE cleanup detail | Live #44 after a successful no-SIM exit. No desktop override, modem runtime mount, lease, socket or LTE routes. Eight rmnet interfaces remained down, with no addresses or DNS scope. Stock ModemManager and Wi-Fi-bound HTTPS204 passed. | Cleanup and Wi-Fi coexistence verified. Stock desktop controls show no modem in this state. |
| Modem link setup diagnostics | Ten routine link-construction messages were logged at error priority on #44. Isolated ARM64 candidate build retained mapping errors and emits a setup summary without pointer addresses. | Build-level verification only. Runtime log classification awaits a distinct device trial. |
| LTE IPv6 and dual-stack request fields | The attach and PDP definition encoders agree on wire values 2, 5 and 6. Standalone byte construction passed for all three protocols on the native #44 ARM64 userspace and kept the IPv4 default identical. | Request construction verified. Modem activation, prefix and route acquisition, DNS and IPv6 data remain pending with a usable SIM. |
| LTE experimental address observation | Local bounded trial patch passed host guards and an ARM64 fixture for two same-context address-family messages and one-shot deactivation. Existing desktop path stays on the qualified IPv4 mode. | Fixture verification only. Live attach, assigned families, deactivation acknowledgment and IPv6 traffic remain pending with a usable SIM. |
| LTE probe DNS decoding | Updated A/AAAA decoder parsed real answers over the native #44 Wi-Fi interface. Host tests rejected unrelated owners, wrong questions and looping aliases. | Decoder verified. Wi-Fi DNS answers do not qualify LTE-bound IPv6 DNS or data. |
| IPv6 probe transport binding | Native #44 passed exact IPv6 TCP and UDP USB payload echo, with the expected link-local source and interface and IPv6-only sockets. The same USB source was rejected on Wi-Fi. IPv4 Wi-Fi DNS and certificate-verified HTTPS204 passed using the same helper. | Source/interface binding verified on the handset. Modem IPv6 routing and carrier transport remain untested. |
| Modem SBD ring bounds | Native #44 distinct boot verified the new module build ID and 18 initialized SBD rings. Last data buffer end 4,276,224 of 5,242,880 bytes, PIF_INIT_DONE sent, no-SIM cleanup and Wi-Fi HTTPS204 pass. | Valid configuration exercised on hardware. Invalid layout tests ran on the host. SIM-present traffic with this module remains pending. |
| Modem SBD startup diagnostics | Native #44 distinct boot with matched module build ID, 18 rings, the same buffer end and PIF_INIT_DONE. SBD setup error-priority lines went from 44 to 0 across the two boots. No-SIM cleanup, six sensor reads, Wi-Fi HTTPS204 and zero failed units. | Normal initialization verified on hardware. Layout and initialization failure reporting tested on the host. Other error-priority messages and SIM-present traffic remain open. |
| Modem boot completion | Native #44 distinct boot with matched module build ID, normal BOOT_OFF then CP_START, one INIT_END, modem ONLINE and watchdog IRQ enabled. No timeout, no failed units, no-SIM cleanup, six IIO devices and Wi-Fi HTTPS204 passed. | Normal timing verified on hardware. Early and missing signal cases verified by the host driver test. SIM-present traffic on this module remains pending. |
| Modem packet previews | Native #44 distinct warm boot with matching module build ID. Nine real previews had valid lengths and format, two capped at 16 bytes. Modem initialization, no-SIM cleanup, six IIO devices and Wi-Fi HTTPS204 passed. | Preview behavior verified during modem startup and shutdown. Fragmented and inaccessible prefix handling exercised on the host. SIM-present traffic remains pending. |
| Modem controller IRQ resources | Native #44 reboot confirmed exact module build ID, both CP IRQ registrations, PIF_INIT_DONE and absence of the previous false invalid-GPIO error. No-SIM cleanup, five IIO reads and Wi-Fi HTTPS204 passed. | Valid probe on hardware, invalid resources and unwind on host. Physical failure/watchdog IRQ delivery and SIM-present data on this module are pending. |
| Speakers / microphone / headset | Owner heard speaker tones and short recorded playback; #11 MICBIAS1 readback8065 confirms bypass cleared; GNOME input/output nodes persist | Initial speech replay failed with robotic/crackling sound. ABOX timing rule removed repeated resyncs; subsequent cue-assisted10s spoken recording/replay confirmed clear without crackling by owner. Short acoustic and owner-confirmed voice recognition/response tests pass; long quality pending. Full audio quality, headset/call paths, multi-mic and processing parity unverified |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; exact-BOOT startup and hci0 persisted on#13; pairing/audio pending |
| Accelerometer / gyroscope | Raw motion response verified; #25 actual8G and six-pose signed-axis qualification; #27 real IIO accel/scale/matrix | Acceleration system integration verified; native #44 raw 3-axis gyro IIO starts on reboot with 100 reads/25 s and 12/14/9 distinct values across axes. Angular scale, mounting, accuracy and endurance remain unqualified |
| Automatic screen rotation / sensor service | #27 SensorProxy sees real accel/ALS; GNOME normal→transform0, left-up→transform1; owner confirms rotation and correct touch before and after reboot; service auto-starts. Owner found native Auto Rotate button and confirmed disabling it prevents rotation; live orientation-lock=true | Normal/photo-landscape rotation, reboot persistence and native rotation lock verified. #28 reboot preserves lock setting=true; other poses/endurance/power pending; #28 real room-light ON/OFF drives standard GNOME duty-backlight levels4→16→3; sensor/backlight auto-start and level3 restoration passed a further#28 reboot; optical/color/flicker parity pending |
| SSP startup transport | Native44 4–5 ms first-write settle trial loaded on the phone; a zero-byte acknowledgment still occurred. Verified original profile restored on a separate boot, with active sensor service and readable acceleration and light feeds. | Startup retry remains open. The timing change was discarded. Opt-in diagnostics confirmed zero response status and credit with MCU-ready high, on transaction 455. A subsequent paired transaction completed all 36 bytes on attempt 2 with credit restored. |
| Light / proximity / compass / pressure | #23 owner light cover/uncover:204 samples/60s,68..391lux. Proximity detect0/1 with ADC118..1105. Isolated compass:200 vectors/40s,accuracy0→2. Pressure84 samples/15s. No malformed frames | Physical light/proximity/motion response verified. Light IIO/desktop integration verified on#27; #28 real room-light changes drive GNOME backlight. Heading/absolute pressure/calibration remain pending (rotation listed separately). Combined raw/calibrated compass trial had frozen calibrated vectors; default diagnostic corrected to isolated calibrated mode |
| Pressure IIO | Native #44, pinned profile and bridge hot-loaded. Ordinary Linux user read 300 samples/60 s, 120 distinct values, 101.4119–101.4160 kPa. Acceleration, lux and Wi-Fi-bound HTTPS204 passed. On a distinct #44 boot it started automatically and returned 60 reads/15 s, 41 distinct, 101.4132–101.4166 kPa, with acceleration and light readable. | Runtime IIO read and startup on reboot verified. Absolute accuracy and per-device compensation remain pending. |
| Barometer die temperature | Native #44 distinct boot. The pressure IIO device returned 160 temperature reads/40 s, 28 distinct values, 38.00–38.27 °C. Pressure continued readable, all six IIO devices and Wi-Fi HTTPS204 passed. | Die temperature reporting and startup verified. Reference temperature and pressure accuracy remain pending. |
| Board thermistors | Native #44, matching revision 26 tables, read-only polling. Ordinary Ubuntu user read 180 pairs/45 s with nine distinct values, channel 0 at 32.2–32.4 °C and channel 1 at 28.7–29.1 °C. Other five sensor paths and Wi-Fi HTTPS204 passed. On a distinct #44 boot, both board thermistors started and produced nine distinct pairs over 40 s. | Linux IIO temperature observation and automatic startup verified. Absolute accuracy and thermal/charging policy remain pending. |
| Proximity IIO | Native #44 pinned bridge and broker hot-loaded. Stock SensorProxy recognized and claimed proximity and reported far. Ordinary user read 80 far states/20 s alongside acceleration, lux and pressure. Wi-Fi HTTPS204 and no failed units. On a distinct #44 boot, the stock proxy claimed it and reported far. | Startup, far-state publication and automatic restart verified on hardware. Physical near/far transitions on this Ubuntu path and suspend/wake remain pending. |
| Magnetometer | Native #44 bounded diagnostic with reverified own stock BOOT/EFS calibration: 135 samples at reported quality 3, zero overflow, 155 acceleration samples. The broker removed the magnetic channel at the end. | Actual magnetic data and cleanup verified. Direction and tilt accuracy require physical reference measurements with this calibration. |
| Compass heading | #27 original cardinal comparison status1, up to~37degree disagreement with reference. Offline tilt geometry and quality gates tested. On #44 stock SensorProxy reported HasCompass=false to GeoClue even during the raw capture. | App remains waiting. Post-init cardinal/tilted comparison and standard heading-backend integration pending. |
| Compass capture analysis | The offline CLI directly read real SSP broker JSONL on the phone. All 135 calibrated #44 batches passed the quality and paired-acceleration gates; the candidate matrix returned circular concentration above 0.9999. An earlier low-quality #27 capture yielded no accepted batches. | Consistency and rejection behavior verified on existing captures. The magnetic mount matrix, heading accuracy against a reference and publication to stock SensorProxy remain unverified. |
| Korean text / touch input | Noto CJK/emoji font coverage passed. Native IBus physical-keycode probe commits 가나다, virtual-keycode0 rejects all letters; owner sees Latin output despite Hangul selection | Pinned local1.5.5-2build2+g965n1 native package built/installed; physical and virtual probes both commit 가나다; owner confirms real Korean touch input. Post-reboot virtual probe also commits 가나다 and standard IBus auto-starts. Fresh image rebuild pending |
| Vibration / notification RGB | Source audit found missing DT/config connections and upstream object/mask/bias errors; reviewed source fixes pass host C tests only | Not enabled or hardware-qualified; PWM clocks/supply/current limits and stock behavior parity pending |
| Cameras / flash / hardware video codecs | #48 exposes no V4L2 video device and media support is disabled. The stock tree has four FIMC-IS sensor nodes, MIPI PHY, actuators and a camera ISP. | Native media graph, streaming, flash and hardware video codecs remain pending. |
| Native camera and fingerprint applications | On #48, installed Ubuntu Cheese and fprintd. Cheese opens but enumerates no camera; preferences probing emits missing-device GLib errors. fprintd starts on demand and its manager returns zero devices; fprintd-list reports no devices. No TEE support or SPI reader is enumerated. | Application/service foundation installed. Camera capture and fingerprint enrollment are unavailable; ISP and secure biometric transport/backend development remain pending. No PAM change. See DESKTOP_HARDWARE.md. |
| Native Mobile Network settings controls | On #48, the tracked application launcher opens the actual GNOME WWAN panel. Accessibility enumeration confirms mobile data, roaming, network selection, APNs, SIM lock and modem details controls. Rebuilt and loaded the guarded SIPC plugin; ModemManager now exposes one 4G mode and GNOME displays “4G Only” instead of including 5G. | Launcher and corrected software capability display verified on hardware. ModemManager restart preserved desktop LTE/Bluetooth services and Wi-Fi HTTPS204, with no failed units. The current SIM remains unregistered; this test does not requalify data, PIN changes, operator selection or additional RF modes. No reboot persistence test for this update. |
| GPS / NFC / fingerprint / other Lineage-supported sensors | GPS has a qualified GeoClue transport path below. The #47 kernel exposes neither NFC nor camera class devices, and the stock fingerprint stack uses a secure SPI device. | GNSS fix, NFC tag read, fingerprint enrollment and camera use remain pending. |
| Buttons / brightness / USB OTG / fast charging | #16 non-root GPIO reader/seat ACL verified; #18 four direct DPMS cycles retained background heartbeats and fresh SSH,0 new matching display/GPU errors; original state restored | Screen-only path verified; #28 opt-in duty backlight0..16 accepts seven-level sweep including off/max, GNOME brightness API available. Real room-light changes drive GNOME brightness4→16→3 on old16-level driver; native33 now uses401stock-duty levels with~4.95s full transition and owner-confirmed smooth automatic brightness; native switch off/on and3DPMS restores pass; active white-window max/min repeats correlate with~0.32A net-current change. Optical luminance/color/flicker, physical short/long button interaction, OTG and fast-charge negotiation pending |
| Charging / temperature / idle power | Native#16 input limit500000uA; inhibit → Not charging/N/A and near-zero battery current; auto → Charging/Fast restored | Charge-control field/encoding fixes hardware verified; no current increase. Fast charging negotiation, thermal endurance and screen-off drain unverified |
| Sleep / resume / warm reboot | Native #44 exposes only s2idle in mem_sleep, sleep/suspend targets masked, no RTC class device. Native #27/#28 and #44 warm reboots observed. | Bounded warm reboot verified. Timed wake, actual suspend/resume and deep-idle remain unqualified. |
| Exynos8 hardware clock | Built an isolated ARM64 RTC object and device tree from the revision 26 register/interrupt and Exynos8 match evidence. DTB inspection verified the single RTC node and both interrupts. | Candidate compile and device-tree structure verified. RTC probe, time reads, alarm delivery and timed suspend wake remain pending on hardware. |
| GPIO debug listing | Native #44 produced 23 traces from a missing optional direction callback. With upstream guard `d761c7e38a00`, #46 completed three reads on initial boot and three on a separate warm boot without a direction warning or call trace. | Verified on hardware. |
| Combined GPU and GPIO #46 build | Full ARM64 Image and BOOT package verified. Compared with #45, only the GPIO debug-listing source differs, and the configs, module symbols, device trees and ramdisk match. | Built and installed. Hardware results follow. |
| Combined GPU and GPIO #46 hardware | Fresh verified nine-partition backup, BOOT readback and native start. Three GPIO listings produced no direction warning or call trace. Nine GPU runs counted four 455→260 MHz and five 572→260 MHz transitions, with 109 power-ons, 900 exact frames and no matching PLL or Panfrost error. Original ceiling restored and Wi-Fi HTTPS204 passed. | GPIO regression and bounded GPU clock behavior verified on-device. Long-term recurrence of the intermittent PLL fault and desktop animation performance remain open. |
| #46 warm boot and services | #46 remained active after a separate reboot. Six IIO devices, three ALSA PCM endpoints, powered BlueZ controller and Wi-Fi HTTPS204 confirmed. Desktop LTE failed before confirmed RIL readiness and CBD startup, with stock ModemManager active afterward. | Sensor, audio and Bluetooth enumeration checked. Desktop LTE startup failed, and #46 SIM-present data remains untested. |
| #46 stock Ubuntu sensor integration | Ubuntu 24.04 IIO Sensor Proxy active. Active GNOME Wayland session had ambient brightness on and rotation lock off. Proxy recognized the accelerometer and returned 341 lux and proximity far. Ordinary-user IIO reads succeeded across all six sensor devices. | Existing desktop integration checked. Fresh physical rotation and brightness changes were not exercised. GeoClue has no compass feed, and the proximity read does not qualify desktop screen blanking. |
| #46 wireless compass reference | Owner viewed live XYZ and calibration in a temporary Wayland window. With USB detached, five reference poses gave 15 quality-3 samples each without overflow. Best proper axis mapping still had about 44° error on a flat pose and 115° when tilted. GeoClue read `HasCompass=false` on its standard compass object. | Physical response and wireless diagnostic verified. Heading accuracy failed. Stock Ubuntu compass publication is disabled. |
| #47 experimental compass | BOOT readback and native start verified. Stock Ubuntu Sensor Proxy discovered the buffered compass. GeoClue's service account claimed and read changing real headings around 63° before and after a distinct warm boot. A temporary Wayland window read the same property. | Standard compass publication active in experimental mode. Absolute heading and tilt accuracy remain unqualified. |
| #47 Compass desktop app | Ordinary desktop user received a live magnetic heading through the on-demand Sensor Proxy relay. The installed launcher opened a real Wayland window and its accessibility tree showed 168.6°. | Launcher and visible live reading verified. Magnetic and tilt calibration remain pending. |
| #47 Qt 5 sensor examples | The Ubuntu Sensor Explorer example loaded its packaged QML and Explorer model in the real Wayland user session. Its rendered Properties rows showed nonzero sample timestamps and actual tilt X/Y in degrees, proximity far, gyro X/Y/Z in °/s, about 101.6 kPa and 40 °C from the barometer, and magnetic azimuth around 105°. The packaged Qt Quick demo also displayed two tilt angles and Far using the configured default backends. | Five live Qt 5 data paths verified. This session exercised proximity far only. Gyro motion accuracy/axis alignment and compass accuracy remain open. The example's Running column may stay false while Properties receives values. |
| #47 Ubuntu hwmon | The stock hwmon consumer exposed one barometer die and two board temperatures through `sensors -u`. Two distinct warm boots reproduced all three readings; the final boot also delivered live experimental compass values with the revised calibration-state policy. | Read-only monitoring and compass coexistence verified. No thermal policy changes. |
| #47 GNSS startup | Own Samsung daemon in a bounded isolated runtime reached IPC FIFO initialization using files on read-only SYSTEM/VENDOR. | Native satellite fix, NMEA and GeoClue integration pending. |
| NFC and fingerprint inventory | Own stock NFC configuration identifies S3NRN82 on I²C. Linux's S3FWRN82 implementation is UART-specific and its Samsung I²C implementation matches S3FWRN5. #48 exposes no I²C controller at the stock NFC address 0x108e0000. Enable/firmware GPIOs come from a PCAL6524 expander on a second unregistered controller at 0x10930000, with a separate shared 1.8 V NFC rail; the stock fingerprint uses secure-mode SPI (Egis ET510). | Board I²C, clock, GPIO expander and power bring-up precede standard NFC service integration. Secure fingerprint transport and enrollment remain pending. |
| NFC PERIC1 bus candidate on #48 | Exact revision 26 SM-G965N stock BOOT and vendor clock tables agree on the USI08 full USI and USI10 dedicated I²C paths. ARM64 DTB compilation, both controller resources and pinctrl phandles, exact gate-table additions and client absence passed. Candidate BOOT unpacked to the identical #48 Linux Image, original outer DT and ramdisk, and new inner DTB. | Build and structural verification only. No hardware bus registration, transfer or NFC tag read qualified. Actual input clock rates and PCAL6524 power/reset remain open. |
| NFC PERIC1 #48 hardware trial | BOOT readback and two native starts verified with both I²C adapters registered. A targeted PCAL6524 read first timed out while Bluetooth used its bit-banged bus on the same pins. A temporary CLKREQ bit change did not help and was restored. With Bluetooth stopped and the mux read back as function 3 on both GPP6 pins, the PCAL6524 returned a live input byte. Clock register readback implies 50 MHz for USI08 and 200 MHz for dedicated USI10. | Dedicated I²C transfer to PCAL6524 verified in isolation. Shared Bluetooth/NFC use, the USI08 clock description, NFC power and tag reads remain open. |
| #48 shared NFC expander and Linux NFC core | Standard gpio-pca953x owned the live PCAL6524 and the trial zrn-bt used GPIO line 7 on the native I²C bus. BCM firmware loaded, BlueZ discovery saw 13 peers, and the old GPIO adapter was absent. The upstream nfc/nci modules loaded and AF_NFC plus generic netlink worked. | Shared expander use and the standard kernel API verified in a live trial. No NFC radio registered. Boot-time integration, S3NRN82 transport/power and tag reads remain pending. |
| #48 NFC boot integration and S3NRN82 probe | A persistent guarded native-expander Bluetooth service started from a distinct warm boot, with a powered BlueZ adapter and the NFC and NCI modules loaded. S3NRN82 at 0x27 NACKed CORE_RESET in a direct transfer and in an ARM64 I²C driver. Readback showed LDO38 set to the stock 1.8 V selector and the VEN/FIRM GPIOs following the commands. CLK_REQ and data IRQ remained low. | Native Bluetooth, shared GPIO and the NFC core persist on reboot. S3NRN82 power/clock delivery at the chip, radio registration and actual tag reading remain unverified. Trial controller driver was removed after its failed probe. |
| #48 S3NRN82 active-low VEN correction | Stock SEC_NFC_PW_ON=0 identified the polarity error. Actual I2C CORE_RESET returned success. The NCI driver registered nfc0, and Linux DEV_UP/START_POLL/STOP_POLL succeeded with the post-wake delay. After a separate warm reboot, nfc0 and powered BlueZ started automatically and the NFC operations repeated. | Controller transport, Linux NFC initialization, polling commands and persistent Bluetooth/NFC coexistence verified. Actual tag detection and content reading await a physical tag. Earlier chip nonresponse was caused by the incorrect VEN polarity. |
| #48 native sensor application integration | Added QAccelerometer with the live IIO scale and board mount matrix. Actual Sensor Explorer displayed timestamped X/Y/Z around -0.15/-0.14/9.53 m/s². The distribution generic.rotation backend returned gravity-derived pitch/roll. Existing tilt, proximity, gyro, pressure and compass passed the same GUI model check. | Stationary acceleration delivery and standard Qt derived rotation verified. Generic rotation yaw is zero; controlled dynamic accuracy remains unqualified. |
| #48 NFC and Bluetooth lifecycle | Ten real DEV_UP/START_POLL/STOP_POLL/DEV_DOWN cycles completed. Two Bluetooth service stop/start cycles unloaded and reloaded its module, discovered the new UART each time and restored a powered BlueZ adapter while nfc0 remained registered. | Repeated lifecycle and coexistence verified. Actual NFC tag content still requires a physical tag. |
| #47 GNSS HAL and hub IPC | Real vendor HAL started standalone GNSS. Longer trials returned a satellite callback and 14 checksum-valid NMEA sentences. The GeoClue service account received all 14 over a private Unix socket. A GeoClue application client was created, but start was denied by the user's location setting. | Receiver data and local transport verified. Valid satellite fix and desktop location pending. |
| #47 GNSS and desktop location enabled | User location preference enabled. The actual GeoClue daemon connected to the isolated NMEA-only source and its desktop test client started. Owner placed the phone with sky exposure for the 205-second receiver trial. That trial forwarded 14 checksum-valid NMEA sentences. | Standard service transport verified. No GNSS fix or GeoClue location object. Temporary GNSS source removed, and desktop location preference enabled. |
| #47 persistent GeoClue GPS source | Real GeoClue client connected to the enabled systemd socket, activated the guarded receiver and received 14 checksum-validated NMEA sentences. Disconnect returned the service to idle. | Installed and enabled on demand. Real latitude/longitude fix remains unverified. |
| #48 GNSS synchronized UTC | The installed ARM64 HAL helper received Ubuntu's NTP-synchronized UTC with a CLOCK_BOOTTIME reference. The handset HAL returned success, then the GeoClue account received 14 checksum-valid sentences in a three-minute observed session. GGA and RMC did not report a fix. | Time-aid delivery verified. A satellite fix, position callback, ephemeris assistance and position cache remain unqualified. |
| #47 flip-cover input | Owner magnet sweep produced GPIO level changes and interrupts on GPA3 line 6, followed by eleven native `SW_LID` close/open pairs and matching logind events. Final state was open with the magnet removed. | GPIO, evdev and logind verified on hardware. A fitted cover and screen or power actions were not exercised. Existing lid policy is ignore. |
| #47 standard Ubuntu battery and charging | UPower exposed the native battery and charger to the desktop DisplayDevice. On USB power, UPower reported present, 99%, fully charged and OnBattery=false, consistent with the live power-supply nodes. | Standard battery reporting on USB verified. Cable removal and charge-rate qualification remain separate. |
| #47 Ubuntu Mobile Network recovery | Pinned nine-partition recovery backup and original private modem receipt proved changes were confined to the permitted EFS ext4 fields. Refreshed the receipt and preserved the old one and working modem data. ModemManager enumerated one internal modem and real SIM; NetworkManager exposed rmnet0 as GSM. Wi-Fi-bound HTTPS204 passed. | Standard desktop modem enumeration recovered. The modem reported EPS searching, packet not attached and a real signal code; cellular data was unavailable in this session. |
| #48 Exynos8 RTC | BOOT readback, native start and a separate warm reboot verified. Ubuntu registered s3c-rtc and exposed /dev/rtc0. The initial invalid calendar accepted a synchronized UTC write, ticked and delivered an awake RTC alarm interrupt. The RTC retained its advancing time on reboot, and systemd timedated read the hardware clock. | Hardware clock, awake alarm and warm reboot retention verified. Automatic RTC/system clock sync is disabled for this trial. Power-off retention and wake from suspend remain unverified. |
| #48 standard Ubuntu mobile data | On a distinct warm boot with the verified modem receipt, ModemManager registered the SIM on its home network and NetworkManager connected rmnet0 as GSM. An uncached IPv4 DNS lookup selected rmnet0, followed by TLS-verified HTTPS204 bound to it. LTE counters increased by RX10/TX13 with zero interface errors; separately bound Wi-Fi HTTPS204 also passed. | End-to-end IPv4 cellular data via Ubuntu Mobile Network verified on this boot. Mobility, IPv6, voice and SMS remain open. |
| Replacement data USIM on #48 NFC trial | The previous running RIL reported SIM not ready after the tray change. The modem detected the replacement after restart. Native boots with refreshed provenance exposed the SIM to Ubuntu and reported EPS searching, nonzero signal and no packet attachment. A separate 60-second warm-boot observation found no cellular bearer; Wi-Fi HTTPS204 passed. | SIM enumeration verified. Carrier registration and IPv4/IPv6 data with the replacement SIM remain open. The earlier confirmed IPv4 trial used a different SIM. |
| #48 NFC desktop service and controls | Pinned upstream neard built and passed all three NDEF/SNEP suites. Its standard ObjectManager exposes nfc0. Ordinary-user D-Bus power and polling commands passed before and after a service restart. A real GTK frontend exercised checkbox/button handlers and all six visible status checks passed. | Power and polling controls installed and verified in a separate NFC launcher. NDEF parsing suites passed upstream fixtures. Physical tag detection and content remain unverified. |
| #48 physical NFC target and persistent clock fix | The initial owner card trial detected nothing. Implemented the stock single-byte vendor clock configuration (0x28, value 0x12) before CORE_RESET. The owner then confirmed recognition and neard published one tag/four records. After an active-tag socket-release fix, three full power cycles each read one tag/four records and final power-off succeeded. The first reboot exposed neard starting before the NFC netlink family; a bounded actual-radio readiness gate fixed that race. A second distinct warm boot automatically started neard and Bluetooth; ordinary-user polling again read one tag/four records, BlueZ was powered and Wi-Fi HTTPS204 passed, with no failed units. | Physical tag detection, NDEF records, repeated active-tag power cycling and warm-boot NFC/Bluetooth coexistence verified for this target. Current boot had zero matching unsupported 0xf3f, receive-error or failed-send messages. No card identifier or record contents retained in Git. Other tag protocols, write operations, payments, emulation and secure elements remain unqualified. |
| #48 wireless GPS observation and desktop test | Owner reported USB removed and phone placed for sky exposure. Commands used its Wi-Fi SSH address and explicitly Wi-Fi-bound HTTPS204 passed. The UDC state still said configured, so it did not independently confirm physical removal. A 300-second guarded GeoClue-socket test received 14 valid NMEA sentences, zero bad checksums, GSA type 1 and zero used satellites; no GSV or position fix. | Wi-Fi-controlled GNSS observation verified. No satellite fix; continuous data and assistance remain open. Only synchronized UTC aid is implemented. No position/raw NMEA retained in Git. |
| #48 startup manager, Maps and GPS Test apps | Installed Ubuntu startup-applications and GNOME Maps; real accessibility frames confirmed Startup Applications Preferences, Maps and GPS Test. The custom GPS GUI showed actual 14-sentence/no-fix data. Dedicated unprivileged test unit and selected-account-only Polkit control passed normal-user start/stop over SSH. A new three-second cancellation emitted final/cancelled summary and unit success/inactive. | App launch, actual diagnostic display and on-demand remote control verified. Missing GSV displays unknown visibility, not a measured zero. This does not qualify map tiles, navigation or actual GPS location. No application was added to login autostart. |
| #48 GNSS daemon crash correction | Payload-suppressed trace found SIGSEGV and native debugging located NdkSensorsInfo → NdkSensorsStart in the optional Android sensor-service path. The private trial XML now changes only hal SensorsEnable=false. A 300-second wireless run produced 3,291 checksum-valid sentences and no invalid sentence, without daemon exit. Supervisor now notices daemon death while HAL stdout stays open; real-child host tests cover that failure. | Continuous reception and the observed crash correction verified. Main Ubuntu IIO/Qt sensors remain active; Android inertial GPS aiding is disabled. Earlier 14-message/no-update observations were not evidence of a running receiver. |
| #48 GNSS LTO assistance | Own read-only gps_psds.conf identified V5 Broadcom sources. Verified HTTPS returned a fresh 124,383-byte file. Root-only cache checks Last-Modified, 24h reuse, own-config hash and blob hash. HAL XTRA init/inject returned zero and receiver lto2.dat exactly matched the cache. The hardened refresh unit passed and hourly freshness timer is active. | Download, cache and HAL delivery/storage verified. Expired/tampered/config-mismatched host cases rejected. Offline and expiry field regressions, SUPL and prior-position injection remain open. |
| #48 satellite fix and GeoClue/Maps | After the owner offered opened-window placement, a new 300-second assisted run produced 4,448 valid sentences, zero invalid, real GGA/RMC fix and GSA type3. GSV per-constellation maximum10 and GGA used maximum8. A separate normal-user GeoClue client then received a location 1.2s old with reported accuracy3m. Maps native current-location action executed with no visible connection/permission error. | Basic satellite fix and standard desktop position delivery verified. No coordinates retained in Git; accuracy is a service estimate, not surveyed truth. Cold-boot/suspend/moving outdoor accuracy, map centering ground truth and navigation remain unqualified. |
| Kernel health reporting | Updated analyzer matched one hub standby warning, one PLL lock failure, one PLL rollback failure, 23 GPIO warnings and four modem QoS notices in the live #44 kernel buffer and journal. Only the kernel buffer retained the boot header. | Warning detection and separate source counts verified. The report still shows open hardware issues. |
| Screen-only background operation | Native #44 running handler matched the repository. Two 8.2 s software display-off intervals, Mutter mode off and CRTC inactive, six IIO reads every ~250 ms and Wi-Fi HTTPS204. Original display and lock state restored, boot and handler process unchanged. | Display-only background operation verified. Physical power-key behavior and Android comparison of battery drain remain pending. |

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


Native48 RTC IRQ-only DT correction (2026-11-20): exactly two inner-DTB flag
bytes changed from NONE to LEVEL_HIGH; same kernel Image/module ABI. A fresh
nine-partition TWRP backup passed and BOOT-only write/readback succeeded after
the previous snapshot correctly failed the EFS identity check. RECOVERY, EFS,
CPEFS, RADIO, DTB and DTBO full hashes matched the fresh snapshot on native boot.
Initial boot and separate warm reboot: invalid RTC IRQ warning0/call trace0,
clock advanced, awake RTC_AF alarm delivered and cleared, HCTOSYS0, retained
RTC time. Sensor/audio/Bluetooth/cover services active, BT powered, NFC
node/neard present, seven IIO devices, sound card and Wi-Fi HTTPS204. This
qualifies RTC awake/warm-reboot operation, not cold power retention or suspend
wake, nor a repeat of physical NFC/audio/profile tests. GPS regression pending.


Native48 secondary GPT repair: full primary/tail snapshots preserved on handset
and host, checked against receipts and independently rebuilt candidate. Empty
reserved20KiB secondary array/header restored; primary byte-identical and25
entries unchanged. Header512/sector4096 correctly distinguished. Initial
post-write CRC/readback and separate warm reboot pass; alternate-GPT warning0,
protected RECOVERY/EFS/CPEFS/RADIO/DTB/DTBO unchanged. RTC warning/call trace0,
Wi-Fi204 and driver/NFC startup pass. LTE private provenance correctly refused
recovery-only superblock changes; exact old/new backup proof and existing
bounded revalidation passed without writing originals/working NV. Current SIM
registration/data needs separate verification. GPS264s output2,852 valid/0
invalid, no fix; interrupted for this reboot, not a completed five-minute test.


Final post-provenance-maintenance boot: all six checked driver/desktop-LTE/NFC
services active, failed units0, actual modem module present, ModemManager enabled,
registration idle and packet service detached. Wi-Fi HTTPS204. This supersedes
the temporary LTE startup failure for service startup only; it does not qualify
current-SIM registration/data. Existing provenance suite41 tests and isolated
maintenance lease/refusal/cleanup tests3 pass. The published wrapper encodes the
successful on-device isolated sequence; source pin/root-path checks were added
for reuse and the wrapper file itself was not used to repeat a provenance write.


Native48 RGB low-current trial (2026-11-20): existing PMIC child only, no parent
reprobe/DT/BOOT update. Guarded input/ABI/BOOT/model/backup checks passed. Three
standard indicator class nodes, max_brightness1. Fifteen physical-output
on/off register checks passed; owner saw blue/red/green blinking. Public
controller test, stop/unload/start/retest passed. Separate warm reboot restored
g965n-led.service and three class nodes; repeat readback passed, failed units0,
RTC/GPT/call-trace/Oops/BUG markers0. This qualifies low-current RGB output and
startup, not brightness calibration, HW blink, GNOME notifications or charging
policy. Reproducible build-only recipe and three existing actual-C/topology
checks pass after reviewing the stale cache-only DTS topology pin.

Haptic remains unqualified. Initial five CMU reads succeeded; a further PLL
read-only diagnostic received userspace SIGBUS and stopped. No clock/PWM/motor
power writes and no physical vibration test were performed. Do not infer motor
failure or a verified PWM rate from that diagnostic.


Native48 haptic board integration: actual26MHz timer source verified by hardware
counter26.06MHz; dedicated APB gate and real gpg1-7 supply/gpp3-1 PWM1, no shared
PLL/BOOT write. Initial boot boostHIGH/PWM2 corrected an earlier rail-off
assumption. Standard FF_RUMBLE100ms and4x200ms output/auto-stop/close-off pass;
IMU Z std202..311 versus baseline3.9..4.1 supports mechanical vibration.
Ordered stop/restart, original GPIO/pad restoration and normal-user device
access pass. First warm-boot device-link warning fixed by targeting controller
parent; final separate warm boot/test has warning/call-trace/Oops/BUG0,
RTC/GPT warning0 and failed units0. Motor settles boost0/bias0/MOTOR_EN0.
Actual patched magnitude function393,216 ASan/UBSan cases and complete fresh
module/tool cross-build pass. No stock waveform/calibrated force/endurance/
suspend/GNOME notification-policy claim. GPS unattended300s regression:
3,279 valid/0 invalid sentences, satellites0/fixfalse at current placement.


Native48 actual DSI Mesa swizzle A/B/A:24 transitions per phase, three fixed
Cairo windows and four warmups. Opening paint p95 picker/grid/repeat:
23.236/23.128/22.297 →10.778/10.835/13.537 →22.519/24.655/22.322ms.
Above16.7ms counts4/4/4 →0/1/0 →4/4/4. Frame-clock dispatch tails remain
17.165/23.628/21.849ms; no presentation-FPS/all-stutter claim. Actual restore
recovered baseline DSO mapping; final accepted child overlay preserved parent
files and survived a separate warm reboot. Actual Shell coherent candidate
mapping and Panfrost DRM fd confirmed. Two GPU readback runs200 frames,
13,107,200 bytes/zero mismatches;256MiB live textures passed. Reboot failed
units0/serious kernel and matching GPU fault patterns0; IIO7, major services
active and Wi-Fi HTTPS204. Fresh native neon source preparation and1,296
swizzle regression cases passed; clean full binary rebuild is a separate step.

Post-reboot desktop compass relay6 finite heading samples passed; direct
D-Bus access denied to root/ubuntu by intentional policy, geoclue HasCompass
true. Sensor supervisor journal error lines0; standard NTP synchronized true.
Original screen-off state restored. Separate clean full build running under
normal-user unit/Nice10/CPUQuota100%/jobs2; first57/1325 no failed compile
markers. Full clean build and its later hardware adoption remain pending.

Current post-reboot modem query: power on/searching registration/no unlock
required, data unverified. RTC/synchronized UTC delta0.53s. Targeted dmesg
RTC/GPT/touch/sensor/P2P IF_ADD timeout patterns0; vendor bus QoS notices4,
CPU capability notices9 remain. No blanket clean-log/all-modules claim.
Clean rebuild latest202/1325 active, compile failure markers0.


Native48 persistent-open feedbackd revealed real haptic idle power bug:
boost1/bias1 despite MOTOR_EN0. Stopped daemon then applied MAX77705-only
lazy-playback power patch. Actual held-open new state0/0/0; three standard
fbcli100ms trials each observed1/1/1 during play and0/0/0 at auto-stop with
daemon still alive. Independent4s rail-cut timers cancelled after verification.
Updated guarded100ms/8192 diagnostic passed on/auto-off/close-off. Production
functions100 held-open cycles and injected power/PWM/start/stop errors passed
ASan/UBSan. Source-pinned optional idle-power module build passed. Serious
kernel patterns0/failed system units0. Consumer enabled after tests; new module
warm reboot, complete GNOME notification linkage and battery savings pending.


후속: clean Mesa 전체 빌드1325/1325·receipt 검증 완료. 새 출력의 실제
Panfrost/Gallium 매핑 확인, readback100프레임/6,553,600바이트 오류0,
256MiB 텍스처 검사 통과. 실행 중인 Shell은 기존 검증 overlay 유지.
이제 새 진동 모듈 재부팅 회귀 시험을 시작했습니다.

Native48 final idle-power warm boot: all major system services and standard
feedback user daemon active, actual idle0/0/0 before first rumble. Guarded
100ms/8192 and standard fbcli actual on→automatic full-off both passed.
Serious kernel patterns0/failed units0. Existing qualified Shell overlay stable.
First early Wi-Fi SSH timeout recovered on retry; no long-term network claim.
This supersedes new haptic module reboot-pending entry above only.


Native48 residual animation review: three restored controls, two qualified
input-QoS comparisons,24 actual DSI transitions each. Per-opening app-grid peak
median controls26.215/23.921/22.837ms versus18.280/21.199ms; grid worst paired
28.059→19.062 and34.768→24.547ms. Long picker frames remain. Pooled p95 is
sample-count-sensitive; added per-opening analyzer and synthetic tests to avoid
false improvements. Notifications are event timing, not scanout/photometric FPS.

Actual input raised349.916/1066→1499.333/2327MHz for500ms then restored.
Separate QA MAX1794MHz remained authoritative during boost, with min/max1794
and original idle minima after expiry; QA removed and prior max2327 returned.
Adopted guarded current-device service active/enabled, next boot unverified.
Owner says current performance sufficient, so no additional tuning/reboot.
Other trials restored: governors/affinity/GPU min/poll/dock; tiling child removed.
Tiling helper passed2,688 exact native cases and100-frame GPU readback/256MiB,
but did not improve full scene latency and was not adopted. First boost run
with zero-flags ID table did not attach and is invalid performance evidence;
explicit EV_KEY/EV_ABS ID flags fixed attachment, real input proof and production
worker/ID-table fault/expiry/wrap tests passed. Final3s minima349.916/1066,
GPU/serious kernel patterns0, failed units0. Whole energy/suspend and zero long
frames are not qualified. Follow-up priority is observed logs, not more tuning.


Native48 log-first follow-up: missing keyring PAM library installed from Ubuntu
packages; actual native dlopen passed, fresh GDM login not replayed. Separate
RGB0007 named-regmap build and guarded module replacement passed all three
low-current register readbacks; core map preserved, named RGB map present,
new duplicate errors0 and LEDs off. This module revision has not had a separate
boot test. Existing LED boot evidence is retained at its original scope.

Final guarded read-only full-ring collection retained boot header,978lines,
error-priority57/warnings68; journal378lines lacked early header. Actual CPU
register differences52+unsupported notice1, hub reset unconfirmed1, modem
vendor QoS4. Call trace/SError/GPU PLL lock/rollback/GPIO direction warning0;
separate severe-kernel/GPU-fault searches0, failed system units0. Bluetooth
adapter1/poweredtrue but SAP interface absent. GDM remote-display assertions
and automatic-login keyring warning remain. No all-feature/clean-boot claim.
Host production input-QoS ASan/UBSan test,4 overlay inventory tests,3 opening
analysis tests,2 Mesa builder tests and source/patch pin checks passed.

Software Center/PackageKit/AppStream and official Chrome ARM64 installed;
package installation is not browser page/catalog/install-flow qualification.
Owner moved the ChatGPT white-page investigation to another context; stopped
that investigation without clearing profiles or changing login/autostart.


Native48 owner warm reboot: exact model/BOOT/protected backup preflight passed;
input service auto-started/enabled, receipt matches new boot. Kernel uinput
neutral Shift raised minima1499.333/2327MHz, restored349.916/1066MHz, maxima
unchanged. QA native Werror compile passed, temporary input module/device/timer
removed. Earlier compositor virtual input was not kernel-handler pass evidence.
Named RGB auto-start: both maps present, boot duplicates0, three on/off readbacks
passed/all off. Haptic100ms/8192 on/auto-off/close-off, Wi-Fi-bound HTTPS204 and
finite standard IIO reads passed. Accuracy/cold boot/suspend not requalified.

Full ring1,024lines/error57/warn68; journal423lines lacks early header. CPU52+1,
hub reset1, modem QoS4 persist; call trace/SError/PLL/GPIO/action/chanspec0.
No real modem bus provider/ECT table: no speculative clock patch installed.
Location enabled, authorized GeoClue GNSS session active. One failed GNSS
instance rejected a non-GeoClue peer as designed; preserved, not a receiver
crash or an all-failed-units-zero result. Document portal remains excluded WIP.


xgps integration native48: package installation, ordinary-user launch, live
NMEA221/TPV160 records and loopback-only GPSD listener verified after startup
delay. GeoClue peer ACL retained, viewer has no command path to HAL. New bridge
boot persistence and outdoor satellite/fix accuracy remain untested.

Final xgps check: connected-port2948 window confirmed through accessibility,
ordinary-user launcher active,145 live TPV messages received with mode1 (no
position fix). Stock launcher was shadowed only by a per-user xgps.desktop
pointing to the connected wrapper; package launcher preserved. The bridge
restart disconnected an earlier viewer; launched a new connected window and
verified delivery after receiver startup. No satellite-fix claim.


Native48 location integration: two guarded normal reboots, no kernel/image
change. CP0811 returned20 LTE records while EPS2/searching. New MM GetCellInfo
returned20 LTE/1 serving; two exact private SIPC→D-Bus identity matches pass.
Standard source1 nonempty, location disable-clear/re-enable-restore pass.
Other radio types/signal units, external RF freshness and registered1/5
comparison unverified. BeaconDB/submit-data=false preserved. Full ARM64 build
and final clean plugin rebuild plus49 host tests pass.

GPS authorized window181s1699 NMEA/1233 TPV; detailed180s1687/1225, mode1, no
GSV/HAL-visible satellites/fix. Final45s207/148 mode1. Standalone/start/UTC/
XTRA-init0. Owner clarified location prevents satellite reception: environmental
limit, not a proven receiver/driver defect. Favorable-location fix is pending.
Initial GPSD observer without an active location client is not RF evidence.


Fallback follow-up: authorized location request enabled MM source1 on demand,
GeoClue accuracy25000m. Cell-specific coordinate lookup success is unverified;
coarse network estimate must not be labelled a GNSS/cell-position pass.


## 2026-11-21 — GNSS start-position assistance

Native Bionic build +21 host GNSS tests pass, including actual C parser and
callback-slot ASan/UBSan tests. Initial candidate's return0 was not a pass:
no NMEA/worker245, private debugger confirmed missing extended request callback.
The corrected104-byte persistent callback table handled a real request and
180s delivered1688 NMEA/1225 TPV, mode1/no fix, latest GNSS-instance exception0.
Standalone/start/UTC/position/XTRA-init/inject0, XTRA124383bytes. Old-source
post-recovery241s control2348/1706; early no-seed control was confounded by
stale trial artifacts and is not isolated evidence of seed failure.

Root cache0700/files0600, network-only record;671s-old sample refused, fresh
network25km prepared1.14s. Watcher automatically active after earlier reboot;
mode1 never created the GNSS cache. Corrected session clean shutdown left0
known trial artifacts before ordinary reboot.
수정 HAL 일반 재부팅 후 모델/#48/BOOT/보호 백업/실행파일 핀 재확인.
센서·GNSS 소켓·GPSD bridge·캐시 서비스 자동 active. 재시험91초에서
NMEA687/TPV498, 위치 요청 콜백1회, 해당 부팅 GNSS 예외0 확인.
시작/standalone/UTC/위치/XTRA init/inject0. unit 검증 통과, 배포된
serve.py/seed.py 소스 해시·0600 일치. 위성0/mode1이며 새 fix 증거는 아님.
No new satellite fix or TTFF improvement claim. Real fix cache capture/reuse,
offline/expired assistance field test, SUPL and open-sky accuracy remain pending.


## 2026-11-21 — Same-place Android satellite fix comparison

Same-place control is owner-reported plus screenshot:4 signals/2 in use,
strength21–27, No Fix in the image. Environment-only conclusion withdrawn.
S9+300s2996 NMEA/2177 TPV,0sat/mode1; filtered180s1677/1217 also no fix.
Independent network-only request replay exercised (two position inject0,
request replay1),301s3018/2193 still no fix. Current26 host GNSS tests pass;
actual C parser and callback independence/repeat tests under ASan/UBSan.

UTC/XTRA candidate181s1699/1233 with request counts0/0; ready-time one-shot
181s1698/1232, API0 but no metadata/RF improvement. Both extras removed.
Native reproducible final network-reply helper d1c926ca... installed with exact
model/BOOT/backup/pin checks, protected partitions untouched. New-code reboot
regression is not yet qualified.

Public receiver-status tool60s32 STA/32 UNC, matched common version9 layout,
tPeF/TimeSource0/ephemeris0/field5=4294.967/F. Interpretation against supplier
version10 is inferred. Raw payload/position/date/IDs not emitted. Tracing attempt
was not a valid RF measurement; five known leftovers preserved under verified
idle ownership. Final clean60s356 NMEA/257 TPV, mode1/0sat; deployed source
hashes match, no temporary diagnostic config/logger/ptracer. USB still configured
and owner cannot unplug currently. No root cause/GPS fix/TTFF pass claim.


## 2026-11-21 non-GPS follow-up (in progress)

| Check | Result / limit |
|---|---|
| Wi-Fi scan regression | Three LastScan changes;15/23/25 APs, station connection retained, interface-bound HTTPS204 each, new escan timeout0. Historical timeout not fixed/proved. |
| BT/audio/NFC software readiness | Powered BlueZ with A2DP/AVRCP/HFP UUIDs, PipeWire/WirePlumber active, neard active and one NFC device. No new peer/tag physical validation. |
| USB power / screen-only load | Actual500mA gadget and charger cap. Ordinary-user35s screen-off: current reversed positive and status Charging; original mode restored. No current-limit write. |
| Charging LED initial native-trigger trial | Failed to follow real status reversal: red remained0 while battery Charging. New UPower bridge installed but not yet qualified/enabled at boot. |
| UPower Refresh diagnostic | UnknownMethod on an enumerated device; display mode restored, not counted as transition pass. |
| CPU/GPU thermal presentation | Existing private TMU policy/cached temperatures present; standard CPU/GPU hwmon export absent. No new kernel built or installed. |

UPower bridge real transition passed: charging red1 by26.6s, later discharging
red0. Lifecycle first test failed early-start signal race; fixed readiness and
cleanup, retest pending. Screen woke at32.7s during48s sample; cause unconfirmed.


Final qualification supersedes the pending bridge rows above: lifecycle stop/
restore, restart, manual-owner preservation and warm-reboot auto-start passed.
Exact source/unit match; model/#48/BOOT/protected backups rechecked.48s screen-
off repeat stayed mode3, Charging12.6s then UPower/red1 by22.7s; later actual
Discharging/red0 and LED register enable0. Full/green and USB-unplug pending.
Fresh ring956lines/early header present; CPU52+1/hub1/modem QoS4 persist; targeted
calltrace/SError/GPU PLL/GPIO/escan/RGB duplicate0. New boot failed units0,
ALS131lux/7 IIO devices, Wi-Fi HTTPS204. Modem21cells/1serving, registration
searching: cell read qualifies, current LTE data does not.


## Vehicle power-on — 2026-11-21

| Check | Evidence / limit |
|---|---|
| Full shutdown then USB power | Owner reports Ubuntu does not boot. Current installation does not qualify automatic cold power-on. Attach screen/kernel entry not yet observed. |
| Current read-only access | Exact model/#48/BOOT/protected-backup guard PASS, Ubuntu reachable/charger online1, pstore0 files. Not a cold-attach trial. |
| Source review | No charger-only branch in shim; embedded DT replaces incoming FDT. Existing reset/recovery magic and normal service autostart do not prove cold USB boot. No device change or fix installed. |

See [vehicle power review](VEHICLE_POWER.md) for the pending physical evidence
and bounded test. GPS remains deferred; camera/fingerprint excluded.


## 2026-11-23 — Charge recovery after reported reboot loop

| Check | Actual evidence / limit |
|---|---|
| Fault state | USB online1, CHG_EN reflected as inhibit-charge, battery0%/3.08–3.20V/net discharge,22C. Low-voltage explanation likely; exact reset cause not proven. |
| Guarded restoration | Owner request, exact model/#48/BOOT/protected backups checked; only charge_behaviour=auto, private before/after receipt. |
| Actual charging |5–20s charger and battery Charging, net+60..98mA, average+57mA, voltage3.225V. Input500mA/charge450mA/CV4.2V unchanged. |
| Still unresolved | Why CHG_EN became0, charging endurance/reboot/full behavior, exact repeated-reset cause. Prior kernel coverage incomplete; old archived SError not attributed to new incident. |


## 2026-11-23 — Android charge policy candidate (not deployed)

| Check | Result / limit |
|---|---|
| Public reference | Exact Samsung/Lineage commit and charger/battery/ADC/common/DT hashes pinned; exact owner Korean policy still not compared. |
| Intent ownership | Actual production C with faultable regmap: accepted enable/inhibit, failed writes preserving intent, startup rejection, hardware-bit loss distinct from intent, existing properties8tests PASS. |
| Source migration | Prior reviewed charger SHA6df1e5a... accepted; unknown source drift rejected. |
| ARM64 compile | Driver C-object PASS. Initial plural devm API corrected. Full external module NOT linked: qualified Module.symvers missing; no bypass. No full new kernel or hardware boot. |
| Current hardware | Read-only0%/22C/3.314V/+63mA average, Charging/auto. Sensor unit failed before readiness, root IIO devices0. No restart or write this task. |
| Android parity | NOT complete: real battery/USB/charger ADC, thermal/swelling/full/recharge/cable/safety-time policies and hardware qualification remain. Candidate not installed. |


## 2026-11-23 — charging ADC qualification / latest

| 항목 | 결과 | 범위/남은 검증 |
|---|---|---|
| ADC v3 raw | 실기 PASS: 5rows×channels4/1/3/11 | bounded 진단만; 상시/절전/재부팅 미검증 |
| ADC cleanup | 실기 PASS: 모듈 제거·clock/controls/IRQ type 동일 | gate/PLL/rate 쓰기 없음 |
| Wired calibration | original BOOT rev26 3종과 공개 battery/USB/charger tables 일치 | wireless variant 미선택; 절대 온도 외부계기 대조 미실시 |
| 변환 | receipt37.7/35.5/39.9C; 전체 구간 C arithmetic·invalid/freshness tests PASS | live thermal consumer/충전 정책 미연결 |
| Charge fault | CHG1/charge6/battery2/input3/lock0 실제 확인 | 최초 원인 미확정; 영구 battery failure 판정 아님 |
| Input reattach | 사용자 USB10초 재연결 후 charge1/battery4/ChargingGood/net+80–122mA | 해당 발생 건 해제; 자동 software recovery/장기충전 미검증 |
| Build/host checks | 3모듈 compile+modpost+link, ADC/temperature5 + charger8 tests PASS | 새 BOOT/커널 설치 없음; build를 boot 성공으로 표시 안 함 |

이 기록은 앞선 low-battery Charging 및 이후 중단을 모두 보존하고 최신
재연결 복구로 갱신합니다. Android 동일화/완충/재충전/상시 온도 정책은 미완료.

재연결 후 추가30초4표본: Charging/Good 유지, 마지막3.716V/평균+236mA.
일시 부하 방전 표본 존재; 지속/완충/재부팅 시험과 구분합니다.
