# SPDX-License-Identifier: GPL-2.0-only
obj-m += g965n-thermal-qos.o
# Separate read-only QA module; excluded from ordinary cooling deployment.
obj-$(G965N_GPU_SNAPSHOT) += g965n-gpu-idle-snapshot.o
ccflags-y += -I$(srctree)/drivers/gpu/drm/panfrost
