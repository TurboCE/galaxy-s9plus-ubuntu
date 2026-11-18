/* SPDX-License-Identifier: GPL-2.0-only */
/* API client for the distribution's separately licensed sysprof-capture library.
 * No upstream implementation or headers are vendored. Output excludes mark
 * messages (which may contain titles), but still keep raw captures private.
 * cc shell-profile-marks.c -o marks $(pkg-config --cflags --libs sysprof-capture-4)
 */
#include <sysprof-capture.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    SysprofCaptureReader *reader = sysprof_capture_reader_new(argv[1]);
    if (!reader) return 3;
    SysprofCaptureFrameType type;
    while (sysprof_capture_reader_peek_type(reader, &type)) {
        if (type == SYSPROF_CAPTURE_FRAME_MARK) {
            const SysprofCaptureMark *mark = sysprof_capture_reader_read_mark(reader);
            if (!mark) break;
            printf("%lld\t%lld\t%.24s\t%.40s\n", (long long)mark->frame.time,
                   (long long)mark->duration, mark->group, mark->name);
        } else if (!sysprof_capture_reader_skip(reader)) break;
    }
    sysprof_capture_reader_unref(reader);
    return 0;
}
