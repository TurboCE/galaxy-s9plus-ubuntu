/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G965N_BRIDGE_CORE_H
#define G965N_BRIDGE_CORE_H
#include "g965n-iio-uapi.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/byteorder/generic.h>
#define bridge_le32(v) le32_to_cpu(v)
#define bridge_le64(v) le64_to_cpu(v)
#else
#include <stdbool.h>
#include <errno.h>
typedef uint32_t u32; typedef uint64_t u64; typedef int32_t s32;
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define bridge_le32(v) (v)
#define bridge_le64(v) (v)
#else
#define bridge_le32(v) __builtin_bswap32(v)
#define bridge_le64(v) __builtin_bswap64(v)
#endif
#endif
#define G965N_FRESH_NS 2000000000ULL
struct bridge_sample { bool valid; s32 value[3]; u64 when; };
struct bridge_cache {
 struct bridge_sample accel, light, pressure, proximity, gyro;
 u64 heartbeat, seq;
 bool connected;
};
struct bridge_decoded { u64 seq; u32 type; s32 value[3]; };
static inline int bridge_decode(const struct g965n_iio_frame *p, unsigned int bytes,
                                u64 last, struct bridge_decoded *out)
{
 unsigned int i; u32 flags;
 if (bytes != G965N_IIO_FRAME_BYTES) return -EMSGSIZE;
 if (bridge_le32(p->version) != G965N_IIO_VERSION) return -EPROTO;
 if (bridge_le32(p->size) != G965N_IIO_FRAME_BYTES) return -EMSGSIZE;
 for (i=0;i<3;i++) if (bridge_le32(p->reserved[i])) return -EINVAL;
 out->seq=bridge_le64(p->seq);out->type=bridge_le32(p->type);
 if (!out->seq || (!last && out->seq!=1) || out->seq<=last) return -ERANGE;
 flags=bridge_le32(p->flags);
 for (i=0;i<3;i++) out->value[i]=(s32)bridge_le32(p->value[i]);
 switch (out->type) {
 case G965N_IIO_ACCEL:
  if (flags!=G965N_IIO_RANGE_8G_CONFIRMED) return -EINVAL;
  for (i=0;i<3;i++) if (out->value[i]<-32768 || out->value[i]>32767) return -ERANGE;
  break;
 case G965N_IIO_LIGHT:
  if (flags || out->value[0]<0 || out->value[1] || out->value[2]) return -EINVAL;
  break;
 case G965N_IIO_PRESSURE:
  if (flags || out->value[1] || out->value[2]) return -EINVAL;
  if (out->value[0]<=0 || out->value[0]>0x7fffff) return -ERANGE;
  break;
 case G965N_IIO_PROXIMITY:
  if (flags || out->value[1] || out->value[2]) return -EINVAL;
  if (out->value[0]<0 || out->value[0]>1) return -ERANGE;
  break;
 case G965N_IIO_HEARTBEAT:
  if (flags || out->value[0] || out->value[1] || out->value[2]) return -EINVAL;
  break;
 case G965N_IIO_GYRO:
  if (flags) return -EINVAL;
  break;
 default:return -EINVAL;
 }
 return 0;
}
static inline bool bridge_matrix_valid(const int *m, unsigned int count)
{
 unsigned int r,c;int row,col;
 if (count!=9) return false;
 for (r=0;r<9;r++) if (m[r]<-1 || m[r]>1) return false;
 for (r=0;r<3;r++) {
  row=col=0;
  for (c=0;c<3;c++) {
   row+=m[r*3+c]*m[r*3+c]; col+=m[c*3+r]*m[c*3+r];
  }
  if (row!=1 || col!=1) return false;
 }
 return true;
}
static inline bool bridge_fresh(u64 stamp,u64 now)
{ return now>=stamp && now-stamp<=G965N_FRESH_NS; }
static inline void bridge_update(struct bridge_cache *c,const struct bridge_decoded *p,u64 now)
{
 struct bridge_sample *s;
 unsigned int i;
 switch (p->type) {
 case G965N_IIO_ACCEL: s=&c->accel; break;
 case G965N_IIO_LIGHT: s=&c->light; break;
 case G965N_IIO_PRESSURE: s=&c->pressure; break;
 case G965N_IIO_PROXIMITY: s=&c->proximity; break;
 case G965N_IIO_GYRO: s=&c->gyro; break;
 default: s=NULL; break;
 }
 if (s) {
  for(i=0;i<3;i++) s->value[i]=p->value[i];
  s->valid=true;s->when=now;
 }
 c->seq=p->seq;c->heartbeat=now;
}
static inline int bridge_read(const struct bridge_cache *c,u32 type,unsigned int axis,u64 now,s32 *value)
{
 const struct bridge_sample *s;
 if (axis>2 || (type!=G965N_IIO_ACCEL && type!=G965N_IIO_GYRO && axis)) return -EINVAL;
 switch (type) {
 case G965N_IIO_ACCEL: s=&c->accel; break;
 case G965N_IIO_LIGHT: s=&c->light; break;
 case G965N_IIO_PRESSURE: s=&c->pressure; break;
 case G965N_IIO_PROXIMITY: s=&c->proximity; break;
 case G965N_IIO_GYRO: s=&c->gyro; break;
 default: return -EINVAL;
 }
 if (!c->connected || !bridge_fresh(c->heartbeat,now) || !s->valid) return -ENODATA;
 if ((type==G965N_IIO_ACCEL || type==G965N_IIO_PRESSURE || type==G965N_IIO_GYRO) &&
     !bridge_fresh(s->when,now)) return -ENODATA;
 *value=s->value[axis];return 0;
}
#endif
