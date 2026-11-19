# One-shot G965N cache audit

Opt-in diagnostic for the CPU/cache warning investigation. It reads MIDR,
CLIDR, MMFR2 and each present instruction/data/unified cache's CCSIDR on the
actual online CPU. CSSELR selection is temporary, IRQ-protected and restored
with an instruction barrier. No cache enable/disable/maintenance, clock,
MMIO, storage or persistent configuration changes occur. No autoload.

Build against the exact running experimental kernel's prepared output using
its cross compiler; the normal image build does not include or load this probe.
Before explicit `enable_g965n=1` loading, verify the exact model/BOOT, complete
nine-partition backup and probe hash. Capture the numeric architectural output
privately, verify every selector restored, then unload only this probe.
A successful build alone is not hardware evidence or topology qualification.

The callback test compiles the actual source against register/IRQ mocks and
checks reserved/absent cache types, all selectors and prior IRQ restoration.

Samsung's [M3 HotChips2018 presentation, slide9](https://old.hotchips.org/hc30/1conf/1.01_Samsung_Exynos_HotChips_MK_rev2.pdf)
identifies private512KiB L2 and shared4MiB L3 for M3. That corroborates a
problem with the fallback global L2 map, but does not establish the A55
configuration or replace this handset's register evidence. Do not infer
cache ownership from capacity alone or invent unsupported CPU capabilities.
