# SPDX-License-Identifier: GPL-2.0-only
"""Run the actual probe callback with register/IRQ mocks before hardware use."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CacheAuditTest(unittest.TestCase):
    def test_actual_callback_selects_only_present_caches_and_restores_selector(self):
        source = (ROOT / 'experiments/cpu-cache-audit/g965n-cache-audit.c').read_text()
        callback = source[source.index('struct cache_snapshot {'):source.index('static int __init audit_init')]
        prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
typedef uint64_t u64;
#define NR_CPUS 8
static u64 midr_el1, clidr_el1, id_aa64mmfr2_el1, csselr_el1;
static unsigned int reads, barriers, irq;
static u64 observed[14];
static unsigned int smp_processor_id(void) { return 0; }
static u64 read_ccsidr(void) {
    assert(irq == 1); assert(reads < 14);
    observed[reads++] = csselr_el1;
    return 0x1000 + csselr_el1;
}
#define read_sysreg(reg) (read_##reg())
#define read_midr_el1() (midr_el1)
#define read_clidr_el1() (clidr_el1)
#define read_id_aa64mmfr2_el1() (id_aa64mmfr2_el1)
#define read_csselr_el1() (csselr_el1)
#define read_ccsidr_el1() read_ccsidr()
#define write_sysreg(v, reg) do { assert(irq == 1); reg = (v); } while (0)
#define local_irq_save(flags) do { flags = irq; irq = 1; } while (0)
#define local_irq_restore(flags) do { irq = flags; } while (0)
#define isb() do { assert(irq == 1); barriers++; } while (0)
'''
        suffix = r'''
int main(void) {
    unsigned int type, prior_irq;
    for (type = 0; type < 8; type++) {
        for (prior_irq = 0; prior_irq < 2; prior_irq++) {
            reads = barriers = 0; irq = prior_irq; csselr_el1 = 10;
            clidr_el1 = type; memset(snapshots, 0, sizeof(snapshots));
            snapshot_cpu(0);
            assert(irq == prior_irq); assert(csselr_el1 == 10);
            assert(snapshots[0].sampled);
            assert(snapshots[0].selector_before == snapshots[0].selector_after);
            assert(reads == (type == 3 ? 2 : type >= 1 && type <= 4 ? 1 : 0));
            assert(barriers == reads + 1);
            if (type == 1) assert(observed[0] == 1);
            if (type == 2 || type == 4) assert(observed[0] == 0);
            if (type == 3) assert(observed[0] == 0 && observed[1] == 1);
        }
    }
    reads = barriers = irq = 0; csselr_el1 = 4;
    clidr_el1 = 3 | (4 << 3) | (4 << 6);
    snapshot_cpu(0);
    assert(reads == 4 && observed[0] == 0 && observed[1] == 1);
    assert(observed[2] == 2 && observed[3] == 4);
    assert(csselr_el1 == 4 && irq == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'callback.c'
            path.write_text(prefix + callback + suffix)
            exe = path.with_suffix('')
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Wno-unused-parameter',
                            '-Werror', str(path), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
