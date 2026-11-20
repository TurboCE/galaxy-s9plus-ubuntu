# SM-G965N flip-cover input

Build the optional module against the exact running G965N kernel with
`CONFIG_KEYBOARD_GPIO=y`:

```sh
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" M="$PWD/experiments/cover" \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- modules
```

Place the module at `cover/g965n-cover.ko` in the private module package.
Use `scripts/g965n/package-experiments.py --features cover` with the exact
kernel output and installed BOOT image to write its receipt. After the
model, backup and operator checks, use
`deploy-drivers.py --package PACKAGE --enable-cover` on the handset.
Start the resulting `g965n-cover.service` to load the module now. The
receipt also guards the enabled startup unit on later boots.

The revision 26 stock tree identifies GPA3 line 6 as the flip-cover input
and GPA0 line 2 as a separate accessory input. Only GPA3 line 6 is offered
to Linux GPIO keys as an active-low `EV_SW/SW_LID`. The separate
accessory input is available through the diagnostic only. The module
contains no cover power policy. Ubuntu logind uses its current policy
when it receives the switch state.
