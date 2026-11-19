# Wi-Fi roaming policy compatibility

The observed firmware result for command55 is `-3`, **BCME_BADOPTION**;
`BCME_UNSUPPORTED` is `-23`. Linux's ordinary `-EBADE` result does not retain
that distinction. Command55 is `WLC_SET_ROAM_TRIGGER`. It must not be treated
as an unsupported command merely because the firmware rejects its current
policy combination.

## Actual boot evidence and narrow correction

Kernel24 boot records established both a successful `wnm_bsstrans_resp` read
with value5 and command55's raw BADOPTION result. Its `preinit_status` read
returned Linux `-52`, with `valid=0 value=0`: this is not evidence that the
preinitialization query is unsupported.

The Samsung/Lineage reference blocks legacy trigger changes when product
WBTEXT policy5 is active, directing callers to the firmware roaming profile.
The correction therefore applies only to board `samsung,star2lte`, BCM4361
chip ID `0x4361`, primary interface0, and a **fresh successful** policy read
returning5. In that case it preserves the product profile by not sending
legacy command55. It does not disable WBTEXT or write any replacement policy.

The policy is read again on every qualified roaming setup. No decision is
cached across calls. A failed read, any other policy, or another board/chip/
interface retains the original trigger write and its existing error reporting.
The condition does not depend on `preinit_status` success. Beacon timeout,
roam-off, roam delta, their write ordering and payloads, and the original
function's returned errors remain unchanged. This is a source correction
pending a new actual device boot; it does not establish roaming performance.

## Bounded numeric observations

`scripts/build/g965n-wifi-diagnostics.py` places policy reads before this
function's existing initialization writes:

| Numeric kind | Read-only iovar | Meaning established by source |
| --- | --- | --- |
| 0 | `preinit_status` | Stock driver uses query success to select optimized firmware preinitialization |
| 1 | `wnm_bsstrans_resp` | Stock enum value5 is `WL_BSSTRANS_POLICY_PRODUCT_WBTEXT` |

An atomic one-shot limits diagnostic logs and the preinitialization query to
the first qualified setup per driver lifetime, normally during boot network
setup. That first setup performs two GETs. Subsequent qualified setups perform
one fresh policy GET and no further diagnostic records. A module reload starts
a new driver lifetime. There is no periodic polling, retry, scanning or
interface cycling. Other boards, chips and interfaces perform no new query
and cannot consume the diagnostic one-shot.

The two records contain numeric `kind`, query `ret`, `valid`, and `value` only.
`valid=1` requires return0. On failure, `valid=0 value=0` explicitly discards any
partial or stale output. Query returns use the ordinary Linux API and may be
generic error mappings; do not infer an exact firmware error from them. Existing
raw command55 and P2P diagnostics remain separate. No addresses, network
identities, command payloads, credentials or packet contents are recorded.
The shared `fwil_fwerr` flag is never changed.

## Source basis and reproducibility

The pinned mainline `cfg80211.c` previously sent a legacy trigger unconditionally.
Samsung/Lineage reference commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`, under
`drivers/net/wireless/bcmdhd_101_16/`, supplies the comparison:

- `wl_android.c:wl_android_set_roam_trigger()` blocks legacy trigger writes
  under product WBTEXT policy and refers callers to roaming profiles.
- `include/wlioctl.h` defines product WBTEXT policy5;
  `include/bcmutils.h` defines BADOPTION `-3` and unsupported `-23`.
- `dhd_linux.c:dhd_preinit_ioctls()` queries `preinit_status`; query success
  selects optimized initialization and explicit unsupported selects its legacy
  branch. This comparison does not reinterpret the observed Linux `-52`.
- `dhd_linux.c` queries `wnm_bsstrans_resp` to recognize product WBTEXT.

The adaptation is new port code. Original Broadcom ISC notices in the modified
kernel files remain unchanged; patch script and tests retain GPL-2.0-only
notices.

The patcher checks exact pristine and resulting SHA256 identities for all
three affected C files before modifying any file. It also accepts the exact
reviewed kernel24 observer form: that known hash must reverse to the exact
pristine source before applying this correction. Unknown drift fails closed.
Previously reviewed `fwil.c` and `fweh.c` diagnostics remain byte-identical;
reapplying makes no change.

Host tests compile the actual helper and original/patched roaming functions
with AddressSanitizer/UndefinedBehaviorSanitizer. They check other-board/chip/
interface isolation, policy success/failure and non5 paths, unchanged existing
failure returns and ordered write bytes, initial diagnostic bounds, failed
output invalidation, and later policy changes5→0→5→failure. Only the qualifying
product-policy case removes command55; later reads must reverse that decision
when policy changes. Run tests with exact pristine sources available through
`WIFI_KERNEL_SOURCE`; private fixture copies are never committed.

A passing host test or build is not a successful device boot, restored roaming,
or proof of radio behavior. Actual boot observations and later corrections
belong in the changelog and validation matrix. No manual firmware commands or
separate feature tests are needed to collect ordinary boot records.
