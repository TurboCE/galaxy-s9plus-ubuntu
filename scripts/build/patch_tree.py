"""Wire this port's own drivers into the mainline tree's Kbuild files.

Idempotent: runs before every build, does nothing if the entries are already
there. Takes the kernel source directory as its only argument.
"""
import re
import subprocess
import sys
from pathlib import Path

src = Path(sys.argv[1])
TAB = "\t"


def insert_before(path, anchor, text, marker):
    p = src / path
    s = p.read_text()
    if marker in s:
        print(f"{path}: {marker} already there")
        return
    assert anchor in s, f"{path}: anchor {anchor!r} not found"
    p.write_text(s.replace(anchor, text + anchor, 1))
    print(f"{path}: {marker} added")


def insert_after(path, anchor, text, marker):
    p = src / path
    s = p.read_text()
    if marker in s:
        print(f"{path}: {marker} already there")
        return
    if anchor.endswith("\n"):
        line = anchor
    else:
        matches = [l for l in s.splitlines(keepends=True) if anchor in l]
        assert len(matches) == 1, f"{path}: {anchor!r} matched {len(matches)} lines"
        line = matches[0]
    assert line in s, f"{path}: anchor {anchor!r} not found"
    p.write_text(s.replace(line, line + text, 1))
    print(f"{path}: {marker} added")


# --- UFS host driver for the Exynos 9810 -------------------------------------
insert_after(
    "drivers/ufs/host/Makefile",
    "obj-$(CONFIG_SCSI_UFS_EXYNOS) += ufs-exynos.o",
    "obj-$(CONFIG_SCSI_UFS_EXYNOS9810) += ufs-exynos9810.o ufs-cal-9810.o\n",
    "SCSI_UFS_EXYNOS9810",
)

ufs_kconfig = f"""config SCSI_UFS_EXYNOS9810
{TAB}tristate "Exynos 9810 UFS host controller driver"
{TAB}depends on SCSI_UFSHCD_PLATFORM && (ARCH_EXYNOS || COMPILE_TEST)
{TAB}help
{TAB}  UFS host support for the Samsung Exynos 9810, whose PHY and UNIPRO
{TAB}  calibration differs from every variant ufs-exynos.c covers. Uses
{TAB}  Samsung's own ufs-cal-9810 sequence, unchanged from the vendor kernel.

"""
insert_before(
    "drivers/ufs/host/Kconfig",
    "config SCSI_UFS_VARIABLE_SG_ENTRY_SIZE\n",
    ufs_kconfig,
    "SCSI_UFS_EXYNOS9810",
)

# The core only honours hba->sg_entry_size when this is on, and our FMP
# descriptor type needs 128-byte PRDT entries.
insert_after(
    "drivers/ufs/host/Kconfig",
    TAB + "default y if SCSI_UFS_EXYNOS && SCSI_UFS_CRYPTO" + chr(10),
    TAB + "default y if SCSI_UFS_EXYNOS9810" + chr(10),
    "default y if SCSI_UFS_EXYNOS9810",
)

# --- clock gates the port opens by hand (no 9810 clock driver) -------------
insert_after(
    "drivers/soc/samsung/Makefile",
    "obj-$(CONFIG_EXYNOS_PMU)",
    "obj-y\t\t\t\t+= s9p-clkgate.o\n",
    "s9p-clkgate.o",
)

# --- G3D power domain (vendor on/off sequence plus the EL3 TZPC restore) ---
insert_after(
    "drivers/soc/samsung/Makefile",
    "s9p-clkgate.o",
    "obj-y\t\t\t\t+= s9p-g3d-pd.o\n",
    "s9p-g3d-pd.o",
)

# --- MAX77705 Type-C MCU: route D+/D- to the AP -----------------------------
insert_after(
    "drivers/soc/samsung/Makefile",
    "s9p-g3d-pd.o",
    "obj-$(CONFIG_I2C)\t\t+= s9p-max77705-muic.o\n",
    "s9p-max77705-muic.o",
)

# --- USB 2.0 PHY, vendor CAL for this exact PHY revision -------------------
insert_after(
    "drivers/phy/samsung/Makefile",
    "phy-exynos5-usbdrd.o",
    "obj-$(CONFIG_GENERIC_PHY)\t+= phy-exynos9810-usbdrd.o\n",
    "phy-exynos9810-usbdrd.o",
)

# --- the bootloader framebuffer, presented as a KMS device named "exynos" ----
insert_after(
    "drivers/gpu/drm/sysfb/Makefile",
    "simpledrm.o",
    f"obj-$(CONFIG_DRM_EXYNOS_BOOTFB){TAB}+= exynos-bootfb.o\n",
    "DRM_EXYNOS_BOOTFB",
)

fb_kconfig = f"""config DRM_EXYNOS_BOOTFB
{TAB}tristate "Exynos bootloader framebuffer (KMS device named exynos)"
{TAB}depends on DRM && MMU
{TAB}select APERTURE_HELPERS
{TAB}select DRM_CLIENT_SELECTION
{TAB}select DRM_GEM_SHMEM_HELPER
{TAB}select DRM_KMS_HELPER
{TAB}select DRM_SYSFB_HELPER
{TAB}help
{TAB}  simpledrm under a different name. Samsung's DECON keeps scanning out
{TAB}  the framebuffer the bootloader set up, so that buffer works as a
{TAB}  scanout without a display driver -- and calling the device "exynos"
{TAB}  is what makes Mesa pair it with the Panfrost render node.

"""
insert_before(
    "drivers/gpu/drm/sysfb/Kconfig",
    "config DRM_SIMPLEDRM\n",
    fb_kconfig,
    "DRM_EXYNOS_BOOTFB",
)

# --- HSI2C: say what the controller was doing when a transfer timed out -----
# On this SoC every transfer ended in "tx timeout" although the bus is set up
# like the vendor's. Before giving up, poll the interrupt status by hand (so a
# transfer that completed without its interrupt arriving still succeeds, and
# says so), and log the controller's registers otherwise.
i2c_path = "drivers/i2c/busses/i2c-exynos5.c"
i2c = (src / i2c_path).read_text()
if "S9P_I2C_DIAG" not in i2c:
    inc_anchor = "#include <linux/i2c.h>\n"
    assert inc_anchor in i2c
    i2c = i2c.replace(inc_anchor, inc_anchor + "#include <linux/kernel_stat.h> /* S9P_I2C_DIAG */\n", 1)
    old = TAB + "if (time_left == 0)\n" + TAB + TAB + "ret = -ETIMEDOUT;\n"
    assert i2c.count(old) == 1, f"{i2c_path}: timeout anchor matched {i2c.count(old)} times"
    new = (
        TAB + "if (time_left == 0 && !i2c->atomic &&\n"
        + TAB + "    exynos5_i2c_poll_irqs_timeout(i2c, msecs_to_jiffies(20))) {\n"
        + TAB + TAB + "dev_warn_once(i2c->dev, \"S9P: transfer finished but its interrupt (%d, %u so far) never arrived; polled\\n\",\n"
        + TAB + TAB + TAB + "      i2c->irq, kstat_irqs_usr(i2c->irq));\n"
        + TAB + TAB + "time_left = 1;\n"
        + TAB + "}\n"
        + TAB + "if (time_left == 0) {\n"
        + TAB + TAB + "ret = -ETIMEDOUT;\n"
        + TAB + TAB + "dev_err(i2c->dev, \"S9P %s addr=%02x len=%d irq=%d(%u): ctl=%08x fifoctl=%08x inten=%08x intst=%08x fifost=%08x conf=%08x auto=%08x to=%08x trans=%08x fs=%08x/%08x/%08x usi_con=%08x usi_opt=%08x\\n\",\n"
        + TAB + TAB + TAB + "(msgs->flags & I2C_M_RD) ? \"rd\" : \"wr\", msgs->addr, msgs->len,\n"
        + TAB + TAB + TAB + "i2c->irq, kstat_irqs_usr(i2c->irq),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x00), readl(i2c->regs + 0x04),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x20), readl(i2c->regs + 0x24),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x30), readl(i2c->regs + 0x40),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x44), readl(i2c->regs + 0x48),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x50), readl(i2c->regs + 0x60),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0x64), readl(i2c->regs + 0x68),\n"
        + TAB + TAB + TAB + "readl(i2c->regs + 0xc4), readl(i2c->regs + 0xc8));\n"
        + TAB + "}\n"
    )
    i2c = i2c.replace(old, new, 1)
    (src / i2c_path).write_text(i2c)
    print(f"{i2c_path}: S9P_I2C_DIAG added")
else:
    print(f"{i2c_path}: S9P_I2C_DIAG already there")

# --- Panfrost: keep GPU buffers where the display block can reach them ------
# DECON addresses scanout with a 32-bit register, and this board has 6 GB:
# ZONE_DMA holds the 1.9 GB below 4 GB, ZONE_NORMAL everything above, and
# DMA32 is empty. A GPU buffer handed to KMS for direct scanout therefore
# lands above 4 GB, and importing it into the DECON device goes through
# swiotlb -- where it cannot fit either, because panfrost backs buffers with
# transparent hugepages and a 2 MB segment exceeds swiotlb's 256 KB maximum
# ("swiotlb buffer is full" in the log, once per attempt). The import fails
# and the compositor falls back to copying every frame.
#
# __GFP_DMA32 on panfrost's shmem mappings puts those pages in ZONE_DMA (the
# zonelist falls through an empty DMA32), so the import is a plain mapping
# and scanout works straight off the rendered buffer. The GPU itself is
# unaffected: its MMU is 40-bit and does not care where the pages are.
gem_c = "drivers/gpu/drm/panfrost/panfrost_gem.c"
g_path = src / gem_c
g = g_path.read_text()
if "S9P_GEM_DMA32" not in g:
    anchor_create = (TAB + "shmem = drm_gem_shmem_create(dev, size);" + chr(10)
                     + TAB + "if (IS_ERR(shmem))" + chr(10)
                     + TAB + TAB + "return ERR_CAST(shmem);" + chr(10))
    assert anchor_create in g, f"{gem_c}: shmem_create anchor not found"
    g = g.replace(anchor_create, anchor_create + chr(10)
        + TAB + "/* S9P_GEM_DMA32: below 4 GB, so KMS can scan this out directly */" + chr(10)
        + TAB + "mapping_set_gfp_mask(shmem->base.filp->f_mapping," + chr(10)
        + TAB + TAB + TAB + "     (mapping_gfp_mask(shmem->base.filp->f_mapping)" + chr(10)
        + TAB + TAB + TAB + "      & ~__GFP_HIGHMEM) | __GFP_DMA32);" + chr(10), 1)
    inc = "#include <linux/err.h>" + chr(10)
    if inc in g:
        g = g.replace(inc, inc + "#include <linux/pagemap.h> /* S9P_GEM_DMA32 */" + chr(10), 1)
    else:
        first = g.index("#include")
        g = g[:first] + "#include <linux/pagemap.h> /* S9P_GEM_DMA32 */" + chr(10) + g[first:]
    g_path.write_text(g)
    print(f"{gem_c}: GPU buffers restricted to the low 4 GB")
else:
    print(f"{gem_c}: S9P_GEM_DMA32 already there")

# --- Panfrost: isolate the port's all-BO low-memory allocation policy ------
# The display needs 32-bit scanout addresses; the Mali MMU itself does not.
# Constraining every GPU BO to that zone can exhaust low RAM while high RAM
# remains available. Keep the old policy by default, but allow a controlled
# new-allocation-only comparison without another kernel flash. Existing BOs
# are never moved. Whether imported scanout still works must be device-tested.
g = g_path.read_text()
if "S9P_LOWMEM_BO" not in g:
    anchor = "#include <linux/pagemap.h> /* S9P_GEM_DMA32 */\n"
    assert g.count(anchor) == 1
    g = g.replace(anchor, anchor +
        "#include <linux/moduleparam.h> /* S9P_LOWMEM_BO */\n"
        "static bool s9p_lowmem_bos = true;\n"
        "module_param_named(s9p_lowmem_bos, s9p_lowmem_bos, bool, 0644);\n"
        'MODULE_PARM_DESC(s9p_lowmem_bos, "restrict new GPU BOs to low RAM for the S9 scanout experiment");\n', 1)
    anchor = TAB + "mapping_set_gfp_mask(shmem->base.filp->f_mapping,\n"
    assert g.count(anchor) == 1
    g = g.replace(anchor, TAB + "if (READ_ONCE(s9p_lowmem_bos)) /* S9P_LOWMEM_BO */\n"
                  + TAB + anchor, 1)
    g_path.write_text(g)

# AArch64 tables qualify internal high-bank GPU access, but DECON still needs
# low-address exported buffers. Retain the conservative default until userspace
# and kernel distinguish private allocations from display-exportable allocations.
g = g_path.read_text()
if 'S9P_LOWMEM_SAFE_DEFAULT' not in g:
    anchor = '#include <linux/moduleparam.h> /* S9P_LOWMEM_BO */\n'
    assert g.count(anchor) == 1
    g = g.replace(anchor, anchor + '#include <linux/of.h> /* S9P_LOWMEM_SAFE_DEFAULT */\n', 1)
    anchor = 'static bool s9p_lowmem_bos = true;'
    assert g.count(anchor) == 1
    g = g.replace(anchor, 'static bool s9p_lowmem_bos = true; /* shared scanout still needs DMA32 */', 1)
    anchor = '\tif (READ_ONCE(s9p_lowmem_bos)) /* S9P_LOWMEM_BO */\n'
    assert g.count(anchor) == 1
    g = g.replace(anchor,
        '\tif (READ_ONCE(s9p_lowmem_bos) || /* S9P_LOWMEM_SAFE_DEFAULT */\n'
        '\t    !of_device_is_compatible(dev->dev->of_node, "samsung,exynos9810-mali") ||\n'
        '\t    !(to_panfrost_device(dev)->comp->gpu_quirks & BIT(GPU_QUIRK_FORCE_AARCH64_PGTABLE)))\n', 1)
    g_path.write_text(g)

# Repair previously patched build trees too; #11's all-high default caused
# DECON swiotlb bounce failures despite a clean GPU-only pressure readback.
g = g_path.read_text()
g = g.replace('static bool s9p_lowmem_bos; /* default permits qualified AArch64 board */',
              'static bool s9p_lowmem_bos = true; /* shared scanout still needs DMA32 */')
g_path.write_text(g)

# --- Panfrost: make the job-slot flush reduction switchable at run time ------
# Mali-G72 r0p1 on this SoC throws sporadic DATA_INVALID_FAULT / page faults at
# VA 0 under allocation churn, which vanish with PAN_MESA_DEBUG=sync. Flush
# reduction lets the GPU skip cache clean/invalidate between jobs; the switch
# (/sys/module/panfrost/parameters/s9p_flush_reduction, or
# panfrost.s9p_flush_reduction=0 on the command line) tests that hypothesis
# without a rebuild.
pj_path = "drivers/gpu/drm/panfrost/panfrost_job.c"
pj = (src / pj_path).read_text()
if "S9P_FLUSH" not in pj:
    old = "cfg |= JS_CONFIG_ENABLE_FLUSH_REDUCTION;"
    assert pj.count(old) == 1, f"{pj_path}: flush-reduction anchor matched {pj.count(old)} times"
    pj = pj.replace(old, "cfg |= s9p_flush_reduction ? JS_CONFIG_ENABLE_FLUSH_REDUCTION : 0; /* S9P_FLUSH */", 1)
    first_static = pj.index("\nstatic ")
    pj = (pj[:first_static]
          + "\n#include <linux/moduleparam.h> /* S9P_FLUSH */\n"
          + "static bool s9p_flush_reduction = true;\n"
          + "module_param_named(s9p_flush_reduction, s9p_flush_reduction, bool, 0644);\n"
          + "MODULE_PARM_DESC(s9p_flush_reduction, \"use JS_CONFIG_ENABLE_FLUSH_REDUCTION on GPUs that offer it (S9P experiment)\");\n"
          + pj[first_static:])
    (src / pj_path).write_text(pj)
    print(f"{pj_path}: S9P_FLUSH added")
else:
    print(f"{pj_path}: S9P_FLUSH already there")

# --- Panfrost: retain submission owner for actionable fault diagnosis ------
# Fault logs previously omitted the client, so a compositor fault after a
# benchmark could be mistaken for a fault in that benchmark. Log only on
# faults; no per-frame printk and no register/clock changes.
insert_before('drivers/gpu/drm/panfrost/panfrost_job.h',
              '#include <uapi/drm/panfrost_drm.h>',
              '#include <linux/sched.h> /* S9P_JOB_OWNER_INCLUDE */\n',
              'S9P_JOB_OWNER_INCLUDE')
insert_after('drivers/gpu/drm/panfrost/panfrost_job.h',
             'struct panfrost_job {\n',
             '\tpid_t submitter_tgid; /* S9P_JOB_OWNER */\n'
             '\tchar submitter_comm[TASK_COMM_LEN];\n',
             'S9P_JOB_OWNER */')
insert_after('drivers/gpu/drm/panfrost/panfrost_drv.c',
             '\tjob->pfdev = pfdev;\n',
             '\tjob->submitter_tgid = task_tgid_nr(current); /* S9P_JOB_OWNER */\n'
             '\tget_task_comm(job->submitter_comm, current);\n',
             'S9P_JOB_OWNER')
pj = (src / pj_path).read_text()
if 'S9P_JOB_OWNER' not in pj:
    anchor = '\t} else {\n\t\tdev_err(pfdev->base.dev, "js fault,'
    assert pj.count(anchor) == 1
    diagnostic = ('\t} else {\n'
        '\t\t/* S9P_JOB_OWNER: record the actual ioctl submitter. */\n'
        '\t\tdev_err(pfdev->base.dev, "job owner=%s tgid=%d bos=%u jc=%#llx\\n",\n'
        '\t\t\tjob->submitter_comm, job->submitter_tgid, job->bo_count, job->jc);\n'
        '\t\tdev_err(pfdev->base.dev, "js fault,')
    (src / pj_path).write_text(pj.replace(anchor, diagnostic, 1))

# Timeouts need the same owner information as hardware exception reports.
pj = (src / pj_path).read_text()
if "S9P_TIMEOUT_OWNER" not in pj:
    anchor = '\tdev_err(pfdev->base.dev, "gpu sched timeout, js='
    assert pj.count(anchor) == 1
    pj = pj.replace(anchor,
        '\t/* S9P_TIMEOUT_OWNER: distinguish compositor and benchmark jobs. */\n'
        '\tdev_err(pfdev->base.dev, "timeout owner=%s tgid=%d bos=%u jc=%#llx\\n",\n'
        '\t\tjob->submitter_comm, job->submitter_tgid, job->bo_count, job->jc);\n'
        + anchor, 1)
    (src / pj_path).write_text(pj)

timeout_snapshot_v1 = r"""/* S9P_TIMEOUT_SNAPSHOT: diagnostics only, no acknowledgement or recovery writes. */
static void panfrost_job_timeout_snapshot(struct panfrost_job *job)
{
	struct panfrost_device *pfdev = job->pfdev;
	struct panfrost_job *queued;
	unsigned long flags, suspended;
	int js = panfrost_job_get_slot(job), pm_ref;
	unsigned int i;
	u32 irq[9] = {}, state = 0, cmd_next = 0, next_lo = 0, next_hi = 0;
	u32 gpu_status = 0;
	u64 seqno[2] = {};
	bool present[2] = {}, matches[2] = {}, signaled[2] = {};
	bool mmio = false;
	const u32 irq_regs[] = {
		JOB_INT_RAWSTAT, JOB_INT_MASK, JOB_INT_STAT,
		MMU_INT_RAWSTAT, MMU_INT_MASK, MMU_INT_STAT,
		GPU_INT_RAWSTAT, GPU_INT_MASK, GPU_INT_STAT,
	};

	/* Pin only an already active, referenced device. Never wake it merely
	 * to diagnose a timeout, or schedule a new idle transition on release.
	 */
	pm_ref = pm_runtime_get_if_in_use(pfdev->base.dev);
	spin_lock_irqsave(&pfdev->js->job_lock, flags);
	suspended = READ_ONCE(pfdev->is_suspended[0]);
	for (i = 0; i < ARRAY_SIZE(seqno); i++) {
		queued = pfdev->jobs[js][i];
		present[i] = queued != NULL;
		matches[i] = queued == job;
		if (queued && queued->done_fence) {
			seqno[i] = queued->done_fence->seqno;
			/* Do not call a fence helper that might acquire job_lock. */
			signaled[i] = test_bit(DMA_FENCE_FLAG_SIGNALED_BIT,
					      &queued->done_fence->flags);
		}
	}
	if (pm_ref > 0 && !suspended) {
		for (i = 0; i < ARRAY_SIZE(irq_regs); i++)
			irq[i] = job_read(pfdev, irq_regs[i]);
		state = job_read(pfdev, JOB_INT_JS_STATE);
		cmd_next = job_read(pfdev, JS_COMMAND_NEXT(js));
		next_lo = job_read(pfdev, JS_HEAD_NEXT_LO(js));
		next_hi = job_read(pfdev, JS_HEAD_NEXT_HI(js));
		gpu_status = job_read(pfdev, GPU_STATUS);
		mmio = true;
	}
	spin_unlock_irqrestore(&pfdev->js->job_lock, flags);
	if (pm_ref > 0)
		pm_runtime_put_noidle(pfdev->base.dev);

	/* MMIO values span a few reads, not an atomic hardware snapshot.
	 * Print only after releasing job_lock; never expose BO contents.
	 */
	dev_err(pfdev->base.dev,
		"timeout snapshot js=%d pm_ref=%d suspended=%#lx reset=%d mmio=%d q0=%d/%d/%llu/%d q1=%d/%d/%llu/%d\n",
		js, pm_ref, suspended, atomic_read(&pfdev->reset.pending), mmio,
		present[0], matches[0], (unsigned long long)seqno[0], signaled[0],
		present[1], matches[1], (unsigned long long)seqno[1], signaled[1]);
	if (mmio)
		dev_err(pfdev->base.dev,
			"timeout registers job_irq=%#x/%#x/%#x mmu_irq=%#x/%#x/%#x gpu_irq=%#x/%#x/%#x js_state=%#x next_cmd=%#x next_head=%#x:%08x gpu_status=%#x\n",
			irq[0], irq[1], irq[2], irq[3], irq[4], irq[5],
			irq[6], irq[7], irq[8], state, cmd_next, next_hi,
			next_lo, gpu_status);
}

"""

# Timeout-only observation: retain the normal scheduler/recovery behavior.
# The PM reference never wakes the GPU; job_lock protects queue/fence snapshots.
# MMIO reads do not ACK interrupts, and printk runs after releasing job_lock.
pj = (src / pj_path).read_text()
if "S9P_TIMEOUT_SNAPSHOT" not in pj:
    anchor = "static enum drm_gpu_sched_stat panfrost_job_timedout(struct drm_sched_job\n"
    assert pj.count(anchor) == 1
    diagnostic = timeout_snapshot_v1
    pj = pj.replace(anchor, diagnostic + anchor, 1)
    anchor = '\t/* S9P_TIMEOUT_OWNER: distinguish compositor and benchmark jobs. */\n'
    assert pj.count(anchor) == 1
    pj = pj.replace(anchor, '\tpanfrost_job_timeout_snapshot(job);\n\n' + anchor, 1)
    (src / pj_path).write_text(pj)

# Upgrade the exact known v1 helper in cached trees; never guess at changed C.
# Bounded reads only on timeout, under the existing PM/queue guard. No MMIO
# writes, no fence callbacks under job_lock, and every printk remains outside it.
pj = (src / pj_path).read_text()
timeout_snapshot_v2 = r"""/* S9P_TIMEOUT_SNAPSHOT: diagnostics only, no acknowledgement or recovery writes.
 * S9P_TIMEOUT_SNAPSHOT_V2: live producer slots and full-width power masks.
 */
static void panfrost_job_timeout_snapshot(struct panfrost_job *job)
{
	struct panfrost_device *pfdev = job->pfdev;
	struct panfrost_job *queued;
	unsigned long flags, suspended;
	int js = panfrost_job_get_slot(job), pm_ref;
	unsigned int i, j;
	u32 irq[9] = {}, state = 0;
	u32 slots[NUM_JOB_SLOTS][14] = {}, power[3][6] = {};
	u32 gpu_status = 0;
	u64 seqno[2] = {};
	bool present[2] = {}, matches[2] = {}, signaled[2] = {};
	bool mmio = false;
	const u32 irq_regs[] = {
		JOB_INT_RAWSTAT, JOB_INT_MASK, JOB_INT_STAT,
		MMU_INT_RAWSTAT, MMU_INT_MASK, MMU_INT_STAT,
		GPU_INT_RAWSTAT, GPU_INT_MASK, GPU_INT_STAT,
	};

	const u32 power_regs[3][6] = {
		{ GPU_SHADER_PRESENT_LO, GPU_SHADER_PRESENT_HI,
		  SHADER_READY_LO, SHADER_READY_HI, SHADER_PWRTRANS_LO, SHADER_PWRTRANS_HI },
		{ GPU_TILER_PRESENT_LO, GPU_TILER_PRESENT_HI,
		  TILER_READY_LO, TILER_READY_HI, TILER_PWRTRANS_LO, TILER_PWRTRANS_HI },
		{ GPU_L2_PRESENT_LO, GPU_L2_PRESENT_HI,
		  L2_READY_LO, L2_READY_HI, L2_PWRTRANS_LO, L2_PWRTRANS_HI },
	};
	const char * const power_names[] = { "shader", "tiler", "l2" };

	/* Pin only an already active, referenced device. Never wake it merely
	 * to diagnose a timeout, or schedule a new idle transition on release.
	 */
	pm_ref = pm_runtime_get_if_in_use(pfdev->base.dev);
	spin_lock_irqsave(&pfdev->js->job_lock, flags);
	suspended = READ_ONCE(pfdev->is_suspended[0]);
	for (i = 0; i < ARRAY_SIZE(seqno); i++) {
		queued = pfdev->jobs[js][i];
		present[i] = queued != NULL;
		matches[i] = queued == job;
		if (queued && queued->done_fence) {
			seqno[i] = queued->done_fence->seqno;
			/* Do not call a fence helper that might acquire job_lock. */
			signaled[i] = test_bit(DMA_FENCE_FLAG_SIGNALED_BIT,
					      &queued->done_fence->flags);
		}
	}
	if (pm_ref > 0 && !suspended) {
		for (i = 0; i < ARRAY_SIZE(irq_regs); i++)
			irq[i] = job_read(pfdev, irq_regs[i]);
		state = job_read(pfdev, JOB_INT_JS_STATE);
		for (i = 0; i < NUM_JOB_SLOTS; i++) {
			const u32 regs[] = {
				JS_STATUS(i), JS_CONFIG(i), JS_AFFINITY_LO(i), JS_AFFINITY_HI(i),
				JS_HEAD_LO(i), JS_HEAD_HI(i), JS_TAIL_LO(i), JS_TAIL_HI(i),
				JS_COMMAND_NEXT(i), JS_CONFIG_NEXT(i),
				JS_HEAD_NEXT_LO(i), JS_HEAD_NEXT_HI(i),
				JS_AFFINITY_NEXT_LO(i), JS_AFFINITY_NEXT_HI(i),
			};

			for (j = 0; j < ARRAY_SIZE(regs); j++)
				slots[i][j] = job_read(pfdev, regs[j]);
		}
		for (i = 0; i < ARRAY_SIZE(power_regs); i++) {
			for (j = 0; j < ARRAY_SIZE(power_regs[0]); j++)
				power[i][j] = job_read(pfdev, power_regs[i][j]);
		}
		gpu_status = job_read(pfdev, GPU_STATUS);
		mmio = true;
	}
	spin_unlock_irqrestore(&pfdev->js->job_lock, flags);
	if (pm_ref > 0)
		pm_runtime_put_noidle(pfdev->base.dev);

	/* MMIO values span a few reads, not an atomic hardware snapshot.
	 * Print only after releasing job_lock; never expose BO contents.
	 */
	dev_err(pfdev->base.dev,
		"timeout snapshot js=%d pm_ref=%d suspended=%#lx reset=%d mmio=%d q0=%d/%d/%llu/%d q1=%d/%d/%llu/%d\n",
		js, pm_ref, suspended, atomic_read(&pfdev->reset.pending), mmio,
		present[0], matches[0], (unsigned long long)seqno[0], signaled[0],
		present[1], matches[1], (unsigned long long)seqno[1], signaled[1]);
	if (!mmio)
		return;
	dev_err(pfdev->base.dev,
		"timeout registers job_irq=%#x/%#x/%#x mmu_irq=%#x/%#x/%#x gpu_irq=%#x/%#x/%#x js_state=%#x gpu_status=%#x\n",
		irq[0], irq[1], irq[2], irq[3], irq[4], irq[5],
		irq[6], irq[7], irq[8], state, gpu_status);
	for (i = 0; i < NUM_JOB_SLOTS; i++)
		dev_err(pfdev->base.dev,
			"timeout slot%u status=%#x config=%#x affinity=%#x:%08x head=%#x:%08x tail=%#x:%08x next_cmd=%#x next_config=%#x next_head=%#x:%08x next_affinity=%#x:%08x\n",
			i, slots[i][0], slots[i][1], slots[i][3], slots[i][2],
			slots[i][5], slots[i][4], slots[i][7], slots[i][6],
			slots[i][8], slots[i][9], slots[i][11], slots[i][10],
			slots[i][13], slots[i][12]);
	for (i = 0; i < ARRAY_SIZE(power); i++)
		dev_err(pfdev->base.dev,
			"timeout power %s present=%#x:%08x ready=%#x:%08x transition=%#x:%08x\n",
			power_names[i], power[i][1], power[i][0], power[i][3],
			power[i][2], power[i][5], power[i][4]);
}

"""
if "S9P_TIMEOUT_SNAPSHOT_V2" not in pj:
    assert pj.count(timeout_snapshot_v1) == 1, "Panfrost timeout snapshot v1 anchor drift"
    (src / pj_path).write_text(pj.replace(timeout_snapshot_v1, timeout_snapshot_v2, 1))
else:
    assert pj.count(timeout_snapshot_v2) == 1, "Panfrost timeout snapshot v2 anchor drift"

# Independent recovery correction, adapted from the upstream mailing-list patch:
# Arun Iyengar <aiyengar1990@gmail.com>, 2026-11-13 09:03:04 +0000,
# [PATCH v3 12/14] drm/panfrost: Wait for the soft-stopped slots with the live slot status
# Message-ID: <20261113-panfrost-long-jobs-v3-12-80ae78d38f6e@gmail.com>
# https://lore.kernel.org/all/20261113-panfrost-long-jobs-v3-12-80ae78d38f6e@gmail.com/
# Author's original mail was read through the lore-kernel.gnuweeb.org mirror.
# Additional original-mail archive: https://lists.openwall.net/linux-kernel/2026/11/13/872
# Fixes: 030761e097b4 (drm/panfrost: Queue jobs on the hardware).
# Retain the kernel source's GPL-2.0 terms and author attribution. This adopts
# only patch 12's live-state wait and defensive dequeue guard, not patch 13's
# long-job policy. It does NOT claim to fix the initiating GPU timeouts.
pj = (src / pj_path).read_text()
if "S9P_LIVE_SLOT_STATUS" not in pj:
    replacements = [
        (r"""static u32 panfrost_active_slots(struct panfrost_device *pfdev,
				 u32 *js_state_mask, u32 js_state)
{
	u32 rawstat;

	if (!(js_state & *js_state_mask))
		return 0;

	rawstat = job_read(pfdev, JOB_INT_RAWSTAT);
	if (rawstat) {
		unsigned int i;

		for (i = 0; i < NUM_JOB_SLOTS; i++) {
			if (rawstat & MK_JS_MASK(i))
				*js_state_mask &= ~MK_JS_MASK(i);
		}
	}

	return js_state & *js_state_mask;
}
""", r"""/* S9P_LIVE_SLOT_STATUS: adapted from Arun Iyengar's 2026-11-13 v3 12/14.
 * JOB_INT_JS_STATE is latched by JOB_INT_CLEAR, not a live idle indication.
 * Keep the original 10ms stop budget and the existing reset policy.
 */
static bool panfrost_slots_idle(struct panfrost_device *pfdev)
{
	unsigned int i;

	for (i = 0; i < NUM_JOB_SLOTS; i++) {
		if (job_read(pfdev, JS_STATUS(i)) ==
		    DRM_PANFROST_EXCEPTION_ACTIVE)
			return false;
	}

	return true;
}

"""),
        (r"""	u32 js_state, js_state_mask = 0xffffffff;
	unsigned int i, j;
	bool cookie;
""", r"""	unsigned int i, j;
	bool cookie, idle;
"""),
        (r"""	/* Wait at most 10ms for soft-stops to complete */
	ret = readl_poll_timeout(pfdev->iomem + JOB_INT_JS_STATE, js_state,
				 !panfrost_active_slots(pfdev, &js_state_mask, js_state),
				 10, 10000);
""", r"""	/* Wait for live slot status before draining queues, at most 10ms. */
	ret = read_poll_timeout(panfrost_slots_idle, idle, idle, 10, 10000,
				false, pfdev);
"""),
        (r"""	struct panfrost_job *job = pfdev->jobs[slot][0];

	WARN_ON(!job);
""", r"""	struct panfrost_job *job = pfdev->jobs[slot][0];

	if (WARN_ON(!job))
		return NULL;
"""),
    ]
    for old, new in replacements:
        assert pj.count(old) == 1, "Panfrost live-slot correction anchor drift"
        pj = pj.replace(old, new, 1)
    (src / pj_path).write_text(pj)

# A failed BO dump still reserves its full data range. Zero the complete file
# so invalid/mapping-failure ranges never expose untouched vmalloc contents.
# Preserve dump validity/layout and do not populate sparse heap pages here.
dump_path = src / 'drivers/gpu/drm/panfrost/panfrost_dump.c'
dump = dump_path.read_text()
dump_old = '\titer.start = __vmalloc(file_size, GFP_KERNEL | __GFP_NOWARN |\n\t\t\t__GFP_NORETRY);'
dump_new = ('\t/* S9P_DUMP_ZERO: invalid BO ranges must contain defined bytes. */\n'
            '\titer.start = __vmalloc(file_size, GFP_KERNEL | __GFP_NOWARN |\n'
            '\t\t\t__GFP_NORETRY | __GFP_ZERO);')
if 'S9P_DUMP_ZERO' not in dump:
    assert dump.count(dump_old) == 1, 'Panfrost dump allocation anchor drift'
    dump_path.write_text(dump.replace(dump_old, dump_new, 1))
else:
    assert dump.count(dump_new) == 1, 'Panfrost zeroed dump allocation drift'

# Report why BO backing failed rather than only a WARN backtrace.
mmu_path = src / "drivers/gpu/drm/panfrost/panfrost_mmu.c"
mmu = mmu_path.read_text()
if "S9P_SGT_ERROR" not in mmu:
    anchor = '\tif (WARN_ON(IS_ERR(sgt)))\n\t\treturn PTR_ERR(sgt);'
    assert mmu.count(anchor) == 1
    replacement = (
        '\tif (IS_ERR(sgt)) { /* S9P_SGT_ERROR */\n'
        '\t\tdev_err_ratelimited(pfdev->base.dev, "BO backing failed: err=%ld bytes=%zu heap=%u\\n",\n'
        '\t\t\tPTR_ERR(sgt), obj->size, bo->is_heap);\n'
        '\t\treturn PTR_ERR(sgt);\n\t}')
    mmu_path.write_text(mmu.replace(anchor, replacement, 1))

# --- Exynos9810: use the vendor's AArch64 GPU page-table mode ---------------
# Lineage bv_r38p1 device/mali_kbase_device.c selects AArch64 unconditionally.
# The DTS already has this board-compatible before the generic Bifrost fallback.
# Reuse mainline's existing AARCH64 support; do not alter other Bifrost devices.
insert_before('drivers/gpu/drm/panfrost/panfrost_drv.c',
    'static const struct panfrost_compatible default_pm_rt_data = {',
    '/* S9P_AARCH64_MMU: the clock provider owns the ACPM rail. */\n'
    'static const struct panfrost_compatible exynos9810_data = {\n'
    '\t.num_supplies = 0,\n'
    '\t.supply_names = NULL,\n'
    '\t.num_pm_domains = 1,\n'
    '\t.pm_domain_names = NULL,\n'
    '\t.gpu_quirks = BIT(GPU_QUIRK_FORCE_AARCH64_PGTABLE),\n'
    '};\n\n', 'S9P_AARCH64_MMU')
# Reconcile trees patched before the board's rail ownership was explicit.
pf_drv = src / 'drivers/gpu/drm/panfrost/panfrost_drv.c'
pf_text = pf_drv.read_text()
old_board = ('static const struct panfrost_compatible exynos9810_data = {\n'
             '\t.num_supplies = ARRAY_SIZE(default_supplies) - 1,\n'
             '\t.supply_names = default_supplies,\n')
new_board = ('static const struct panfrost_compatible exynos9810_data = {\n'
             '\t.num_supplies = 0,\n'
             '\t.supply_names = NULL,\n')
assert old_board in pf_text or new_board in pf_text
pf_drv.write_text(pf_text.replace(old_board, new_board, 1))
pf_dvfs = src / 'drivers/gpu/drm/panfrost/panfrost_devfreq.c'
pf_text = pf_dvfs.read_text()
if 'S9P_OPTIONAL_OPP_SUPPLIES' not in pf_text:
    anchor = '\tret = devm_pm_opp_set_regulators(dev, pfdev->comp->supply_names);\n'
    assert pf_text.count(anchor) == 1
    pf_text = pf_text.replace(anchor,
        '\t/* S9P_OPTIONAL_OPP_SUPPLIES: no Linux regulator for ACPM-owned rails. */\n'
        '\tret = 0;\n'
        '\tif (pfdev->comp->num_supplies)\n'
        '\t\tret = devm_pm_opp_set_regulators(dev, pfdev->comp->supply_names);\n', 1)
    pf_dvfs.write_text(pf_text)

insert_after('drivers/gpu/drm/panfrost/panfrost_drv.c',
    '\t/* Set first to probe before the generic compatibles */\n',
    '\t{ .compatible = "samsung,exynos9810-mali", /* S9P_AARCH64_MATCH */\n'
    '\t  .data = &exynos9810_data, },\n', 'S9P_AARCH64_MATCH')
mmu_path = src / 'drivers/gpu/drm/panfrost/panfrost_mmu.c'
mmu = mmu_path.read_text()
if 'S9P_MMU_MODE_LOG' not in mmu:
    anchor = '\tmmu = kzalloc_obj(*mmu);\n'
    assert mmu.count(anchor) == 1
    mmu = mmu.replace(anchor,
        '\t/* S9P_MMU_MODE_LOG: record the actual selected page-table format. */\n'
        '\tdev_info_once(pfdev->base.dev, "GPU page tables: %s\\n",\n'
        '\t\tfmt == ARM_64_LPAE_S1 ? "AARCH64_4K" : "Mali legacy LPAE");\n\n'
        + anchor, 1)
    mmu_path.write_text(mmu)

# --- sysfb: invalidate the CPU cache before blitting a GPU-written FB -------
# Mutter renders with Panfrost straight into the KMS driver's shmem dumb
# buffers (exported as dma-buf). Those are mapped cached on the CPU side
# (map_wc is false for native shmem objects), and the per-frame blit into the
# sboot framebuffer reads them with the CPU, so stale cache lines from the
# previous frame end up on screen. drm_gem_fb_begin_cpu_access() only syncs
# *imported* objects. Map the pages for our own (non-coherent) device once and
# invalidate before every blit; the device needs a DMA mask that covers the
# RAM above 4 GB or the mapping would bounce through swiotlb.
sm_path = "drivers/gpu/drm/sysfb/drm_sysfb_modeset.c"
sm = (src / sm_path).read_text()
if "S9P_FB_SYNC" not in sm:
    inc = '#include "drm_sysfb_helper.h"\n'
    assert inc in sm
    sm = sm.replace(inc, "#include <linux/dma-mapping.h> /* S9P_FB_SYNC */\n#include <drm/drm_gem_shmem_helper.h>\n" + inc, 1)
    old = TAB + "ret = drm_gem_fb_begin_cpu_access(fb, DMA_FROM_DEVICE);\n"
    assert sm.count(old) == 1, f"{sm_path}: begin_cpu_access anchor matched {sm.count(old)} times"
    new = (TAB + "if (fb->obj[0] && !drm_gem_is_imported(fb->obj[0])) { /* S9P_FB_SYNC */\n"
           + TAB + TAB + "struct sg_table *s9p_sgt = drm_gem_shmem_get_pages_sgt(to_drm_gem_shmem_obj(fb->obj[0]));\n"
           + TAB + TAB + "if (!IS_ERR_OR_NULL(s9p_sgt))\n"
           + TAB + TAB + TAB + "dma_sync_sgtable_for_cpu(dev->dev, s9p_sgt, DMA_FROM_DEVICE);\n"
           + TAB + "}\n" + old)
    sm = sm.replace(old, new, 1)
    (src / sm_path).write_text(sm)
    print(f"{sm_path}: S9P_FB_SYNC added")
else:
    print(f"{sm_path}: S9P_FB_SYNC already there")

fb_path = "drivers/gpu/drm/sysfb/exynos-bootfb.c"
fbc = (src / fb_path).read_text()
if "S9P_FB_SYNC" not in fbc:
    inc = "#include <linux/aperture.h>\n"
    assert inc in fbc
    fbc = fbc.replace(inc, inc + "#include <linux/dma-mapping.h> /* S9P_FB_SYNC */\n", 1)
    old = TAB + "sdev = exynos_bootfb_device_create(&exynos_bootfb_driver, pdev);\n"
    assert fbc.count(old) == 1, f"{fb_path}: probe anchor matched {fbc.count(old)} times"
    new = (TAB + "ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(40)); /* S9P_FB_SYNC */\n"
           + TAB + "if (ret)\n" + TAB + TAB + "return ret;\n" + old)
    fbc = fbc.replace(old, new, 1)
    (src / fb_path).write_text(fbc)
    print(f"{fb_path}: S9P_FB_SYNC dma mask added")
else:
    print(f"{fb_path}: S9P_FB_SYNC already there")

# --- HSI2C: the Exynos 9810 timing model --------------------------------------
# The 9810's controller is the "AutoV9" generation: SCL = IPCLK / ((CLK_DIV+1)
# * 16), CLK_DIV in TIMING_FS3[23:16], and the high-period / start-hold shapes
# are bit patterns in TIMING_FS2[7:0] and TIMING_FS1[23:16] (vendor
# exynos5_i2c_set_timing, fast-speed branch). The Exynos 8895 formula wrote
# CLK_DIV = 0 here, i.e. a 12.5 MHz SCL, and the master sat in WAIT for ever.
if "S9P_I2C_TIMING" not in i2c:
    old = (
        TAB + "if (i2c->variant->hw == I2C_TYPE_EXYNOSAUTOV9) {\n"
        + TAB + TAB + "div = ((clkin / (16 * i2c->op_clock)) - 1);\n"
        + TAB + TAB + "i2c_timing_s3 = div << 16;\n"
        + TAB + TAB + "if (hs_timings)\n"
        + TAB + TAB + TAB + "writel(i2c_timing_s3, i2c->regs + HSI2C_TIMING_HS3);\n"
        + TAB + TAB + "else\n"
        + TAB + TAB + TAB + "writel(i2c_timing_s3, i2c->regs + HSI2C_TIMING_FS3);\n"
        + "\n"
        + TAB + TAB + "return 0;\n"
        + TAB + "}\n"
    )
    assert i2c.count(old) == 1, f"{i2c_path}: autov9 timing block matched {i2c.count(old)} times"
    new = (
        TAB + "if (i2c->variant->hw == I2C_TYPE_EXYNOSAUTOV9) { /* S9P_I2C_TIMING */\n"
        + TAB + TAB + "unsigned int mhz = clkin / 1000000, n, s1, s2, s3;\n"
        + TAB + TAB + "void __iomem *r1 = i2c->regs + (hs_timings ? HSI2C_TIMING_HS1 : HSI2C_TIMING_FS1);\n"
        + TAB + TAB + "void __iomem *r2 = i2c->regs + (hs_timings ? HSI2C_TIMING_HS2 : HSI2C_TIMING_FS2);\n"
        + TAB + TAB + "void __iomem *r3 = i2c->regs + (hs_timings ? HSI2C_TIMING_HS3 : HSI2C_TIMING_FS3);\n"
        + "\n"
        + TAB + TAB + "/* vendor: div = ipclk / (op * 15), shapes from ipclk in MHz */\n"
        + TAB + TAB + "div = (clkin / (op_clk * 15)) & 0xff;\n"
        + TAB + TAB + "if (hs_timings)\n"
        + TAB + TAB + TAB + "n = (7 * mhz) / ((div + 1) * 100);\n"
        + TAB + TAB + "else\n"
        + TAB + TAB + TAB + "n = (9 * mhz) / ((div + 1) * 10);\n"
        + TAB + TAB + "if (n > 7)\n"
        + TAB + TAB + TAB + "n = 7;\n"
        + TAB + TAB + "s2 = ((0xffffffffu >> n) << n) & 0xff;\t\t/* TSCL_H */\n"
        + TAB + TAB + "n = n ? n - 1 : 0;\n"
        + TAB + TAB + "s1 = ((0xffffffffu >> n) << n) & 0xff;\t\t/* TSTART_HD */\n"
        + TAB + TAB + "s3 = (readl(r3) & ~0x00ff0000) | (div << 16);\n"
        + TAB + TAB + "writel(s3, r3);\n"
        + TAB + TAB + "writel((readl(r2) & ~0xff) | s2, r2);\n"
        + TAB + TAB + "writel((readl(r1) & ~0x00ff0000) | (s1 << 16), r1);\n"
        + TAB + TAB + "dev_info(i2c->dev, \"S9P timing %s: ipclk=%u op=%u div=%u -> scl=%u Hz, t1=%08x t2=%08x t3=%08x\\n\",\n"
        + TAB + TAB + TAB + " hs_timings ? \"HS\" : \"FS\", clkin, op_clk, div,\n"
        + TAB + TAB + TAB + " clkin / ((div + 1) * 16), readl(r1), readl(r2), readl(r3));\n"
        + TAB + TAB + "return 0;\n"
        + TAB + "}\n"
    )
    i2c = i2c.replace(old, new, 1)
    (src / i2c_path).write_text(i2c)
    print(f"{i2c_path}: S9P_I2C_TIMING added")
else:
    print(f"{i2c_path}: S9P_I2C_TIMING already there")

# --- ACPM mailbox (S2MPS18 over the APM firmware): voltages -----------------
insert_after(
    "drivers/soc/samsung/Makefile",
    "s9p-max77705-muic.o",
    "obj-$(CONFIG_S9P_ACPM)\t\t+= s9p-acpm.o\n",
    "s9p-acpm.o",
)

# --- G3D clock steps (stock maximum by default, thermal cap lowers) --------
insert_after(
    "drivers/soc/samsung/Makefile",
    "s9p-acpm.o",
    "obj-$(CONFIG_S9P_ACPM)\t\t+= s9p-g3d.o\n",
    "s9p-g3d.o",
)

acpm_kconfig = f"""config S9P_ACPM
{TAB}bool "ACPM MFD mailbox access (Exynos 9810 S2MPS18)"
{TAB}depends on ARCH_EXYNOS
{TAB}help
{TAB}  The S2MPS18 main PMIC is behind the APM firmware; this speaks the
{TAB}  vendor acpm_ipc/acpm_mfd protocol (channel 2) so in-kernel code can
{TAB}  set BUCK rails. Used by s9p-cpufreq and s9p-g3d.

"""
soc_kc_path = "drivers/soc/samsung/Kconfig"
soc_kc = (src / soc_kc_path).read_text()
if "config S9P_ACPM" not in soc_kc:
    (src / soc_kc_path).write_text(soc_kc + acpm_kconfig)
    print(f"{soc_kc_path}: S9P_ACPM added")
else:
    print(f"{soc_kc_path}: S9P_ACPM already there")

cpufreq_mk = (src / "drivers/cpufreq/Makefile").read_text()
if "s9p-cpufreq.o" not in cpufreq_mk:
    cpufreq_mk += "obj-$(CONFIG_ARM_S9P_CPUFREQ) += s9p-cpufreq.o\n"
    (src / "drivers/cpufreq/Makefile").write_text(cpufreq_mk)
    print("drivers/cpufreq/Makefile: s9p-cpufreq.o added")
else:
    print("drivers/cpufreq/Makefile: s9p-cpufreq.o already there")

cpufreq_kc = (src / "drivers/cpufreq/Kconfig").read_text()
if "ARM_S9P_CPUFREQ" not in cpufreq_kc:
    cpufreq_kc += f"""config ARM_S9P_CPUFREQ
{TAB}bool "cpufreq for the Samsung Exynos 9810 (Galaxy S9+)"
{TAB}depends on ARM64
{TAB}select S9P_ACPM
{TAB}help
{TAB}  Scales both clusters with the vendor PLL table entries and sets the
{TAB}  BUCK rails through the APM firmware. The ACPM DVFS plugin refuses
{TAB}  this port, so the vendor's own acme path is not available.

"""
    (src / "drivers/cpufreq/Kconfig").write_text(cpufreq_kc)
    print("drivers/cpufreq/Kconfig: ARM_S9P_CPUFREQ added")
else:
    print("drivers/cpufreq/Kconfig: ARM_S9P_CPUFREQ already there")

# --- DECON scanout takeover --------------------------------------------------
drm_mk = (src / "drivers/gpu/drm/Makefile").read_text()
if "s9p/" not in drm_mk:
    drm_mk += "obj-$(CONFIG_DRM_S9P_DECON) += s9p/\n"
    (src / "drivers/gpu/drm/Makefile").write_text(drm_mk)
    print("drivers/gpu/drm/Makefile: s9p/ added")
else:
    print("drivers/gpu/drm/Makefile: s9p/ already there")

drm_kc_path = "drivers/gpu/drm/Kconfig"
drm_kc = (src / drm_kc_path).read_text()
if 's9p/Kconfig"' not in drm_kc:
    anchor = 'source "drivers/gpu/drm/xlnx/Kconfig"\n'
    assert anchor in drm_kc, f"{drm_kc_path}: xlnx anchor not found"
    drm_kc = drm_kc.replace(anchor, anchor + 'source "drivers/gpu/drm/s9p/Kconfig"\n', 1)
    (src / drm_kc_path).write_text(drm_kc)
    print(f"{drm_kc_path}: s9p/Kconfig sourced")
else:
    print(f"{drm_kc_path}: s9p/Kconfig already sourced")

# --- brcmfmac: BCM4361 (WiFi of this phone) ----------------------------------
# Markuss Broks's upstream patch (wireless-next v3, 2026-08-20), plus the two
# extra BRCMF_PCIE_DEVICE lines maintainer Arend van Spriel asked for in
# review (2G-only 0x4420 and 5G-only 0x4421 variants). Chip rambase and
# sr_capable like the 4359, per the patch's chip.c hunk. Every insert is
# guarded on its own so a partial application never blocks a build.
hw_ids = "drivers/net/wireless/broadcom/brcm80211/include/brcm_hw_ids.h"
hw_path = src / hw_ids
hw = hw_path.read_text()
changed = False
if "BRCM_CC_4361_CHIP_ID" not in hw:
    anchor = "#define BRCM_CC_4359_CHIP_ID\t\t0x4359\n"
    assert anchor in hw, f"{hw_ids}: 4359 chip anchor not found"
    hw = hw.replace(anchor, anchor +
        "#define BRCM_CC_4361_CHIP_ID\t\t0x4361\n", 1)
    changed = True
if "BRCM_PCIE_4361_DEVICE_ID" not in hw:
    anchor = "#define BRCM_PCIE_4359_DEVICE_ID\t0x43ef\n"
    assert anchor in hw, f"{hw_ids}: 4359 device id anchor not found"
    hw = hw.replace(anchor, anchor +
        "#define BRCM_PCIE_4361_DEVICE_ID\t\t0x441f\n"
        "#define BRCM_PCIE_4361_2G_DEVICE_ID\t0x4420\n"
        "#define BRCM_PCIE_4361_5G_DEVICE_ID\t0x4421\n", 1)
    changed = True
if changed:
    hw_path.write_text(hw)
    print(f"{hw_ids}: 4361 IDs added")
else:
    print(f"{hw_ids}: 4361 already there")

pcie_c = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"
pc_path = src / pcie_c
pc = pc_path.read_text()
pc_changed = False
if 'BRCMF_FW_CLM_DEF(4361' not in pc:
    anchor = 'BRCMF_FW_DEF(4359, "brcmfmac4359-pcie");'
    assert anchor in pc, f"{pcie_c}: 4359 fw anchor not found"
    pc = pc.replace(anchor, anchor +
        '\nBRCMF_FW_CLM_DEF(4361, "brcmfmac4361-pcie");', 1)
    pc_changed = True
if "BRCMF_FW_ENTRY(BRCM_CC_4361_CHIP_ID" not in pc:
    anchor = "\tBRCMF_FW_ENTRY(BRCM_CC_4359_CHIP_ID, 0x000001FF, 4359),"
    assert anchor in pc, f"{pcie_c}: 4359 fw entry anchor not found"
    pc = pc.replace(anchor, anchor +
        "\n\tBRCMF_FW_ENTRY(BRCM_CC_4361_CHIP_ID, 0xFFFFFFFF, 4361),", 1)
    pc_changed = True
if "BRCM_PCIE_4361_DEVICE_ID, WCC" not in pc:
    anchor = "\tBRCMF_PCIE_DEVICE(BRCM_PCIE_4359_DEVICE_ID, WCC),"
    assert anchor in pc, f"{pcie_c}: 4359 device anchor not found"
    pc = pc.replace(anchor, anchor +
        "\n\tBRCMF_PCIE_DEVICE(BRCM_PCIE_4361_DEVICE_ID, WCC),"
        "\n\tBRCMF_PCIE_DEVICE(BRCM_PCIE_4361_2G_DEVICE_ID, WCC),"
        "\n\tBRCMF_PCIE_DEVICE(BRCM_PCIE_4361_5G_DEVICE_ID, WCC),", 1)
    pc_changed = True
# A cold-started chip can enumerate and still answer its first BAR read with
# all ones (chip_recognition "MMIO read failed" -> -ENODEV) when the host
# gets to it too early. Deferring the probe lets the driver core try again
# later in the boot instead of giving up on the only WLAN there is.
if "brcmf_pcie_probe: defer" not in pc:
    anchor = ("\t\tret = PTR_ERR(devinfo->ci);\n"
              "\t\tdevinfo->ci = NULL;\n"
              "\t\tgoto fail;\n")
    assert anchor in pc, f"{pcie_c}: chip_attach failure anchor not found"
    pc = pc.replace(anchor,
        "\t\tret = PTR_ERR(devinfo->ci);\n"
        "\t\tif (ret == -ENODEV)\t/* brcmf_pcie_probe: defer, chip not ready yet */\n"
        "\t\t\tret = -EPROBE_DEFER;\n"
        "\t\tdevinfo->ci = NULL;\n"
        "\t\tgoto fail;\n", 1)
    pc_changed = True
if pc_changed:
    pc_path.write_text(pc)
    print(f"{pcie_c}: 4361 support added")
else:
    print(f"{pcie_c}: 4361 already there")

chip_c = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c"
ch_path = src / chip_c
ch = ch_path.read_text()
ch_orig = ch
case_4359 = "case BRCM_CC_4359_CHIP_ID:"
case_4361 = "case BRCM_CC_4361_CHIP_ID:"
# tcm_rambase(): the vendor driver files the 4361 under the 4347 chip class
# (bcmdhd siutils.c) and loads it at CR4_4347_RAM_BASE = 0x170000
# (dhd_pcie.c) -- not at the 4359's rev-dependent 0x180000/0x160000 that the
# upstream patch used. 64 KB off is exactly "FW failed to initialize" with
# nothing else to show. Any earlier placement in the function is undone
# first, so the edit is idempotent.
head, sep, tail = ch.partition("static u32 brcmf_chip_tcm_rambase(")
assert sep, f"{chip_c}: tcm_rambase not found"
fn_end = tail.index("\n}\n")
fn, rest = tail[:fn_end], tail[fn_end:]
fn = re.sub(r"\tcase BRCM_CC_4361_CHIP_ID:[^\n]*\n", "", fn)
anchor = "\tcase BRCM_CC_43751_CHIP_ID:\n"
assert anchor in fn, f"{chip_c}: 43751 rambase anchor not found"
fn = fn.replace(anchor,
                "\t" + case_4361 + "\t/* 4347 class: CR4_4347_RAM_BASE */\n"
                + anchor, 1)
ch = head + sep + fn + rest
# sr_capable(): the retention_ctl check, like the 4359 (last occurrence).
idx = ch.rfind(case_4359)
assert idx >= 0
fn_start = ch.rfind("bool brcmf_chip_sr_capable(", 0, idx)
if case_4361 not in ch[fn_start:idx]:
    ch = ch[:idx] + case_4361 + "\n\t" + ch[idx:]
ch = ch.replace(case_4361 + "\n\t\t" + case_4359, case_4361 + "\n\t" + case_4359)
if ch != ch_orig:
    ch_path.write_text(ch)
    print(f"{chip_c}: 4361 rambase 0x170000 / sr_capable set")
else:
    print(f"{chip_c}: 4361 already there")

# --- brcmfmac: stamp H2D work items like Broadcom's DHD does -----------------
# Every host-to-dongle ring item carries a per-ring sequence number in the
# common header's 4th byte (DHD: cmn_msg_hdr_t.epoch = seqnum % 253, seqnum
# starting at 254) and a phase bit (flags bit 7, flipped whenever an
# allocation lands on the ring base). brcmfmac leaves both at zero. The
# BCM4361 B2 firmware verifies them: every unstamped item on the control
# ring came back as ring status BADOPTION (3) and the first ioctl timed out.
# Stamping happens centrally in brcmf_commonring_write_complete(), after the
# callers filled their headers; D2H rings are never written by the host, so
# only H2D rings are touched. Firmware that does not check ignores the bytes.
cr_h = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/commonring.h"
cr_h_path = src / cr_h
crh = cr_h_path.read_text()
if "stamp_ptr" not in crh:
    anchor = "\tbool was_full;\n"
    assert anchor in crh, f"{cr_h}: was_full anchor not found"
    crh = crh.replace(anchor, anchor +
        "\n\t/* H2D item stamping: next unstamped item, phase bit, sequence */\n"
        "\tu16 stamp_ptr;\n"
        "\tu8 phase;\n"
        "\tu32 seqnum;\n", 1)
    cr_h_path.write_text(crh)
    print(f"{cr_h}: stamp fields added")
else:
    print(f"{cr_h}: stamp fields already there")

cr_c = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/commonring.c"
cr_c_path = src / cr_c
crc = cr_c_path.read_text()
if "brcmf_commonring_stamp" not in crc:
    anchor = "void brcmf_commonring_config(struct brcmf_commonring *commonring, u16 depth,"
    assert anchor in crc, f"{cr_c}: config anchor not found"
    helper = (
        "/*\n"
        " * Every host-to-dongle work item carries a per-ring sequence number in\n"
        " * the common header's 4th byte (\"epoch\") and a phase bit in the flags\n"
        " * byte, the way Broadcom's DHD stamps them: epoch = seqnum % 253 with\n"
        " * seqnum starting at 254, phase (bit 7) flipped whenever an allocation\n"
        " * lands on the ring base. Firmware that verifies them (BCM4361 B2)\n"
        " * rejects unstamped items with ring status BADOPTION.\n"
        " */\n"
        "#define BRCMF_H2D_EPOCH_MODULO\t253\n"
        "#define BRCMF_H2D_EPOCH_INIT\t(BRCMF_H2D_EPOCH_MODULO + 1)\n"
        "#define BRCMF_H2D_PHASE_BIT\t0x80\n"
        "\n"
        "static void brcmf_commonring_stamp(struct brcmf_commonring *commonring)\n"
        "{\n"
        "\tu8 *item;\n"
        "\n"
        "\twhile (commonring->stamp_ptr != commonring->w_ptr) {\n"
        "\t\tif (commonring->stamp_ptr == 0)\n"
        "\t\t\tcommonring->phase ^= BRCMF_H2D_PHASE_BIT;\n"
        "\t\titem = commonring->buf_addr +\n"
        "\t\t       commonring->stamp_ptr * commonring->item_len;\n"
        "\t\titem[2] = (item[2] & ~BRCMF_H2D_PHASE_BIT) | commonring->phase;\n"
        "\t\titem[3] = commonring->seqnum % BRCMF_H2D_EPOCH_MODULO;\n"
        "\t\tcommonring->seqnum++;\n"
        "\t\tcommonring->stamp_ptr++;\n"
        "\t\tif (commonring->stamp_ptr == commonring->depth)\n"
        "\t\t\tcommonring->stamp_ptr = 0;\n"
        "\t}\n"
        "}\n"
        "\n"
    )
    crc = crc.replace(anchor, helper + anchor, 1)
    anchor = "\tcommonring->f_ptr = 0;\n}\n"
    assert anchor in crc, f"{cr_c}: config f_ptr anchor not found"
    crc = crc.replace(anchor,
        "\tcommonring->f_ptr = 0;\n"
        "\tcommonring->stamp_ptr = 0;\n"
        "\tcommonring->phase = 0;\n"
        "\tcommonring->seqnum = BRCMF_H2D_EPOCH_INIT;\n"
        "}\n", 1)
    anchor = "int brcmf_commonring_write_complete(struct brcmf_commonring *commonring)\n{\n"
    assert anchor in crc, f"{cr_c}: write_complete anchor not found"
    crc = crc.replace(anchor, anchor + "\tbrcmf_commonring_stamp(commonring);\n\n", 1)
    cr_c_path.write_text(crc)
    print(f"{cr_c}: H2D item stamping added")
else:
    print(f"{cr_c}: H2D item stamping already there")

# --- PCIe root complex for the Exynos 9810 (WiFi channel, BCM4361) -----------
insert_after(
    "drivers/pci/controller/dwc/Makefile",
    "obj-$(CONFIG_PCI_EXYNOS) += pci-exynos.o\n",
    "obj-$(CONFIG_PCIE_EXYNOS9810) += pcie-exynos9810.o\n",
    "PCIE_EXYNOS9810",
)

pcie_kconfig = f"""config PCIE_EXYNOS9810
{TAB}tristate "Samsung Exynos 9810 PCIe host controller (WiFi)"
{TAB}depends on PCI && OF && ARM64 && PCI_MSI
{TAB}select PCIE_DW_HOST
{TAB}select PCIE_DW
{TAB}help
{TAB}  PCIe channel 0 of the Exynos 9810, wired to the WiFi module on the
{TAB}  Galaxy S9/S9+. The PHY is programmed with Samsung's own CAL sequence
{TAB}  from the driver; the single endpoint is served with MSI only.

"""
insert_before(
    "drivers/pci/controller/dwc/Kconfig",
    "config PCIE_DW_EP\n",
    pcie_kconfig,
    "PCIE_EXYNOS9810",
)

# --- M3 cluster: vendor PMU defaults before PSCI CPU_ON ----------------------
# Without these six writes CPU4-7 take CPU_ON (returns 0) but never reach
# secondary_start_kernel: "CPU4: failed to come online", "failed in unknown
# state : 0x0". They are the CPUCL1 entries of pmucal_lpm_init in Samsung's
# 4.9.59 kernel (cal_if_init -> pmucal_system_init, before SMP). Cold-boot
# values from sboot: 0x1088 = c7150000, the five OPTION registers = 1, also
# after a warm reboot. Enabled by s9p_vendor_m3_defaults; the M3 must come up
# in the initial SMP bring-up (maxcpus=8), hotplug still fails.
insert_after(
    "arch/arm64/kernel/psci.c",
    "#include <linux/of.h>\n",
    "#include <linux/io.h>\n",
    "#include <linux/io.h>",
)

m3_defaults = """/* S9P-VENDOR-DEFAULTS: Samsung 4.9.59 pmucal_lpm_init, CPUCL1 entries. */
static bool s9p_vendor_m3_defaults;

static int __init s9p_vendor_m3_defaults_param(char *unused)
{
	s9p_vendor_m3_defaults = true;
	return 0;
}
early_param("s9p_vendor_m3_defaults", s9p_vendor_m3_defaults_param);

static int s9p_apply_vendor_m3_defaults(unsigned int cpu)
{
	static const struct {
		u32 offset, mask, value;
	} seq[] = {
		/* CPU_QCH_CLUSTER1_NONCPU_SYS_PWR_REG */
		{ 0x1088, 0xff000000, 0x8d000000 },
		/* MEMORY_CLUSTER1_CPU[0..3]_OPTION and NONCPU_OPTION */
		{ 0x2114, 3, 2 },
		{ 0x2180, 3, 2 },
		{ 0x21ec, 3, 2 },
		{ 0x2258, 3, 2 },
		{ 0x2384, 3, 2 },
	};
	void __iomem *pmu;
	unsigned int i;
	int err = 0;

	if (!s9p_vendor_m3_defaults ||
	    !of_machine_is_compatible("samsung,exynos9810") ||
	    (cpu_logical_map(cpu) & ~3ULL) != 0x100)
		return 0;
	pmu = ioremap(0x14060000, 0x8000);
	if (!pmu)
		return -ENOMEM;
	for (i = 0; i < ARRAY_SIZE(seq); i++) {
		u32 before = readl(pmu + seq[i].offset);
		u32 after;

		writel((before & ~seq[i].mask) | seq[i].value,
		       pmu + seq[i].offset);
		after = readl(pmu + seq[i].offset);
		pr_info("S9P vendor PMU %04x: %08x -> %08x mask=%08x\\n",
			seq[i].offset, before, after, seq[i].mask);
		if ((after & seq[i].mask) != seq[i].value) {
			err = -EIO;
			break;
		}
	}
	dsb(sy);
	iounmap(pmu);
	return err;
}
/* S9P-VENDOR-DEFAULTS-END */

"""
insert_before(
    "arch/arm64/kernel/psci.c",
    "static int cpu_psci_cpu_boot(unsigned int cpu)\n",
    m3_defaults,
    "S9P-VENDOR-DEFAULTS",
)

psci = src / "arch/arm64/kernel/psci.c"
s = psci.read_text()
old_on = "\tint err = psci_ops.cpu_on(cpu_logical_map(cpu), pa_secondary_entry);\n"
new_on = ("\tint err = s9p_apply_vendor_m3_defaults(cpu);\n\n"
          "\tif (err)\n\t\treturn err;\n"
          "\terr = psci_ops.cpu_on(cpu_logical_map(cpu), pa_secondary_entry);\n")
if new_on in s:
    print("arch/arm64/kernel/psci.c: M3 defaults call already there")
else:
    assert old_on in s, "arch/arm64/kernel/psci.c: cpu_on line not found"
    psci.write_text(s.replace(old_on, new_on, 1))
    print("arch/arm64/kernel/psci.c: M3 defaults call added")

print("PATCH_TREE_OK")

# The TSP IRQ is ready before the first failing I2C access. The first error
# resets HSI2C, after which an immediate reprobe works. Reinitialize only this
# board's TSP bus once per actual ACPM rail cycle, after both clocks are on.
# No error filtering, speculative extra transfer, other-bus reset or voltage
# change. Keep the existing normal error/recovery path for a genuine fault.
i2c_touch_path = src / 'drivers/i2c/busses/i2c-exynos5.c'
i2c_touch = i2c_touch_path.read_text()
if 'S9P_TOUCH_POST_POWER_RESET' not in i2c_touch:
    pos = i2c_touch.index('#include')
    i2c_touch = (i2c_touch[:pos] +
                 '#include <linux/soc/samsung/s9p-acpm.h> /* S9P_TOUCH_POST_POWER_RESET */\n' +
                 i2c_touch[pos:])
    anchor = '\tunsigned int\t\tatomic;\n'
    assert i2c_touch.count(anchor) == 1
    i2c_touch = i2c_touch.replace(anchor, anchor + '\tu32 s9p_touch_generation;\n', 1)
    anchor = '\tfor (i = 0; i < num; ++i) {\n'
    assert i2c_touch.count(anchor) == 1
    code = '''
\tif (IS_ENABLED(CONFIG_S9P_ACPM) &&
\t    of_machine_is_compatible("samsung,star2lte") &&
\t    !strcmp(dev_name(i2c->dev), "104b0000.i2c") &&
\t    num > 0 && msgs[0].addr == 0x48) {
\t\tu32 generation = s9p_acpm_touch_power_generation();

\t\tif (generation && generation != i2c->s9p_touch_generation) {
\t\t\tu32 before = readl(i2c->regs + HSI2C_TRANS_STATUS);
\t\t\texynos5_i2c_reset(i2c);
\t\t\ti2c->s9p_touch_generation = generation;
\t\t\tdev_info(i2c->dev,
\t\t\t\t "TSP post-power bus reset generation=%u status=%08x->%08x\\n",
\t\t\t\t generation, before,
\t\t\t\t readl(i2c->regs + HSI2C_TRANS_STATUS));
\t\t}
\t}

'''
    i2c_touch_path.write_text(i2c_touch.replace(anchor, code + anchor, 1))

# The G965N handover requires the ACPM LDO reset before the first touch I/O.
# Defer only this board's probe; real I2C errors after readiness still propagate.
touch_path = src / 'drivers/input/touchscreen/s6sy761.c'
touch = touch_path.read_text()
if 'S9P_TOUCH_RAIL_READY' not in touch:
    pos = touch.index('#include')
    touch = (touch[:pos] + '#include <linux/of.h>\n'
             '#include <linux/soc/samsung/s9p-acpm.h> /* S9P_TOUCH_RAIL_READY */\n'
             + touch[pos:])
    anchor = '\tif (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C |'
    assert touch.count(anchor) == 1
    touch = touch.replace(anchor,
        '\tif (IS_ENABLED(CONFIG_S9P_ACPM) &&\n'
        '\t    of_machine_is_compatible("samsung,star2lte") &&\n'
        '\t    !s9p_acpm_touch_ready())\n'
        '\t\treturn dev_err_probe(&client->dev, -EPROBE_DEFER,\n'
        '\t\t\t\t     "waiting for touch rail reset\\n");\n\n' + anchor, 1)
    touch_path.write_text(touch)


# touchscreen_parse_properties(..., true) configures MT axes. Check those,
# not unused legacy ABS_X/Y, and keep the warning for genuinely unset axes.
touch = touch_path.read_text()
if 'S9P_TOUCH_MT_AXIS_CHECK' not in touch:
    anchor = ('\tif (!input_abs_get_max(sdata->input, ABS_X) ||\n'
              '\t    !input_abs_get_max(sdata->input, ABS_Y)) {')
    assert touch.count(anchor) == 1
    touch = touch.replace(anchor,
        '\t/* S9P_TOUCH_MT_AXIS_CHECK: this input device reports multitouch axes. */\n'
        '\tif (!input_abs_get_max(sdata->input, ABS_MT_POSITION_X) ||\n'
        '\t    !input_abs_get_max(sdata->input, ABS_MT_POSITION_Y)) {', 1)
    touch_path.write_text(touch)


# Reviewed source-only fixes. These helpers never enable hardware or flash;
# they reject unknown source/patch hashes before modifying their target files.
subprocess.run([sys.executable, str(Path(__file__).with_name('g965n-wifi-diagnostics.py')),
                str(src)], check=True)
subprocess.run([sys.executable, str(Path(__file__).with_name('g965n-p2p-setup.py')),
                str(src)], check=True)
subprocess.run([sys.executable,
                str(Path(__file__).resolve().parents[2] / 'experiments/pmic/apply.py'),
                'apply', '--kernel-source', str(src)], check=True)

subprocess.run([sys.executable,
                str(Path(__file__).resolve().parents[2] / 'experiments/pinctrl/apply.py'),
                'apply', '--kernel-source', str(src)], check=True)

subprocess.run([sys.executable,
                str(Path(__file__).resolve().parents[2] / 'experiments/clkout/apply.py'),
                'apply', '--kernel-source', str(src)], check=True)
