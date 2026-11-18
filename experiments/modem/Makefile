# SPDX-License-Identifier: GPL-2.0-only
obj-m += g965n-modem.o
g965n-modem-y := mcu_ipc.o shm_ipc.o modem_main.o modem_variation.o modem_io_device.o modem_utils.o modem_dump.o link_device_shmem.o link_device_memory_snapshot.o link_device_memory_flow_control.o link_device_memory_debug.o link_device_memory_sbd.o modem_notifier.o modem_ctrl_ss310ap.o zrn_cp_pmu.o zrn_board.o zrn_overlay_blob.o
ccflags-y += -I$(src) -I$(src)/compat -include $(src)/g965n_compat.h -DCONFIG_OPTION_REGION=\"KOR\" -Wno-unused-function -Wno-unused-variable -Wno-missing-prototypes -Wno-declaration-after-statement -Wno-missing-declarations
