# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/modem/link_device_memory_sbd.c'


class ModemSbdLayoutTests(unittest.TestCase):
    def test_actual_initializer_rejects_bad_layout_before_writing_shared_memory(self):
        source = SOURCE.read_text()
        initializer = source[
            source.index('static int sbd_validate_layout('):
            source.index('int create_sbd_link_device(')
        ]
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'sbd-layout.c'
            binary = Path(directory) / 'sbd-layout'
            test.write_text(STUBS + initializer + CASES)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', str(test), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>

#define U16_MAX UINT16_MAX
#define MAX_LINK_CHANNELS 16
#define ULDL 2
#define RDWR 2
#define DESC_RGN_OFFSET 2048
#define DESC_RGN_SIZE (65536 - DESC_RGN_OFFSET)
#define BUFF_RGN_OFFSET 65536
typedef uint16_t u16;
typedef uint32_t u32;
struct sbd_global_desc { unsigned char bytes[512]; };
struct sbd_link_attr { unsigned int rb_len[ULDL], buff_size[ULDL]; };
struct sbd_link_device {
    unsigned char *shmem;
    unsigned int shmem_size, num_channels;
    struct sbd_link_attr link_attr[MAX_LINK_CHANNELS];
    int ipc_dev;
};
static int initialized;
static void init_desc_alloc(struct sbd_link_device *sl, unsigned int offset)
{ assert(sl && offset == DESC_RGN_OFFSET); }
static void init_buff_alloc(struct sbd_link_device *sl, unsigned int offset)
{ assert(sl && offset == BUFF_RGN_OFFSET); }
static int init_sbd_ipc(struct sbd_link_device *sl, int ipc_dev, struct sbd_link_attr *attr)
{ assert(sl && !ipc_dev && attr); initialized++; return 0; }
static void print_sbd_config(struct sbd_link_device *sl) { assert(sl); }
'''


CASES = r'''
static unsigned char memory[BUFF_RGN_OFFSET + 64];

static void check_rejection(struct sbd_link_device *sl, int error)
{
    assert(init_sbd_link(sl) == error && !initialized);
    for (size_t i = 0; i < sizeof(memory); ++i)
        assert(memory[i] == 0xa5);
}

int main(void)
{
    const struct sbd_link_device valid = {
        .shmem = memory, .shmem_size = sizeof(memory), .num_channels = 1,
        .link_attr = { { .rb_len = { 2, 2 }, .buff_size = { 16, 16 } } },
    };
    struct sbd_link_device sl = valid;
    memset(memory, 0xa5, sizeof(memory));

    sl.shmem = NULL;
    check_rejection(&sl, -EINVAL);
    sl = valid;
    sl.shmem_size = BUFF_RGN_OFFSET - 1;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.shmem_size--;
    check_rejection(&sl, -ENOSPC);
    sl = valid; sl.num_channels = MAX_LINK_CHANNELS + 1;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.num_channels = 0;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.link_attr[0].rb_len[0] = U16_MAX + 1U;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.link_attr[0].buff_size[1] = U16_MAX + 1U;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.link_attr[0].rb_len[1] = 1;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.link_attr[0].buff_size[0] = 0;
    check_rejection(&sl, -EINVAL);
    sl = valid; sl.shmem_size = 8U * 1024 * 1024;
    sl.link_attr[0].rb_len[0] = U16_MAX;
    check_rejection(&sl, -ENOSPC);

    sl = valid;
    assert(init_sbd_link(&sl) == 0 && initialized == 1);
    assert(memory[DESC_RGN_OFFSET - 1] == 0xa5 && memory[DESC_RGN_OFFSET] == 0);
    assert(memory[BUFF_RGN_OFFSET - 1] == 0 && memory[BUFF_RGN_OFFSET] == 0xa5);
    return 0;
}
'''
