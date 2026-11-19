# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'experiments/sensors/bbd.c'


class ControlWriteTests(unittest.TestCase):
    def test_write_dispatches_only_the_copied_command(self):
        source = SOURCE.read_text()
        start = source.index('ssize_t bbd_control_write(')
        end = source.index('ssize_t bbd_patch_read(', start)
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'control.c'
            binary = Path(directory) / 'control'
            test.write_text(STUBS + source[start:end] + CASES)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', '-Wno-unused-parameter', str(test),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#define __user
#define BBD_BUFF_SIZE 8192
#define DEBUG_1HZ_STAT
#define STAT_TX_LHD 1
#define IS_ERR(ptr) ((intptr_t)(ptr) < 0)
#define PTR_ERR(ptr) ((intptr_t)(ptr))
typedef long long loff_t;
struct file;

static size_t copies, dispatched, released, stat_bytes;
static const char *input;
static size_t expected_size;
static ssize_t result;
static int copy_error;

static char *memdup_user_nul(const char *source, size_t size)
{
    ++copies;
    if (copy_error)
        return (char *)(intptr_t)copy_error;
    char *buffer = malloc(size + 1);
    assert(buffer);
    memcpy(buffer, source, size);
    buffer[size] = '\0';
    return buffer;
}

static void kfree(char *buffer)
{
    ++released;
    free(buffer);
}

static void bbd_update_stat(int kind, size_t size)
{
    assert(kind == STAT_TX_LHD);
    stat_bytes += size;
}

static ssize_t bbd_control(const char *command, ssize_t length)
{
    ++dispatched;
    assert(command != input);
    assert(length == (ssize_t)expected_size);
    assert(!memcmp(command, input, expected_size));
    assert(command[expected_size] == '\0');
    return result;
}
'''


CASES = r'''
static void write_command(const char *command, size_t size, ssize_t expected_result)
{
    input = command;
    expected_size = size;
    result = expected_result;
    assert(bbd_control_write(NULL, input, expected_size, NULL) == expected_result);
}

int main(void)
{
    char full[BBD_BUFF_SIZE - 1];
    memset(full, 'a', sizeof(full));
    write_command(full, sizeof(full), sizeof(full));
    write_command("ready", 5, 5);
    write_command("finished", sizeof("finished"), -EIO);

    assert(bbd_control_write(NULL, NULL, 0, NULL) == 0);
    assert(bbd_control_write(NULL, NULL, BBD_BUFF_SIZE, NULL) == -EINVAL);
    copy_error = -EFAULT;
    assert(bbd_control_write(NULL, NULL, 4, NULL) == -EFAULT);
    copy_error = -ENOMEM;
    assert(bbd_control_write(NULL, NULL, 4, NULL) == -ENOMEM);
    assert(copies == 5);
    assert(dispatched == 3);
    assert(released == 3);
    assert(stat_bytes == sizeof(full) + 5 + sizeof("finished"));
    return 0;
}
'''
