# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'experiments/sensors/bcm_gps_spi.c'


class SensorSpiTransferTests(unittest.TestCase):
    def test_only_complete_spi_responses_are_exposed(self):
        source = SOURCE.read_text()
        start = source.index('int bcm_spi_sync(')
        end = source.index('static bool bcm_ssi_settle_patch_tail(', start)
        self.run_case(STUBS + source[start:end] + CASES)

    def test_settle_wait_is_limited_to_the_observed_patch_transition(self):
        source = SOURCE.read_text()
        start = source.index('static bool bcm_ssi_settle_patch_tail(')
        end = source.index('static int bcm_ssi_tx(', start)
        self.run_case(SETTLE_STUBS + source[start:end] + SETTLE_CASES)

    def run_case(self, code):
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'transfer.c'
            binary = Path(directory) / 'transfer'
            test.write_text(code)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', '-Wno-unused-parameter', str(test), '-o', str(binary)],
                           check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <string.h>

struct spi_device { int dev; };
struct spi_transfer { unsigned int len; void *tx_buf, *rx_buf; };
struct spi_message {
    struct spi_device *spi;
    struct spi_transfer *transfer;
    unsigned int actual_length;
};
struct bcm_spi_priv { struct spi_device *spi; };
static struct spi_device device;
static unsigned char tx[8], rx[8];
static int spi_error, errors, tx_logs, rx_logs;
static unsigned int response_length;

#define dev_err(target, ...) do { assert((target) == &device.dev); ++errors; } while (0)

static void spi_message_init(struct spi_message *message)
{ memset(message, 0, sizeof(*message)); }

static void spi_message_add_tail(struct spi_transfer *transfer, struct spi_message *message)
{ message->transfer = transfer; }

static int spi_sync(struct spi_device *spi, struct spi_message *message)
{
    assert(spi == &device && message->spi == spi);
    assert(message->transfer->len == sizeof(tx));
    assert(message->transfer->tx_buf == tx && message->transfer->rx_buf == rx);
    message->actual_length = response_length;
    return spi_error;
}

static void pk_log(const char *direction, const unsigned char *data, int length)
{
    assert(length == sizeof(tx));
    if (!strcmp(direction, "w")) {
        assert(data == tx);
        ++tx_logs;
    } else {
        assert(!strcmp(direction, "r") && data == rx);
        ++rx_logs;
    }
}
'''


CASES = r'''
int main(void)
{
    struct bcm_spi_priv priv = { .spi = &device };
    response_length = sizeof(tx);
    assert(bcm_spi_sync(&priv, tx, rx, sizeof(tx), 8) == 0);
    assert(rx_logs == 1 && !errors);

    response_length = sizeof(tx) - 1;
    assert(bcm_spi_sync(&priv, tx, rx, sizeof(tx), 8) == -EIO);
    response_length = 0;
    assert(bcm_spi_sync(&priv, tx, rx, sizeof(tx), 8) == -EIO);
    spi_error = -ETIMEDOUT;
    assert(bcm_spi_sync(&priv, tx, rx, sizeof(tx), 8) == -ETIMEDOUT);
    assert(tx_logs == 4 && rx_logs == 1 && errors == 3);
    return 0;
}
'''


SETTLE_STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>

#define NSEC_PER_MSEC 1000000ULL
typedef uint64_t u64;
struct bcm_spi_priv { unsigned int tx_last_complete_len; u64 tx_last_complete_ns; };
static bool patch_tail_settle, strict_tx_ack, pending;
static u64 current_time;
static unsigned int waits;
static bool bbd_patch_watchdog_pending(void) { return pending; }
static u64 ktime_get_ns(void) { return current_time; }
static void usleep_range(unsigned int low, unsigned int high)
{ assert(low == 8000 && high == 9000); ++waits; }
'''


SETTLE_CASES = r'''
int main(void)
{
    struct bcm_spi_priv priv = { .tx_last_complete_len = 14, .tx_last_complete_ns = 100 };
    pending = strict_tx_ack = true;
    current_time = priv.tx_last_complete_ns + 49 * NSEC_PER_MSEC;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    patch_tail_settle = true;
    assert(bcm_ssi_settle_patch_tail(&priv, 36) && waits == 1);
    assert(!bcm_ssi_settle_patch_tail(&priv, 35));
    priv.tx_last_complete_len = 13;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    priv.tx_last_complete_len = 14;
    pending = false;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    pending = true;
    strict_tx_ack = false;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    strict_tx_ack = true;
    current_time = priv.tx_last_complete_ns + 39 * NSEC_PER_MSEC;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    current_time = priv.tx_last_complete_ns + 61 * NSEC_PER_MSEC;
    assert(!bcm_ssi_settle_patch_tail(&priv, 36));
    assert(waits == 1);
    return 0;
}
'''
