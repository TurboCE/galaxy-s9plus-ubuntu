# MAX77705 child-node warning audit (no topology change)

The native #21 log reports missing child `of_node` for RGB, charger and haptic.
The reviewed MFD source instantiates all three as platform cells. The board DT
has a PMIC at I2C address `0x66` without those child nodes and a separate charger
I2C device at address `0x69`. The MFD core warns when a platform cell's declared
compatible cannot be matched below its parent.

These messages do not all have the same remedy:

- The current charger implementation is registered with `module_i2c_driver`,
  not a platform driver. Its existing `charger@69` DT node supplies the real
  charger driver. A second platform child named `max77705-charger` is an
  architectural mismatch; adding an empty charger node under the PMIC would
  only silence matching, without binding that I2C driver. The real I2C node and
  its verified charging path must be preserved.
- RGB is a real platform child, but its LED topology/channel properties must
  be described correctly. A compatible-only empty child does not establish a
  functional LED configuration.
- Haptic is a real platform child, whose binding/driver requires a PWM and
  `haptic-supply`. The current board DT does not supply those connections.
  Guessing a motor supply or PWM risks changing hardware behavior.

Do not add empty or disabled DT nodes to hide these warnings. A future source
change should separate the phantom charger platform-cell issue from correct
board descriptions for RGB and haptic. It must retain the original PMIC IRQ
controller, real charger, fuel gauge and USB-C topology. This audit changes none
of those files, drivers or settings and makes no new hardware claims.

Evidence: pinned Linux source `8cd9520d35a6c38db6567e97dd93b1f11f185dc6`,
`drivers/mfd/max77705.c`, `drivers/mfd/mfd-core.c`,
`drivers/power/supply/max77705_charger.c`,
`drivers/leds/leds-max77705.c`, `drivers/input/misc/max77693-haptic.c`,
`Documentation/devicetree/bindings/mfd/maxim,max77705.yaml`, and the tracked
`src/mainline-dts/exynos9810-star2lte.dts`. Private boot logs remain outside Git.
