# CPU cache description audit

Native42 on the owner's G965N rev26, 2026-11-19. The initial DT has CPU and
cluster nodes but no cache links/geometry. The kernel reports inability to
find the hierarchy, then its generic fallback assumes every same-level cache
above L1 is globally shared. The observed L2 map0-7 is that fallback, not a
measurement of physical sharing.

A separately built, opt-in `experiments/cpu-cache-audit` module sampled all
8 online cores under the hotplug lock. Every core restored its prior CSSELR;
the probe was unloaded. No clocks, cache maintenance, storage or persistent
configuration changed. Full register output remains private. All cores in
each group agreed; the following are decoded architecture fields, not sizes
copied from another phone. MMFR2.CCIDX is0 on both core types, so the original
CCSIDR format applies: line=2^(LineSize+4), ways=Associativity+1,
sets=NumSets+1, capacity=line*ways*sets.

| Cores | Architectural level/type | Bytes | Line | Ways | Sets |
|---|---|---:|---:|---:|---:|
| A55 0-3 | L1 data | 32768 | 64 | 4 | 128 |
| A55 0-3 | L1 instruction | 32768 | 64 | 4 | 128 |
| A55 0-3 | L2 unified | 524288 | 64 | 16 | 512 |
| M3 4-7 | L1 data | 65536 | 64 | 8 | 128 |
| M3 4-7 | L1 instruction | 65536 | 128 | 4 | 128 |
| M3 4-7 | L2 unified | 524288 | 64 | 8 | 1024 |
| M3 4-7 | L3 unified | 4194304 | 64 | 16 | 4096 |

Cache geometry alone does not identify ownership. Samsung's
[M3 presentation, slide9](https://old.hotchips.org/hc30/1conf/1.01_Samsung_Exynos_HotChips_MK_rev2.pdf)
specifies private L2 per M3 core and a cluster-shared L3. Arm's
[Cortex-A55 TRM](https://documentation-service.arm.com/static/5e7e09f6a3736a0d2e862d2f)
section B2.23, page330 explicitly describes using the shared outer cache as
architectural L2 when private L2 is absent. Its512KiB CCSIDR encoding exactly
matches all four measured A55 cores. This establishes the shared DSU case
rather than four guessed private512KiB caches.

The proposed board DT adds measured L1 geometry, four private M3 L2 nodes,
a shared M3 L3 and a shared A55 cluster cache at the measured architectural
level2. No cache is enabled/disabled or resized by this description, and no
CPU feature register is overridden. The DT correction is not yet built or
boot-qualified. Verify actual sysfs geometry and ownership, all8 CPUs,
scheduler domains, boot logs and services after a guarded new kernel boot.
Do not claim a performance gain from metadata or removal of one warning.
