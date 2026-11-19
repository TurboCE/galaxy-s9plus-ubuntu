# Wi-Fi boot roaming-policy observations

The observed firmware result for command55 is `-3`, **BCME_BADOPTION**;
`BCME_UNSUPPORTED` is `-23`. Linux's ordinary `-EBADE` result does not retain
that distinction. Command55 is `WLC_SET_ROAM_TRIGGER`. This evidence does not
justify ignoring all failures or treating the command as unsupported.

`scripts/build/g965n-wifi-diagnostics.py` adds two ordinary GET_VAR observations
at the first qualified `brcmf_dongle_roam()` entry, before that function's
existing beacon-timeout, roam-off, trigger or delta writes:

| Numeric kind | Read-only iovar | Meaning established by source |
| --- | --- | --- |
| 0 | `preinit_status` | Stock driver uses query success to select optimized firmware preinitialization |
| 1 | `wnm_bsstrans_resp` | Stock enum value5 is `WL_BSSTRANS_POLICY_PRODUCT_WBTEXT` |

Both exact board compatibility `samsung,star2lte` and chip ID `0x4361`, plus
primary interface index0, are required. An atomic one-shot allows exactly two
queries per driver lifetime, normally during initial boot network setup. A
module reload creates a new driver lifetime; there is no periodic polling,
retry, scanning, interface cycling or persistent firmware change. Other
boards, chips and interfaces cannot consume the one-shot.

The two numeric records contain `kind`, query `ret`, `valid`, and `value` only.
`valid=1` requires return0. On failure, `valid=0 value=0` explicitly discards any
partial or stale firmware output. Query return values use the ordinary Linux
API and may be generic error mappings; do not infer an exact firmware error
or unsupported command from those query returns. Existing raw command55 and
P2P diagnostics remain separate. No addresses, network identities, command
payloads, credentials or packet contents are recorded by this observer.

This is **diagnostic code, not a roaming fix**. Even observing policy5 does
not skip command55 or modify WBTEXT, roaming profiles, returned errors, or the
order and bytes of existing writes. The shared `fwil_fwerr` flag is never
changed. Review actual boot records before proposing a policy-specific fix.
No separate feature test or manual firmware command is needed to read the
records emitted by ordinary initialization.

## Source basis and reproducibility

The pinned mainline `cfg80211.c` supplies a legacy trigger unconditionally.
Samsung/Lineage reference commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`, under
`drivers/net/wireless/bcmdhd_101_16/`, provides the comparison:

- `dhd_linux.c:dhd_preinit_ioctls()` queries `preinit_status`; only explicit
  unsupported uses its legacy branch, while query success uses optimized
  initialization.
- `dhd_linux.c` queries `wnm_bsstrans_resp` to recognize product WBTEXT.
- `wl_android.c:wl_android_set_roam_trigger()` blocks legacy trigger writes
  under that product policy and refers callers to roaming profiles.
- `include/wlioctl.h` defines product WBTEXT policy5;
  `include/bcmutils.h` defines BADOPTION `-3` and unsupported `-23`.

That comparison supports a hypothesis about conflicting roaming policies;
it does not establish the live firmware's policy or every firmware error
path. The observer is new port code; original Broadcom ISC notices in the
modified kernel files remain unchanged. The patch script/tests retain their
GPL-2.0-only notices.

The patcher checks exact pristine and resulting SHA256 identities for all
three affected C files before modifying any file. A cache containing the
already reviewed two-file diagnostics can add only the new policy observer;
reapplying makes no change. Unknown source drift stops without partial writes.
Host tests compile the actual patched observer and roaming function with
AddressSanitizer/UndefinedBehaviorSanitizer, compare the original and patched
write order/payload/returns across existing failure paths, and check scope,
one-shot behavior, two GETs, and failed-value invalidation. Run them with the
exact pristine sources available via `WIFI_KERNEL_SOURCE`; private fixture
copies are never committed.

A passing host test or build is not a successful device boot, a corrected
roaming policy, or proof of Wi-Fi roaming behavior. Actual boot observations
and any later fixes belong in the changelog and validation matrix.
