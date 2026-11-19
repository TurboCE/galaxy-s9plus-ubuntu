/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G965N_IIO_UAPI_H
#define G965N_IIO_UAPI_H
#ifdef __KERNEL__
#include <linux/types.h>
typedef __le32 g965n_le32;
typedef __le64 g965n_le64;
#else
#include <stdint.h>
typedef uint32_t g965n_le32;
typedef uint64_t g965n_le64;
#endif
#define G965N_IIO_VERSION 1U
#define G965N_IIO_FRAME_BYTES 48U
#define G965N_IIO_ACCEL 1U
#define G965N_IIO_LIGHT 2U
#define G965N_IIO_HEARTBEAT 3U
#define G965N_IIO_PRESSURE 4U
#define G965N_IIO_PROXIMITY 5U
#define G965N_IIO_GYRO 6U
#define G965N_IIO_RANGE_8G_CONFIRMED 1U
/* Little endian, exactly48bytes. value[] encodes signed32-bit integers.
 * seq starts at1, strictly increases within an exclusive writer session.
 * ACCEL: three signed16-bit raw counts, RANGE_8G_CONFIRMED mandatory.
 * LIGHT: nonnegative integer lux in value[0]; other values/flags zero.
 * HEARTBEAT: all values/flags zero. reserved[] always zero.
 * PRESSURE: positive LPS22H raw counts (24-bit signed range) in value[0].
 * The other values and flags are zero.
 * PROXIMITY: firmware detection bit in value[0]; other values/flags zero.
 * GYRO: three signed32 SSP samples in hub axes; flags zero.
 */
struct g965n_iio_frame {
 g965n_le32 version, size;
 g965n_le64 seq;
 g965n_le32 type, flags;
 g965n_le32 value[3], reserved[3];
};
#endif
