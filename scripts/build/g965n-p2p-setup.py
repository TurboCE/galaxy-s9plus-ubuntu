#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check/diagnose required G965N P2P setup operations in pinned ISC Linux code.

No device access. Original Broadcom ISC notice remains in the transformed C.
Linux v7.1 p2p.c Copyright(c)2012 Broadcom Corporation supplies protocol facts.
"""
import argparse
import hashlib
from pathlib import Path

REL=Path('drivers/net/wireless/broadcom/brcm80211/brcmfmac/p2p.c')
ORIGINAL='048df2fa9593fa4bf65a3b459e9fca8ae45860bd6dc10a329d026984be6d3c3f'
PREVIOUS='cffa5000c6b36b83542f34148c8d56f568d7c1b6af843031a2b1dd2847bdea89'
MASK_VERSION='d8f6ea105146113785e485be2410f0c953a5bc5a835979422e7ed76f5d1fee84'
PATCHED='adc908e9f1aac6bf2d6b6c53989f0e0f864aaf2d1e4d19a9286ddaf7eaa07b97'
HELPERS=r'''/* G965N: no network identifiers or command data in diagnostics. */
static bool brcmf_g965n_checked_p2p(struct brcmf_if *ifp)
{
	return of_machine_is_compatible("samsung,star2lte") &&
	       ifp->drvr->bus_if->chip == BRCM_CC_4361_CHIP_ID &&
	       ifp->ifidx == 0;
}

static void brcmf_g965n_p2p_step(struct brcmf_if *ifp, unsigned int stage, int ret)
{
	if (brcmf_g965n_checked_p2p(ifp) && net_ratelimit())
		wiphy_info(ifp->drvr->wiphy, "g965n_p2p_setup stage=%u ret=%d\n", stage, ret);
}

'''
BODY=r'''static int brcmf_p2p_set_firmware(struct brcmf_if *ifp, u8 *p2p_mac)
{
	struct brcmf_pub *drvr = ifp->drvr;
	bool checked = brcmf_g965n_checked_p2p(ifp);
	s32 ret;

	ret = brcmf_fil_cmd_int_set(ifp, BRCMF_C_DOWN, 1);
	brcmf_g965n_p2p_step(ifp, 0, ret);
	if (checked && ret)
		return ret;
	ret = brcmf_fil_iovar_int_set(ifp, "apsta", 1);
	brcmf_g965n_p2p_step(ifp, 1, ret);
	if (checked && ret) {
		/* Preserve the normal UP restoration even if APSTA was rejected. */
		int restored = brcmf_fil_cmd_int_set(ifp, BRCMF_C_UP, 1);
		brcmf_g965n_p2p_step(ifp, 2, restored);
		return ret;
	}
	ret = brcmf_fil_cmd_int_set(ifp, BRCMF_C_UP, 1);
	brcmf_g965n_p2p_step(ifp, 2, ret);
	if (checked && ret)
		return ret;
	/* The device-address override requires discovery disabled. */
	ret = brcmf_fil_iovar_int_set(ifp, "p2p_disc", 0);
	brcmf_g965n_p2p_step(ifp, 3, ret);
	if (checked && ret)
		return ret;
	ret = brcmf_fil_iovar_data_set(ifp, "p2p_da_override", p2p_mac, ETH_ALEN);
	brcmf_g965n_p2p_step(ifp, 4, ret);
	if (ret)
		bphy_err(drvr, "failed to update device address ret %d\n", ret);
	return ret;
}'''

def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('P2P source anchor changed')
    return text.replace(old,new,1)


OBSERVER=r'''/* Read back the subscribed IF bit; do not fabricate/replay events or masks. */
static void brcmf_g965n_p2p_event_mask(struct brcmf_if *ifp)
{
	u8 mask[256] = { 0 };
	unsigned int len = ifp->drvr->fweh->event_mask_len;
	unsigned int enabled = 0;
	int ret = -EINVAL;

	if (len > BRCMF_E_IF / 8 && len <= sizeof(mask)) {
		ret = brcmf_fil_iovar_data_get(ifp, "event_msgs", mask, len);
		if (!ret)
			enabled = !!(mask[BRCMF_E_IF / 8] & (1U << (BRCMF_E_IF % 8)));
	}
	if (net_ratelimit())
		wiphy_info(ifp->drvr->wiphy,
			   "g965n_p2p_setup stage=%u ret=%d len=%u if=%u\n",
			   5U, ret, len, enabled);
}

'''

def observe_transform(data):
    text=data.decode()
    text=replace_once(text,'#include "bus.h"\n','#include "bus.h"\n#include "fweh.h"\n')
    text=replace_once(text,'static int brcmf_p2p_set_firmware(',OBSERVER+'static int brcmf_p2p_set_firmware(')
    text=replace_once(text,'\tbrcmf_g965n_p2p_step(ifp, 4, ret);\n',
        '\tbrcmf_g965n_p2p_step(ifp, 4, ret);\n'
        '\tif (checked && !ret)\n\t\tbrcmf_g965n_p2p_event_mask(ifp);\n')
    return text.encode()


CONTEXT=r'''/* Numeric firmware discovery context only, not an invented IF event. */
static void brcmf_g965n_p2p_context(struct brcmf_if *ifp)
{
	u32 bss = 0;
	int ret = brcmf_fil_iovar_int_get(ifp, "p2p_dev", &bss);

	if (net_ratelimit())
		wiphy_info(ifp->drvr->wiphy,
			   "g965n_p2p_context ret=%d bss=%u\n", ret, ret ? 0 : bss);
}

'''

def context_transform(data):
    text=replace_once(data.decode(),'static int brcmf_p2p_set_firmware(',CONTEXT+'static int brcmf_p2p_set_firmware(')
    start=text.index('static struct wireless_dev *brcmf_p2p_create_p2pdev(')
    end=text.index('static int brcmf_p2p_get_conn_idx(',start)
    body=replace_once(text[start:end],'\tif (!err) {\n\t\tbphy_err(drvr, "timeout occurred\\n");',
        '\tif (!err) {\n\t\tif (brcmf_g965n_checked_p2p(pri_ifp))\n\t\t\tbrcmf_g965n_p2p_context(pri_ifp);\n\t\tbphy_err(drvr, "timeout occurred\\n");')
    return (text[:start]+body+text[end:]).encode()

def transform(data):
    import re
    text=data.decode()
    text=replace_once(text,'#include <linux/slab.h>\n','#include <linux/slab.h>\n#include <linux/of.h>\n#include <brcm_hw_ids.h>\n')
    text=replace_once(text,'#include "core.h"\n','#include "core.h"\n#include "bus.h"\n')
    match=re.search(r'static int brcmf_p2p_set_firmware\([^{}]+\)\n\{.*?\n\}',text,re.S)
    if not match:raise ValueError('Missing pinned P2P setup function')
    text=text[:match.start()]+HELPERS+BODY+text[match.end():]
    text=replace_once(text,'\tbrcmf_p2p_set_firmware(pri_ifp, p2p->dev_addr);\n',
        '\terr = brcmf_p2p_set_firmware(pri_ifp, p2p->dev_addr);\n'
        '\tif (err < 0 && brcmf_g965n_checked_p2p(pri_ifp))\n\t\tgoto fail;\n')
    return context_transform(observe_transform(text.encode()))

def apply(root):
    p=Path(root)/REL;data=p.read_bytes();sha=hashlib.sha256(data).hexdigest()
    if sha in (PATCHED, 'feac7014ab29cce5bb63d38868a5437a75e6af54ccc1c9141e45ee5a89fb02fb'):return  # Reviewed later control-context transform.
    if sha==MASK_VERSION:new=context_transform(data)
    elif sha==PREVIOUS:new=context_transform(observe_transform(data))
    elif sha==ORIGINAL:new=transform(data)
    else:raise ValueError('Unreviewed P2P source; no change')
    if hashlib.sha256(new).hexdigest()!=PATCHED:raise ValueError('P2P transform identity differs')
    p.write_bytes(new)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kernel_source',type=Path)
    args=p.parse_args();apply(args.kernel_source)
