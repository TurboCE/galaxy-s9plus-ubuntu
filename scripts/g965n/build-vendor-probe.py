#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build only: original Bionic dependency probe, with reviewed owner inputs.

No device access, daemon launch or flashing. Output/owner libraries stay private.
Use a Linux builder with aarch64-linux-gnu-gcc/binutils and headers_install UAPI.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

PINS={
 'libc.so':'2308e1676ab55cebd2c1207c1149038929132b6da8533e590fce943fe34fd506',
 'libdl.so':'d49dba9e449f25ebfed4edfa2af6b811ba36bd1fe6683475cd8e5821fefe5acd',
 'linker64':'20a066d043128ff56bc115c172cccb5d7db65f5c1416a8248a069ba6a57069be',
}


def checked_inputs(directory):
    for name,digest in PINS.items():
        path=directory/name;info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Unreviewed owner Bionic ABI: '+name)
        data=path.read_bytes()
        if data[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(data[18:20],'little')!=183:
            raise ValueError('Expected owner AArch64 ELF64: '+name)


def build(inputs,headers,output):
    checked_inputs(inputs)
    include=headers/'include'
    for name in ('asm/types.h','asm/unistd.h','linux/seccomp.h','linux/filter.h'):
        if not (include/name).is_file():raise ValueError('Run headers_install first: '+name)
    source=Path(__file__).resolve().parents[2]/'experiments/modem/vendor-probe/probe.c'
    output.mkdir(mode=0o700)  # Preserve all prior builds/receipts.
    binary=output/'probe'
    command=['aarch64-linux-gnu-gcc','-Wall','-Wextra','-Werror','-I'+str(include),
        '-fPIE','-fstack-protector-strong','-fno-builtin','-nostdlib','-pie',
        '-Wl,-e,_start','-Wl,--dynamic-linker=/system/bin/linker64','-Wl,-z,relro,-z,now',
        # Bionic libc's __loader_shared_globals comes from the interpreter's
        # ld-android.so identity; never invent a glibc-compatible replacement.
        '-Wl,--no-undefined,--allow-shlib-undefined',str(source),'-L'+str(inputs),
        '-Wl,-rpath-link,'+str(inputs),'-l:libc.so','-l:libdl.so','-o',str(binary)]
    subprocess.run(command,check=True)
    info=subprocess.check_output(['aarch64-linux-gnu-readelf','-l',str(binary)],text=True)
    if '[Requesting program interpreter: /system/bin/linker64]' not in info:
        raise ValueError('Unexpected executable interpreter')
    binary.chmod(0o700)
    receipt={'profile':'g965n-fva2-bionic-inspect-only','inputs':PINS,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'compiler':subprocess.check_output(['aarch64-linux-gnu-gcc','--version'],text=True).splitlines()[0],
        'ril_init_called':False,'build_only':True}
    path=output/'build.json';path.write_text(json.dumps(receipt,indent=2)+'\n');path.chmod(0o600)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-bionic',type=Path,required=True)
    parser.add_argument('--uapi',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    print(json.dumps(build(args.owner_bionic.resolve(),args.uapi.resolve(),args.output.resolve())))


if __name__=='__main__':main()
