# G965N GPU investigation and acceptance

Panfrost hardware rendering is active. CRC-disabled rendering passed bounded
reboot tests, but **memory-pressure handling and long stability remain open**. See VALIDATION.md and
CHANGELOG.md for actual device evidence. Do not use a glmark score or successful
kernel build as proof of correctness. No proprietary GPU library is published.

## Distinct open failures

- DATA_INVALID / JOB_BUS exceptions from interactive desktop clients.
- Job-slot0 scheduler timeouts during the complete33-scene GLES sequence.
- BO backing allocation failures during desktop use, despite free high RAM.
  The port's all-BO DMA32 restriction is a candidate contributor; errno and a
  controlled allocation-policy comparison are needed before claiming causality.
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
