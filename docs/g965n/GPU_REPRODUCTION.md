# Bounded GPU timeout reproduction

Run on the native SM-G965N Ubuntu graphical session as its desktop user after
verifying the exact BOOT/kernel receipt. Close the application overview and
keep the session unlocked and display awake. Do not overlap modem boot tests,
another GPU benchmark or kernel updates. The validator takes the shared GPU
test lock and temporarily inhibits desktop idle; it does not unlock the session
or change clocks, voltage, PM, module parameters or persistent desktop settings.

The previous private three-scene reproduction is now available directly from
the tracked source:

```bash
python3 scripts/g965n/gpu-validate.py \
  --profile targeted --size 1440x2960 --mesa-debug nocrc --timeline \
  --output "$HOME/.local/state/g965n-gpu-targeted-$(date +%s)"
```

It runs interleaved mapped-buffer updates, the low-complexity fragment-function
scene, and the first fragment/vertex-loop scene for eight seconds each, with a
45-second command deadline and five seconds of subsequent fault observation.
The expected scene names and parameters must all complete in order. Missing,
duplicated or partial scene output fails. It does not require or execute the
independent readback program, and it does not substitute three scenes for the
full profile's 33-scene qualification. `--fifo` explicitly adds the existing
three-scene presentation check if needed.

`--profile full` remains the default: the independent 128x128/100-frame readback program, all 33
one-second glmark2 scenes, and optional FIFO checks use the original deadlines.
For example:

```bash
cc scripts/g965n/gpu-readback.c -o /tmp/g965n-gpu-readback \
  $(pkg-config --cflags --libs egl glesv2)
python3 scripts/g965n/gpu-validate.py --profile full \
  --readback /tmp/g965n-gpu-readback --size 1440x2960 \
  --mesa-debug nocrc --fifo --timeline \
  --output "$HOME/.local/state/g965n-gpu-full-$(date +%s)"
```

The full profile requires33 complete FPS/FrameTime rows with finite positive
values, as well as the final score and no matching kernel faults. Scene
announcements or skipped/zero/malformed rows alone cannot qualify. This checks
the expected default workload's completion, not every possible GPU operation.

Keep the output directory private. `result.json` records the selected profile,
expected and observed completeness, requested/reported surfaces, actual kernel,
settings and new kernel faults. A high score or 61fps does not override faults.
Also inspect display counters in `settings_before`/`settings_after`:
`irq_latch_check_timeouts` counts100us generation-certification rejections,
not necessarily a failed50ms hardware flip. A positive delta needs separate
interpretation even when the bounded rendering/journal check passes; it is not
proof of flawless presentation or, by itself, proof of a missed frame.
Timeline capture uses nonblocking reads with a fixed deadline, kills the command
process group on failure, and waits for the direct child during cleanup. Silent
commands and output without a final newline cannot extend the deadline. Exit
124 and `QUALIFICATION_TIMEOUT` identify a timed-out command; the overall
qualification exits 2 on a failure.

For an explicitly authorized modifier diagnostic, add `--wayland-protocol`.
Only the glmark child receives `WAYLAND_DEBUG=client`; its complete stderr goes
to the separate private `targeted.wayland.log`, `scenes.wayland.log` or
`fifo.wayland.log`. Stdout remains separate so a trace arriving during an
unfinished scene line cannot corrupt scene parsing. Both pipes share the same
deadline and cleanup, including silent stderr, partial lines and large traces.
`--timeline` remains optional and records stdout receipt times only.

This option never changes the parent environment or enables tracing on the
readback program. Without the option, existing environment inheritance and
combined output behavior are unchanged; a pre-existing caller `WAYLAND_DEBUG`
is not silently removed. The receipt records the diagnostic scope and log file.
Tracing adds overhead, so compare modifiers rather than benchmark scores.

Match `zwp_linux_buffer_params_v1.add` modifiers to buffer creation, surface
attach and commit. An explicit modifier proves the **presented wl_buffer**
layout. `DRM_FORMAT_MOD_INVALID` does not prove linear layout. Even explicit
linear presentation may come from an intermediate copy and need not describe
the original render target. Setting `PAN_MESA_DEBUG=noafbc` alone likewise does
not prove the absence of externally supplied AFBC modifiers.

`--fullscreen` asks glmark to use fullscreen instead of `--size`; the receipt
then records the request as `fullscreen`. It leaves the independent 128x128
readback and all deadlines unchanged. Verify actual reported/protocol buffer
dimensions rather than assuming the compositor accepted the request. A
window requesting 1440x2960 produced mostly1440x2896 buffers after decoration
configuration, so that window test alone does not cover steady full-height
rendering. Fullscreen is an explicit additional experiment, never a default.

`timeline.jsonl` stores command start/finish and received-line UTC/monotonic
times. glmark2 is line-buffered through `stdbuf`. These are **output receipt
times**, not GPU job submission, start or completion timestamps; do not assign
a kernel timeout conclusively to a scene from them alone. Raw timelines,
kernel logs, GPU dumps and experiment receipts must not be committed. Only the
reproduction code and sanitized findings belong in Git.
