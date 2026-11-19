# G965N GPU investigation and acceptance

Panfrost hardware rendering is active. CRC-disabled rendering passed bounded
reboot tests, but **memory-pressure handling and long stability remain open**. See VALIDATION.md and
CHANGELOG.md for actual device evidence. Do not use a glmark score or successful
kernel build as proof of correctness. No proprietary GPU library is published.

## Distinct open failures

- DATA_INVALID / JOB_BUS exceptions from interactive desktop clients.
- Job-slot0 scheduler timeouts during the complete33-scene GLES sequence.
- BO backing allocation failures during desktop use, despite free high RAM.
  The all-BO DMA32 restriction reproduced ENOMEM at768MiB. AArch64 high-bank
  allocations pass1024MiB internally, but unrestricted display exports trigger
  DECON swiotlb failures. Private/shared allocation separation remains open.
- Perceived desktop stutter; actual presentation pacing needs measurement.
  GPU3D rendering does not establish hardware video decoding (a separate block).

The image now sets PAN_MESA_DEBUG=nocrc to avoid the reproduced CRC-path hang.
Two full suites passed, including warm reboot and27 G3D power cycles.
Keeping the GPU domain powered, fixing its clock at260MHz, disabling flush
reduction, or disabling AFBC for one test client has not established a repair.
Do not enable these as unexplained global defaults. Sync mode is diagnostic,
not a validated desktop solution.

## Repeatable native test

Install the distribution's `glmark2-es2-wayland`, compiler, EGL/GLES development
headers. Run as the local desktop user with an active Wayland session:

```sh
cc scripts/g965n/gpu-readback.c -o /tmp/g965n-gpu-readback -lEGL -lGLESv2
python3 scripts/g965n/gpu-validate.py \
  --readback /tmp/g965n-gpu-readback --mesa-debug nocrc --output /tmp/gpu-nocrc
```

Use a new private output directory for each run. The runner prevents overlapping
instances, records the exact kernel and GPU settings, requires the physical Mali
renderer, checks100 exact readback frames and all33 scenes, and evaluates a
cursor-bounded kernel-log delta including cooldown. Timeouts or GPU fault lines
fail acceptance even when glmark prints a score. Raw logs/dumps stay private.
For a one-client compression comparison use `--mesa-debug noafbc`; this does not
change GNOME's environment. The runner does not flash or change system settings.

## Allocation-policy diagnostic kernel

Source a3f3c66 adds `panfrost.s9p_lowmem_bos` (defaultY, preserving prior behavior).
It affects only new Panfrost allocations. It does not migrate existing buffers,
change DECON's address width or assert that arbitrary high-address imports work.
Timeout owner and BO backing errno/size diagnostics are also included.

An unrestricted allocation trial must verify DECON imports, visible output,
readback, all scenes and kernel errors. Restore the switch/reboot or roll back
BOOT if scanout regresses. Only a tested configuration belongs in the installation
recipe. Kernel-only writes still require the model/backup/consent checks in
INSTALL.ko.md; RECOVERY/EFS/CPEFS/RADIO/USERDATA are preserved.

A qualified result also needs interactive browser/compositor use, concurrent
clients, allocation churn, idle/power cycles, thermal load and reboot persistence.
A short clean interval establishes only that interval, not all GPU behavior.

## Browser and pressure checks

Serve browser-gpu-test.py --output PRIVATE_RESULT.json and open its loopback
URL on the handset. It compares120 WebGL frames; Firefox can mask the exact
GPU model, so pair it with the native hardware-renderer evidence. Stop the
controlled test browser/profile afterward; do not overwrite the owner's profile.

The readback binary accepts --pressure-mib32..1024 (space-separated argument).
It retains that many MiB of nominal texture data, samples every texture, runs
the normal exact test, then checks every retained texture again. Run under a
bounded timeout, record kernel errors and keep other clients/settings comparable.
On#8,768MiB failed allocation with the original policy; unrestricted allocation
corrupted output. It is unsafe to set s9p_lowmem_bos=N as a default at this stage.

## AArch64 pressure result and display-export qualification

Kernel#11 uses AARCH64_4K tables on the Exynos9810 match and passes1024MiB
retained GPU texture readback with unrestricted allocations and nocrc. This does
not qualify the desktop: real display clients also caused DECON `swiotlb buffer
is full` errors. DECON still has a32-bit DMA address constraint. The validation
runner previously missed these lines; its acceptance regex now includes them
with a regression fixture. Earlier GPU-only passes must not be interpreted as
clean display-export passes.

Runtime lowmem was restoredY. Source now restoresY even on a previously patched
build tree; #11's installed BOOT still defaultsN until replaced, so reboot
persistence is not repaired by this source change alone. The next approach must
keep display-exportable BOs low while permitting verified private GPU BOs high.
Do not infer exportability from BO size or indiscriminately enable high RAM.

Kernel#12 deployed with fresh backup/readback and native boot: lowmemY persists,
full33 scenes plus100 exact frames pass with0 matching interval errors. Owner
reports the physical black shapes gone. Reboot/default changed together; the
artifact's precise cause remains unisolated. Whole-boot optional regulator/probe
messages and desktop frame pacing remain separate open checks.

## Real desktop animation profiling

A kernel log without faults does not establish smooth presentation. GNOME46
exposes org.gnome.Sysprof3.Profiler at /org/gnome/Sysprof3/Profiler on its own bus.
Use `shell-profile.py --output PRIVATE.syscap --seconds 25` as the desktop user
with its session bus while the owner opens/closes the overview. This uses the
normal profiling API; it does not bypass ShowApplications access restrictions.
The initial automatic exercise was denied, so actual profiling used owner input.
Install distribution python3-gi and libsysprof-capture-4-dev to capture/analyze.
Compile `shell-profile-marks.c` with the pkg-config flags in its header, then pipe
its output into `shell-frame-summary.py`. Upstream library/headers are supplied
by the OS package under their own notices, not vendored/relicensed/published here.
All raw captures stay private. No frame messages/window titles are printed by
the marks helper. Mark durations measure particular compositor operations,
**not FPS**; idle gaps must not be counted as dropped animation frames.

On#12, an owner-driven25s capture recorded257 FrameClock dispatches: median0.2ms,
p95=34.74ms, max240.52ms. Paint-view p95=29.34ms, framebuffer-swap max157.92ms,
and an input-event path max229.25ms. These exceed a60Hz16.7ms budget at times;
the owner's rough-animation report is therefore an open performance issue,
not dismissed as normal or proved fixed by a high glmark score. This first trace
does not isolate cold caches, memory pressure, scheduling and driver latency.

On native #44, a temporary upstream uinput module sent the configured
Super+A shortcut and Escape in an unlocked session. The built-in profiler
captured five opens and five closes, and the overview state was checked
after each transition. In the first 800 ms after opening, five of 65 paint
marks exceeded 16.7 ms. Paint p95 was 18.378 ms and frame-clock dispatch
p95 was 24.596 ms. Closing paint p95 was 4.280 ms. The run restored the
desktop and unloaded the temporary driver. These durations are evidence
of actual app-list frame-budget pressure, with scanout cadence unmeasured.

Three native #44 A/B/A trials compared app-list opening under the
existing policy, a bounded intervention, and the restored policy.
The big-cluster performance governor reduced paint p95 from
21.271/22.636 ms in the two controls to 17.790 ms, with the sampled GPU
at 260 MHz. A 455 MHz GPU floor left dispatch p95 near 30.5 ms and a
main-thread utilization clamp gave mixed results. Each trial still
had four opening paints over 16.7 ms. The measured evidence favors
investigating the CPU-side opening workload, with the original power
policy restored on the handset.

Native #44's window picker and app grid both exceeded the frame budget
under their actual configured shortcuts. Opening paint p95 was
18.062/18.645/21.097 ms in the window-picker/app-grid/window-picker
comparison, with four paints over 16.7 ms in each phase. In the
earlier CPU comparison, input dispatch and painting took more time
than framebuffer swapping. These measurements direct investigation
toward shared overview transition work; they do not identify its
specific CPU stack or measure physical scanout.

Userspace perf sampling of the GNOME Shell main thread then resolved
a common Mesa texture upload path. `convert_ubyte` accounted for
7/73 window-picker and 9/86 app-grid opening samples. All 43 hits over
the whole trace mapped to the byte-to-byte conversion branch reached
from Cogl texture allocation. A standalone ARM SIMD prototype passed
byte-accurate tests on the phone and reduced the synthetic conversion
time. No integrated Mesa or actual-animation result follows from
this standalone test.

Kernel#13 additionally corrects the board's ACPM-owned supply description.
The whole-boot missing-mali-regulator error is absent. Another full33-scene/
100-frame exact pass reports0 matching errors.50ms sampling observes260/455/
572MHz with the existing950mV setting and runtime power cycling; no forced
high-frequency or always-on default. This does not close the animation or
private-high/shared-low allocation issues.

## FIFO presentation acceptance

Run gpu-validate.py with `--fifo` to add three4s512x512 FIFO/vsync scenes and
require at least54fps in every scene on this port's fixed60Hz output. The runner
also requires complete scene labels, physical Mali rendering, successful exact
readback/full33 scenes and no matching interval fault. A large unconstrained
benchmark score cannot hide a half-rate presentation path. The regression tests
include the actual31fps failure pattern, incomplete and duplicated scene labels.
Kernel#13 baseline was31fps in each FIFO scene. On the same#14 kernel, old-policyN
gives31/31/31fps while latch-policyY gives60/61/61fps. The complete acceptance
runner then passes all three at61fps, exact readback/full33 scenes and0 matching
interval faults. Completion is sent only after shadow latch AND counted FRAME_START;
otherwise the old armed-event fallback retains the vblank reference. The runtime
switch/counters support reproducible diagnosis. Owner reports improvement with
residual stutter, so full desktop animation smoothness remains unqualified.

## Visible desktop is required for FIFO tests

The runner now takes a temporary GNOME session idle inhibitor during validation
and checks that the display is on, the screen shield inactive and overview closed
before starting. It never unlocks the session or changes persistent idle policy.
A hidden/locked surface can stop FIFO frame callbacks without any GPU fault;
this must be reported as an invalid/incomplete test, not shader corruption.
End-state display/lock values and the inhibitor policy are recorded in results.
Run tests as the desktop user. If a privileged A/B helper shares the runtime lock,
keep that lock owned by the desktop UID; do not disable the lock or chmod it world-
writable to work around an ownership mistake. DECON parameters/counters are now
included with other settings so the exact presentation policy is visible.

Kernel#15 unlocked/awake full qualification passes with61fps in all FIFO scenes,
exact readback/full33 and0 matching faults. Same-kernel N/Y/N process polling
reads43559/1463/43473 while maintaining59..61fps. A source-review generation race
remains a separately prepared candidate until its own compile/boot test; bounded
passes must not be described as a proof that every possible timestamp race is gone.

On native #44 with the accepted Mesa profile, a full-screen, windowed and
repeated full-screen FIFO sequence passed all nine scenes at 60–61 FPS.
The same test started 13.25 seconds into a distinct warm boot and passed
at 58–61 FPS. The early boot had zero DECON latch wait timeouts, and
neither observation produced a new matching GPU/display fault. The
previous 11 FPS run was not reproduced; the scene results do not qualify
GNOME overview animations or long video playback.
