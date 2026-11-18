# SPDX-License-Identifier: GPL-2.0-only
# The host helper downloads and checks this official Ubuntu Base archive first.
FROM scratch
ADD ubuntu-base-24.04.3-base-amd64.tar.gz /
ENV DEBIAN_FRONTEND=noninteractive BUILD=/build BUILD_IMG=""
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential bc bison flex libssl-dev libelf-dev libncurses-dev \
    gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu clang lld llvm \
    device-tree-compiler python3 python3-pip git wget curl ca-certificates \
    debootstrap qemu-user-static binfmt-support cpio gzip lz4 zstd xz-utils \
    rsync kmod fakeroot e2fsprogs dosfstools android-sdk-libsparse-utils \
    openssl file wireless-regdb && rm -rf /var/lib/apt/lists/*
WORKDIR /src
CMD ["bash"]
