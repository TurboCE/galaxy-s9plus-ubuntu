# G965N Shannon modem port — compile stage only

Vendor sources originate in the LineageOS Exynos9810 kernel and GPL-labelled
mainline adaptations in ztOS. SOURCES.json records source paths/hashes. Original
Samsung notices remain. The unlabelled project-specific GPL-3.0 compatibility
header was not copied; g965n_compat.h and empty legacy include adapters are
GPL-2.0-only code for the Linux 7.1 APIs used here.

Full g965n-modem.ko linking passed with the current experimental kernel headers.
This does **not** mean modem registration, SIM recognition or LTE works.

## Current restrictions

- Initialization is blocked by default, including before shared-memory lookup.
- The overlay is deliberately empty and rejected even if enable_g965n=1 is set.
- G965N memory layout, mailbox/GIC and revision must be matched before generating it.
- No module is loaded at boot or installed into the rootfs by these experiments.
- Vendor bus QoS is unimplemented, reported once, and not a performance guarantee.
- The zero-copy path remains disabled; Linux networking uses the copying path.
- Firmware, EFS/CPEFS and Android vendor executables are not redistributed.
- Any future modem boot daemon must use a private working copy of EFS; do not
  mount the real identity/calibration partitions writable as an experiment.

## Actual port changes

- Replace removed timer/time/wakelock/SMC interfaces with Linux 7.1 adapters.
- Use eth_hw_addr_random(ndev), not a write to the now-const dev_addr pointer.
- Read the reviewed board revision from DT instead of removed integer GPIO APIs;
  fail on a missing/out-of-range revision rather than silently choosing zero.
- Keep the original mailbox internal headers distinct from its public UAPI.
- Build/link without KBUILD_MODPOST_WARN or ignored unresolved symbols.

Compile only, with the prepared experimental kernel volume mounted at /build:

```bash
make -C /build/src/mainline O=out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  M=/src/experiments/modem modules
```

Hardware validation sequence: review/generate G965N overlay, prepare OF overlay
support, verify IRQ/shared memory, then controlled manual load after USB SSH is
reliable. Boot the modem using own-device firmware and private NV working files,
then test status/control. An active SIM can be inserted later for LTE data tests.
There is no ready-to-load modem package or successful on-device result yet.
