#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply bounded numeric Wi-Fi diagnostics to the exact reviewed Linux sources.

No device operations. Existing Broadcom ISC source notices remain unchanged.
"""
import argparse
import hashlib
from pathlib import Path

REL = Path('drivers/net/wireless/broadcom/brcm80211/brcmfmac')
ORIGINAL = {
    'fwil.c': '1ba05bb9a089f6da2e7cdc863473c6168e2443e5c97d9e4906a94bde8bb202a9',
    'fweh.c': '4a4c090a81e7c2a954834e98db41633f1cc5dd0a6b739edc5dbfc9b0bcd9f51c',
    'cfg80211.c': '1cb2c600fe401245cd218589d4bc3325f9ac0c0a15bd26ed1576c55eb3d85eb8',
}
FWIL_HELPER = r'''/* G965N bounded diagnostics: no command data or network identities. */
static bool brcmf_g965n_diag_cmd(u32 cmd, const void *data, u32 len, bool set)
{
	return set && (cmd == BRCMF_C_SET_ROAM_TRIGGER ||
		(cmd == BRCMF_C_SET_VAR && data && len >= sizeof("p2p_disc") &&
		 !memcmp(data, "p2p_disc", sizeof("p2p_disc"))));
}

'''
FWIL_LOG = r'''		if (brcmf_g965n_diag_cmd(cmd, data, len, set) && net_ratelimit())
			wiphy_err(drvr->wiphy, "g965n_fw cmd=%u ifidx=%u fwerr=%d\n",
				 cmd, (unsigned int)ifp->ifidx, fwerr);
'''
EVENT_HELPER = r'''/* G965N diagnostic reason: 0=eligible, 1=short, 2=outer index,
 * 3=NOIF, 4=interface index, 5=payload BSS index. No event state changes.
 */
static void
brcmf_g965n_diag_if(struct brcmf_pub *drvr,
		  const struct brcmf_fweh_queue_item *event)
{
	const struct brcmf_event_msg_be *msg = &event->emsg;
	unsigned int idx = 0, action = 0, flags = 0, bss = 0, role = 0;
	unsigned int reason = 0;
	bool p2pdev;

	if (event->code != BRCMF_E_IF || !drvr->fweh->p2pdev_setup_ongoing)
		return;
	/* Bound against the allocated queue data, never just firmware metadata. */
	if (event->datalen < sizeof(struct brcmf_if_event)) {
		reason = 1;
	} else {
		idx = event->data[0];
		action = event->data[1];
		flags = event->data[2];
		bss = event->data[3];
		role = event->data[4];
		p2pdev = (flags & BRCMF_E_IF_FLAG_NOIF) &&
			(role == BRCMF_E_IF_ROLE_P2P_CLIENT ||
			 role == BRCMF_E_IF_ROLE_STA);
		if (msg->bsscfgidx >= BRCMF_MAX_IFS)
			reason = 2;
		else if (!p2pdev && (flags & BRCMF_E_IF_FLAG_NOIF))
			reason = 3;
		else if (idx >= BRCMF_MAX_IFS)
			reason = 4;
		else if (bss >= BRCMF_MAX_IFS)
			reason = 5;
	}
	if (!net_ratelimit())
		return;
	wiphy_err(drvr->wiphy, "g965n_if version=%u status=%u reason=%u len=%u idx=%u action=%u flags=%u bss=%u role=%u disposition=%u\n",
		 (unsigned int)be16_to_cpu(msg->version), be32_to_cpu(msg->status),
		 be32_to_cpu(msg->reason), event->datalen, idx, action, flags,
		 bss, role, reason);
}

'''

# Two ordinary GET_VAR queries before roaming writes, once per driver lifetime.
# Stock 101_16 reads these iovars in dhd_preinit_ioctls; no policy is changed.
ROAM_HELPER = r'''/* G965N boot-policy observation only: kind 0=preinit, 1=WBTEXT.
 * Numeric metadata only; a failed query never makes its output value valid.
 */
static atomic_t brcmf_g965n_roam_diag_done = ATOMIC_INIT(0);

static void brcmf_g965n_roam_policy_diag(struct brcmf_if *ifp)
{
	struct brcmf_pub *drvr = ifp->drvr;
	u32 value;
	s32 ret;

	if (!of_machine_is_compatible("samsung,star2lte") ||
	    drvr->bus_if->chip != BRCM_CC_4361_CHIP_ID || ifp->ifidx != 0 ||
	    atomic_cmpxchg(&brcmf_g965n_roam_diag_done, 0, 1))
		return;

	value = 0;
	ret = brcmf_fil_iovar_int_get(ifp, "preinit_status", &value);
	if (ret)
		value = 0;
	wiphy_info(drvr->wiphy,
		   "g965n_roam_diag kind=0 ret=%d valid=%u value=%u\n",
		   ret, (unsigned int)!ret, value);
	value = 0;
	ret = brcmf_fil_iovar_int_get(ifp, "wnm_bsstrans_resp", &value);
	if (ret)
		value = 0;
	wiphy_info(drvr->wiphy,
		   "g965n_roam_diag kind=1 ret=%d valid=%u value=%u\n",
		   ret, (unsigned int)!ret, value);
}

'''


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('source anchor changed or duplicated')
    return text.replace(old, new, 1)


def transform(name, original):
    text = original.decode()
    if name == 'fwil.c':
        text = once(text, 'static s32\nbrcmf_fil_cmd_data(', FWIL_HELPER + 'static s32\nbrcmf_fil_cmd_data(')
        text = once(text, '\t} else if (fwerr < 0) {\n', '\t} else if (fwerr < 0) {\n' + FWIL_LOG)
    elif name == 'fweh.c':
        text = once(text, 'static void brcmf_fweh_event_worker(', EVENT_HELPER + 'static void brcmf_fweh_event_worker(')
        anchor = '\t\tenum brcmf_fweh_event_code code;\n\n'
        text = once(text, anchor, anchor + '\t\tbrcmf_g965n_diag_if(drvr, event);\n' +
                    '\t\t/* G965N IF input bound: reject before every payload reader. */\n' +
                    '\t\tif (event->code == BRCMF_E_IF &&\n' +
                    '\t\t    event->datalen < sizeof(struct brcmf_if_event))\n' +
                    '\t\t\tgoto event_free;\n')
    elif name == 'cfg80211.c':
        text = once(text, '#include <linux/kernel.h>\n',
                    '#include <linux/kernel.h>\n#include <linux/atomic.h>\n#include <linux/of.h>\n')
        text = once(text, 'static s32 brcmf_dongle_roam(struct brcmf_if *ifp)\n',
                    ROAM_HELPER + 'static s32 brcmf_dongle_roam(struct brcmf_if *ifp)\n')
        text = once(text, '\t/* Configure beacon timeout value based upon roaming setting */\n',
                    '\tbrcmf_g965n_roam_policy_diag(ifp);\n\n' +
                    '\t/* Configure beacon timeout value based upon roaming setting */\n')
    else:
        raise ValueError('unknown source')
    return text.encode()


# Exact patched identities: generated from the reviewed originals and helper.
PATCHED = {
    'fwil.c': '8ce50eaa039f157a47604c81b1629a349223e6ab379816ec4cfb5e5d10afa2b7',
    'fweh.c': 'e58ecc096234b07296d8f6affb72b56bed9e91fe2a62519e081f7a5d161fdb61',
    'cfg80211.c': 'fc3d4d3ccb275149308e7a78243ab7df098ce2ae9994ea3f70a06b646784b2a3',
}


def apply(root):
    pending = []
    for name, expected in ORIGINAL.items():
        path = root / REL / name
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest == PATCHED[name]:
            continue
        if digest != expected:
            raise ValueError(f'{name}: unreviewed source digest; refusing changes')
        result = transform(name, content)
        if hashlib.sha256(result).hexdigest() != PATCHED[name]:
            raise ValueError(f'{name}: diagnostic helper drift; refusing changes')
        pending.append((path, result))
    # Validate both inputs before modifying either source.
    for path, result in pending:
        path.write_bytes(result)
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel_source', type=Path)
    args = parser.parse_args()
    print(f'G965N Wi-Fi diagnostic sources changed: {apply(args.kernel_source)}')


if __name__ == '__main__':
    main()
