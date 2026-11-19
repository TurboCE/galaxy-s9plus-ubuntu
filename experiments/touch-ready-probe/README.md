# G965N TSP IRQ observation

GPL-2.0-only diagnostic, separate from the production build. Compile against
this handset's exact verified kernel headers/export table. A build never
loads a module or flashes a handset.

Default `power_cycle=0` reads actual gpa1/pin0 (the pinned stock/mainline
active-low TSP IRQ) through referenced GPIO-device/descriptor APIs. It does
not request the pin, change its mux/direction or drive it. Sampling100ms is
bounded to200samples and reports transitions only.

Only after explicit G965N model, fresh backup and consent checks, the separate
`power_cycle=1` option can perform the same masked LDO35/43 off2s/on operation
as ACPM handover. It refuses a bound touch driver, preserves voltage bits and
attempts restoration of both original on modes on failure. Arm an independent
bounded reboot recovery before deliberately unbinding touch. The operator
must restore binding, unload this diagnostic and cancel recovery only after
verification. Neither this module nor its Makefile is an installer.

Native#29 read-only test reported rawIRQ1 with touch bound. In the authorized
unbound rail-cycle test, GPIO changed1→0 at103ms, before first I2C at~1s. That
first bind returnedETIMEDOUT, then the kernel registered the input device~160ms
later; a second manual bind returnedEBUSY because it was already bound. This
undermines the proposed long controller-settle delay: an actual boot interrupt
was pending before the failing first access. The normal I2C error path resets
HSI2C; a scoped post-power controller-reset candidate is being tested next.
These observations are not a production GPIO readiness driver or a physical
touch test. Private traces stay outside Git.
