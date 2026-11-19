// SPDX-License-Identifier: GPL-2.0-only
/* One-shot architectural cache enumeration. No cache maintenance, clocks,
 * memory mappings or persistent changes. CSSELR is restored before IRQs.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/cpu.h>
#include <linux/smp.h>
#include <linux/irqflags.h>
#include <asm/barrier.h>
#include <asm/sysreg.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);

struct cache_snapshot {
	u64 midr, clidr, mmfr2, selector_before, selector_after;
	u64 ccsidr[7][2];
	bool sampled;
};
static struct cache_snapshot snapshots[NR_CPUS];

static void snapshot_cpu(void *unused)
{
	struct cache_snapshot *s = &snapshots[smp_processor_id()];
	unsigned long flags;
	unsigned int level, kind, type;

	local_irq_save(flags);
	s->midr = read_sysreg(midr_el1);
	s->clidr = read_sysreg(clidr_el1);
	s->mmfr2 = read_sysreg(id_aa64mmfr2_el1);
	s->selector_before = read_sysreg(csselr_el1);
	for (level = 0; level < 7; level++) {
		type = (s->clidr >> (level * 3)) & 7;
		if (!type)
			break;
		if (type > 4)
			continue; /* Never select a reserved cache type. */
		for (kind = 0; kind < 2; kind++) {
			if ((kind == 0 && type == 1) ||
			    (kind == 1 && type != 1 && type != 3))
				continue;
			write_sysreg((level << 1) | kind, csselr_el1);
			isb();
			s->ccsidr[level][kind] = read_sysreg(ccsidr_el1);
		}
	}
	write_sysreg(s->selector_before, csselr_el1);
	isb();
	s->selector_after = read_sysreg(csselr_el1);
	s->sampled = true;
	local_irq_restore(flags);
}

static int __init audit_init(void)
{
	unsigned int cpu, level, kind, type;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
	    !of_machine_is_compatible("samsung,exynos9810"))
		return -ENODEV;
	cpus_read_lock();
	on_each_cpu(snapshot_cpu, NULL, 1);
	for_each_online_cpu(cpu) {
		struct cache_snapshot *s = &snapshots[cpu];

		pr_info("g965n-cache-audit: cpu=%u midr=%016llx clidr=%016llx mmfr2=%016llx sampled=%u selector_restored=%u\n",
			cpu, s->midr, s->clidr, s->mmfr2, s->sampled,
			s->selector_before == s->selector_after);
		for (level = 0; level < 7; level++) {
			type = (s->clidr >> (level * 3)) & 7;
			if (!type)
				break;
			if (type > 4)
				continue;
			for (kind = 0; kind < 2; kind++) {
				if ((kind == 0 && type == 1) ||
				    (kind == 1 && type != 1 && type != 3))
					continue;
				pr_info("g965n-cache-audit: cpu=%u level=%u kind=%u type=%u ccsidr=%016llx\n",
					cpu, level + 1, kind, type, s->ccsidr[level][kind]);
			}
		}
	}
	cpus_read_unlock();
	return 0;
}
static void __exit audit_exit(void) { }
module_init(audit_init);
module_exit(audit_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in one-shot star2lte architectural cache audit");
