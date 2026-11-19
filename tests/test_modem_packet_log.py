# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


MODEM = Path(__file__).resolve().parents[1] / 'experiments/modem'


class PacketLogTests(unittest.TestCase):
    def test_logs_only_available_packet_prefix(self):
        source = (MODEM / 'modem_utils.c').read_text()
        start = source.index('int pr_buffer(')
        end = source.index('/* flow control CM', start)
        header = (MODEM / 'modem_utils.h').read_text().splitlines()
        limit = next(line for line in header if line.startswith('#define MIF_PACKET_LOG_BYTES '))
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'packet-log.c'
            binary = Path(directory) / 'packet-log'
            test.write_text(limit + '\n' + STUBS + source[start:end] + CASES)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', str(test), '-o', str(binary)],
                           check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#define MIF_TAG "mif"
#define min_t(type, a, b) ((type)(a) < (type)(b) ? (type)(a) : (type)(b))
typedef uint8_t u8;
struct sk_buff {
    const u8 *head, *fragment;
    unsigned int len, head_len;
};
static unsigned int copies, log_lines;
static const u8 *expected_prefix;
static size_t expected_total;
static int expected_length;

static const void *skb_header_pointer(const struct sk_buff *skb, int offset, int len, u8 *scratch)
{
    assert(offset == 0 && len == expected_length);
    if ((unsigned int)len <= skb->head_len)
        return skb->head;
    if (!skb->fragment)
        return NULL;
    memcpy(scratch, skb->head, skb->head_len);
    memcpy(scratch + skb->head_len, skb->fragment, len - skb->head_len);
    ++copies;
    return scratch;
}

static int pr_info(const char *format, const char *subsystem, const char *tag,
                   size_t total, int len, const void *prefix, const char *suffix)
{
    assert(!strcmp(format, "%s: %s(%zu): %*ph%s\n"));
    assert(!strcmp(subsystem, "mif") && !strcmp(tag, "test"));
    assert(total == expected_total && len == expected_length);
    assert(!memcmp(prefix, expected_prefix, len));
    assert(!strcmp(suffix, (size_t)len == total ? "" : " ..."));
    ++log_lines;
    return len;
}
'''


CASES = r'''
int main(void)
{
    static const u8 payload[] = "abcdefghijklmnopqrst";
    struct sk_buff skb = { .head = payload, .len = 4, .head_len = 4 };
    expected_prefix = payload;
    expected_total = expected_length = 4;
    assert(pr_skb("test", &skb) == 4 && !copies && log_lines == 1);

    skb.len = sizeof(payload) - 1;
    skb.fragment = payload + skb.head_len;
    expected_total = skb.len;
    expected_length = 16;
    assert(pr_skb("test", &skb) == 16 && copies == 1 && log_lines == 2);

    skb.fragment = NULL;
    assert(pr_skb("test", &skb) == -EFAULT && log_lines == 2);
    assert(pr_buffer("test", payload, expected_total) == 16);

    skb.len = skb.head_len = expected_total = expected_length = 0;
    assert(pr_skb("test", &skb) == 0 && log_lines == 4);
    return 0;
}
'''
