# G965N BCM4773 sensor-hub transport

GPL-2.0 Broadcom transport and explicitly licensed board/compatibility sources
are pinned in SOURCES.json. Original copyright and licence notices remain.
The stock G965N tree confirms BCM4773 on SPI 0x13ac0000, gpa1-7 host request,
gph0-5 MCU request, gph0-4 MCU response and gph0-0..3 SPI pins. Sensors depend on
this hub and a vendor daemon; enabling IIO alone cannot make them work.

Changes made here:

- Require star2lte and explicit enable_g965n=1 before hardware access.
- Remove all embedded patch includes; request g965n/bcm4773-patch.bin locally
  before changing power/GPIO. No firmware bytes or firmware headers in Git.
- Bound reads against the runtime firmware size, with negative-offset checks.
- Propagate BBD node-init failures; refuse an unbound SPI device and guard
  partial teardown of unregistered driver/misc devices.
- Initialize work before error cleanup can cancel it.

Build with S9_EXPERIMENTAL_SENSORS=1; full module linking passed. To obtain the
patch from your own original BOOT backup, run extract-hub-patch.py STOCK_BOOT
OUTPUT. This handset's record passed format/payload-length checks and matched
the reference Android10 patch. Keep the output private and install locally at
/lib/firmware/g965n/bcm4773-patch.bin. The original C-string terminator is kept.

This is not an end-to-end sensor implementation yet. The owner's vendor lhd,
its Android runtime/configuration, SSP decoding, coordinate transforms and
Linux sensor integration still need validation. No accel/gyro data measured.
Do not automatically load this transport or start the closed daemon at boot.
