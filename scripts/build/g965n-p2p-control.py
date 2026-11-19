# SPDX-License-Identifier: GPL-2.0-only
"""Opt-in firmware-backed BCM4361 discovery control context, no device access.

Protocol evidence: pinned LineageOS exynos9810 6a9461f, bcmdhd_101_16
wl_cfgp2p_init_discovery (p2p_dev BSS, primary control ifidx zero).
New injected C additions are dual licensed ISC OR GPL-2.0-only, preserving
the original Linux Broadcom ISC notices and the port's GPL-2.0-only use.
"""
import argparse
import hashlib
from pathlib import Path

BASE = Path('drivers/net/wireless/broadcom/brcm80211/brcmfmac')
P2P_OLD = 'adc908e9f1aac6bf2d6b6c53989f0e0f864aaf2d1e4d19a9286ddaf7eaa07b97'
P2P_NEW = 'feac7014ab29cce5bb63d38868a5437a75e6af54ccc1c9141e45ee5a89fb02fb'
CORE_OLD = '6be9e2f7ca8bab0b2e747c20d22efed99f1b0b93adb6c304257c2a12e073973e'
CORE_NEW = '8572556af759d417e2ab5d91f4b68eef4e512a38206d990fe09856cdde889e2e'

HELPER = r'''/* G965N firmware has a discovery BSS, not a separate data interface. */
static bool g965n_legacy_p2pdev;
module_param_named(g965n_legacy_p2pdev, g965n_legacy_p2pdev, bool, 0600);
MODULE_PARM_DESC(g965n_legacy_p2pdev, "opt-in star2/4361 firmware-backed discovery control context");

static bool brcmf_g965n_control_scope(struct brcmf_if *pri)
{
	return pri && brcmf_g965n_checked_p2p(pri) &&
	       pri->drvr->bus_if->proto_type == BRCMF_PROTO_MSGBUF &&
	       !pri->drvr->settings->p2p_enable && !pri->drvr->proto->del_if &&
	       pri->drvr->iflist[0] == pri && pri->drvr->if2bss[0] == 0;
}

static bool brcmf_g965n_is_control(struct brcmf_cfg80211_vif *vif)
{
	struct brcmf_if *ifp = vif->ifp;

	return ifp && !ifp->ndev && ifp->ifidx == 0 && ifp->bsscfgidx > 0 &&
	       ifp->bsscfgidx < BRCMF_MAX_IFS &&
	       brcmf_g965n_control_scope(ifp->drvr->iflist[0]);
}

static int brcmf_g965n_create_control(struct brcmf_if *pri,
		struct brcmf_cfg80211_vif *vif, u8 *address)
{
	struct brcmf_if *ifp;
	u32 bss = 0;
	int ret, cleanup;

	/* Never attach a primary data/flow lifecycle to this control-only BSS. */
	if (!brcmf_g965n_control_scope(pri))
		return -EOPNOTSUPP;
	ret = brcmf_fil_iovar_int_set(pri, "p2p_disc", 1);
	if (ret)
		return ret;
	ret = brcmf_fil_iovar_int_get(pri, "p2p_dev", &bss);
	if (ret)
		goto disable;
	if (!bss || bss >= BRCMF_MAX_IFS) {
		ret = -ERANGE;
		goto disable;
	}
	if (pri->drvr->iflist[bss]) {
		ret = -EEXIST;
		goto disable;
	}
	/* Existing non-netdev allocation does not change primary if2bss[0]. */
	ifp = brcmf_add_if(pri->drvr, bss, 0, true, "p2p-control", address);
	if (IS_ERR(ifp)) {
		ret = PTR_ERR(ifp);
		goto disable;
	}
	ifp->vif = vif;
	vif->ifp = ifp;
	wiphy_info(pri->drvr->wiphy, "g965n_p2p_control bss=%u ifidx=0\n", bss);
	return 0;
disable:
	cleanup = brcmf_fil_iovar_int_set(pri, "p2p_disc", 0);
	if (cleanup)
		wiphy_warn(pri->drvr->wiphy, "g965n_p2p_control cleanup=%d\n", cleanup);
	return ret;
}

'''


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Discovery control source anchor changed')
    return text.replace(old, new, 1)


def p2p_transform(data):
    s = data.decode()
    s = once(s, '#include "fweh.h"\n', '#include "fweh.h"\n#include "common.h"\n#include "proto.h"\n#include <linux/module.h>\n')
    marker = 'static struct wireless_dev *brcmf_p2p_create_p2pdev('
    s = once(s, marker, HELPER + marker)
    start = s.index(marker)
    end = s.index('static int brcmf_p2p_get_conn_idx(', start)
    body = s[start:end]
    body = once(body, '\tu32 bsscfgidx;\n', '\tu32 bsscfgidx;\n\tbool control = false;\n')
    body = once(body, '\tpri_ifp = p2p->bss_idx[P2PAPI_BSSCFG_PRIMARY].vif->ifp;\n',
        '\tpri_ifp = p2p->bss_idx[P2PAPI_BSSCFG_PRIMARY].vif->ifp;\n'
        '\tif (g965n_legacy_p2pdev && brcmf_g965n_checked_p2p(pri_ifp) &&\n'
        '\t    !brcmf_g965n_control_scope(pri_ifp)) {\n'
        '\t\terr = -EOPNOTSUPP;\n\t\tgoto fail;\n\t}\n')
    body = once(body, '\tbrcmf_cfg80211_arm_vif_event(p2p->cfg, p2p_vif);',
        '\tif (g965n_legacy_p2pdev && brcmf_g965n_checked_p2p(pri_ifp)) {\n'
        '\t\terr = brcmf_g965n_create_control(pri_ifp, p2p_vif, p2p->dev_addr);\n'
        '\t\tif (err)\n\t\t\tgoto fail;\n\t\tcontrol = true;\n'
        '\t\tgoto discovery_created;\n\t}\n\n'
        '\tbrcmf_cfg80211_arm_vif_event(p2p->cfg, p2p_vif);')
    body = once(body, '\t/* discovery interface created */', 'discovery_created:\n\t/* discovery interface created */')
    a = body.index('\t/* verify bsscfg index for P2P discovery */')
    b = body.index('\n\tINIT_WORK', a)
    check = body[a:b]
    body = body[:a] + '\tif (!control) {\n' + ''.join(('\t'+line if line else '')+'\n' for line in check.splitlines()) + '\t}\n' + body[b:]
    s = s[:start] + body + s[end:]
    marker = '\t\tbrcmf_p2p_cancel_remain_on_channel(vif->ifp);\n\t\tbrcmf_p2p_deinit_discovery(p2p);'
    start = s.index('int brcmf_p2p_del_vif(')
    end = s.index('void brcmf_p2p_ifp_removed(', start)
    deletion = once(s[start:end], marker,
        '\t\tbrcmf_p2p_cancel_remain_on_channel(vif->ifp);\n'
        '\t\tif (brcmf_g965n_is_control(vif)) {\n'
        '\t\t\terr = brcmf_p2p_set_discover_state(vif->ifp, WL_P2P_DISC_ST_SCAN, 0, 0);\n'
        '\t\t\tif (!err)\n\t\t\t\terr = brcmf_fil_iovar_int_set(cfg->pub->iflist[0], "p2p_disc", 0);\n'
        '\t\t\tif (!err) {\n'
        '\t\t\t\tclear_bit(BRCMF_P2P_STATUS_GO_NEG_PHASE, &p2p->status);\n'
        '\t\t\t\tbrcmf_remove_interface(vif->ifp, true);\n\t\t\t}\n'
        '\t\t\tbrcmf_cfg80211_arm_vif_event(cfg, NULL);\n\t\t\treturn err;\n\t\t}\n'
        '\t\tbrcmf_p2p_deinit_discovery(p2p);')
    return (s[:start]+deletion+s[end:]).encode()


def core_transform(data):
    return once(data.decode(), '\tifp = drvr->iflist[bsscfgidx];\n\t/*\n\t * Delete the existing interface',
        '\tifp = drvr->iflist[bsscfgidx];\n'
        '\t/* A duplicate IF_ADD must not dereference a control-only ndev. */\n'
        '\tif (ifp && !ifp->ndev)\n\t\treturn ERR_PTR(-EEXIST);\n'
        '\t/*\n\t * Delete the existing interface').encode()


def apply(root):
    pending = []
    for name, old, new, transform in [('p2p.c', P2P_OLD, P2P_NEW, p2p_transform),
                                     ('core.c', CORE_OLD, CORE_NEW, core_transform)]:
        path = Path(root)/BASE/name
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha == new:
            continue
        if sha != old:
            raise ValueError('Unreviewed '+name+'; no control-context change')
        result = transform(data)
        if hashlib.sha256(result).hexdigest() != new:
            raise ValueError('Control-context transform identity changed')
        pending.append((path, result))
    for path, data in pending:
        path.write_bytes(data)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kernel_source', type=Path)
    apply(p.parse_args().kernel_source)
