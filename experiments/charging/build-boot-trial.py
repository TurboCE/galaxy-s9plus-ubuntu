#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only: verify a charger trial wrapper and preserve unrelated BOOT parts."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
parts=runpy.run_path(str(REPO/'scripts/build/boot_parts.py'))['parts']
tree=runpy.run_path(str(REPO/'experiments/modem/verify-overlay.py'))['tree']


def patch_charge_ceiling(blob):
    before=tree(blob)
    compatible=before.get('',{}).get('compatible',b'').split(b'\0')
    if b'samsung,star2lte' not in compatible or b'samsung,exynos9810' not in compatible:
        raise ValueError('Expected the reviewed star2lte Exynos9810 DTB')
    paths=[p for p,v in before.items() if v.get('compatible')==b'simple-battery\0']
    if len(paths)!=1:raise ValueError('Expected exactly one simple battery')
    path=paths[0];key='constant-charge-voltage-max-microvolt'
    if before[path].get(key)!=struct.pack('>I',4400000):raise ValueError('Unexpected base charge ceiling')
    total,pos,strings=struct.unpack_from('>III',blob,4);stack=[];changed=0;result=bytearray(blob)
    while pos+4<=total:
        token=struct.unpack_from('>I',blob,pos)[0];pos+=4
        if token==1:
            end=blob.index(0,pos,total);stack.append(blob[pos:end].decode());pos=(end+4)&~3
        elif token==2:stack.pop()
        elif token==3:
            length,name=struct.unpack_from('>II',blob,pos);pos+=8
            field=blob[strings+name:blob.index(0,strings+name,total)].decode()
            if '/'.join(stack)==path and field==key:
                if length!=4:raise ValueError('Invalid charge ceiling field')
                struct.pack_into('>I',result,pos,4350000);changed+=1
            pos=(pos+length+3)&~3
        elif token==4:pass
        elif token==9:break
        else:raise ValueError('Invalid FDT token')
    expected={p:dict(v) for p,v in before.items()};expected[path][key]=struct.pack('>I',4350000)
    if changed!=1 or tree(bytes(result))!=expected:raise ValueError('DT changed outside reviewed charge ceiling')
    return bytes(result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-number',type=int,choices=(49,50),default=49)
    p.add_argument('--base-boot',type=Path,required=True);p.add_argument('--base-dtb',type=Path,required=True)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--wrapper',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old=parts(a.base_boot.read_bytes());dtb=patch_charge_ceiling(a.base_dtb.read_bytes()) if a.build_number==49 else a.base_dtb.read_bytes();image=a.image.read_bytes();wrapper=a.wrapper.read_bytes()
    expected_base=b'#48 SMP PREEMPT ' if a.build_number==49 else b'#49 SMP PREEMPT '
    if a.build_number==50:
        nodes=tree(dtb); batteries=[v for v in nodes.values() if v.get('compatible')==b'simple-battery\0']
        if len(batteries)!=1 or batteries[0].get('constant-charge-voltage-max-microvolt')!=struct.pack('>I',4350000):raise ValueError('Expected qualified 4.35V #49 DTB')
    if old['kernel'].count(a.base_dtb.read_bytes())!=1 or expected_base not in old['kernel']:
        raise ValueError('Expected the exact reviewed #48 base wrapper/DTB')
    if image[56:60]!=b'ARM\x64' or ('#'+str(a.build_number)+' SMP PREEMPT ').encode() not in image:raise ValueError('Unreviewed trial image')
    if wrapper.count(image)!=1 or wrapper.count(dtb)!=1:raise ValueError('Wrapper does not contain the exact reviewed image and DTB')
    a.output.mkdir(mode=0o700)
    (a.output/'outer-dt.img').write_bytes(old['dt'])
    target=a.output/('boot-charging'+str(a.build_number)+'.img')
    subprocess.run([sys.executable,str(REPO/'scripts/build/mkboot.py'),'--ref',str(a.base_boot),'--kernel',str(a.wrapper),'--dt',str(a.output/'outer-dt.img'),'-o',str(target)],check=True)
    new=parts(target.read_bytes())
    if new['kernel']!=wrapper or any(new[k]!=old[k] for k in ('ramdisk','second','dt')):raise ValueError('Unrelated BOOT component changed')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    receipt={'model':'SM-G965N','base_boot_sha256':sha(a.base_boot.read_bytes()),'boot_sha256':sha(target.read_bytes()),'boot_bytes':target.stat().st_size,'image_sha256':sha(image),'dtb_sha256':sha(dtb),'hardware_validation':'pending'}
    (a.output/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Charger trial BOOT packaged and unpacked; no device writes')


if __name__=='__main__':main()
