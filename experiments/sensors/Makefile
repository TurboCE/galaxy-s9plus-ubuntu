# SPDX-License-Identifier: GPL-2.0-only
obj-m += zrn-bbd.o
zrn-bbd-y := bbd.o bbd_rpc_lh.o bcm_gps_spi.o bcm_gps_regs.o bcm_gps_mem.o zrn_bbd_board.o
ccflags-y += -I$(src) -include $(src)/zrn_compat.h -Wno-unused-function -Wno-unused-variable -Wno-missing-prototypes -Wno-declaration-after-statement
