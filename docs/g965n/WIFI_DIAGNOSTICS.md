# G965N bounded Wi-Fi diagnostics (source candidate)

This candidate has host C tests, not a device boot or a successful Wi-Fi
Direct test. It does not establish the cause of the observed P2P timeout.
Ordinary Wi-Fi association and P2P-device creation are separate validations.

`scripts/build/g965n-wifi-diagnostics.py KERNEL_SOURCE` modifies only two
reviewed brcmfmac source files. The tracked kernel patch script invokes it;
the helper does not build, install, flash or run any device command. It verifies both
inputs before changing either, accepts only the exact original or exact patched
SHA-256 identities, and rejects unknown drift. Reapplying it is a no-op.

The reviewed Linux source checkout is `8cd9520d35a6c38db6567e97dd93b1f11f185dc6`.
Upstream paths are under
`drivers/net/wireless/broadcom/brcm80211/brcmfmac/`:

| Source | Original SHA-256 |
| --- | --- |
| `fwil.c` | `1ba05bb9a089f6da2e7cdc863473c6168e2443e5c97d9e4906a94bde8bb202a9` |
| `fweh.c` | `4a4c090a81e7c2a954834e98db41633f1cc5dd0a6b739edc5dbfc9b0bcd9f51c` |

The original Broadcom copyrights and ISC SPDX notices remain in place. The
injected C is an adaptation of these ISC-licensed source paths; the repository's
Python helper and tests retain GPL-2.0-only notices. No firmware is included.

## Diagnostic scope

The existing firmware-command wrapper collapses a negative firmware status to
`-EBADE` except when its existing raw-status option is selected. The new diagnostic
prints the raw negative status only after a successful transport for SET command
55 (roam trigger), or SET_VAR command 263 whose bounded name is exactly the
NUL-terminated `p2p_disc`. GET commands, similarly prefixed names and other iovars
are excluded. Existing calls, arguments, error codes and raw-status behavior do
not change.

The IF-event diagnostic runs only for event 54 during an existing P2P-device
setup window. It uses the allocated queue's actual data length before examining
its five-byte IF record, and prints only numeric event version, status, reason,
length, interface index, action, flags, BSS index, role and disposition. Both new
messages explicitly check `net_ratelimit()` before `wiphy_err`, independently
of BRCMDBG or tracing configuration; no bytes, addresses, names,
SSID, MAC or credentials are printed. Interface indexes are transient protocol
indexes, not persistent device identities.

| Disposition | Meaning |
| --- | --- |
| 0 | Meets the existing initial IF dispatch conditions; not proof of handler completion |
| 1 | Actual queued IF data shorter than five bytes; fields are not read |
| 2 | Outer BSS index outside the existing accepted range |
| 3 | Existing NOIF rule would ignore the event |
| 4 | IF payload interface index outside the existing accepted range |
| 5 | IF payload BSS index outside the existing accepted range |

The existing queue admission validates its firmware data length against packet
length and the maximum command length, allocates exactly that much trailing
storage, and stores it in `event->datalen`. This is the length used by the new
reader, not an unverified message header alone. No new event-state transition,
retry, timeout, synthetic event or P2P-disable workaround is introduced.

## Separate IF input-validation fix

The existing IF handler dereferences the five-byte IF record without a minimum
length check. A separately marked guard in the event worker sends IF records
shorter than `sizeof(struct brcmf_if_event)` directly to its existing
`event_free` cleanup label before any existing payload reader. Diagnostic fields
are also bounded independently. Five-byte and longer records retain their
original ordering and dispatch. This fixes a source-level short-input read;
there is no hardware evidence that a short event caused the observed timeout.

## Source evidence and next bounded device test

The owner's pinned Lineage checkout
`6a9461f9460ca51d1217e5069a5d5556fcc79e63` selects
`drivers/net/wireless/bcmdhd_101_16/` for `CONFIG_BCM4361=y`.
Its `wl_cfgp2p_init_discovery` sets `p2p_disc=1`, reads `p2p_dev` for a BSS index,
and registers discovery netinfo with interface index zero. It does not wait for
IF_ADD there. Its `bcmevent.h` IF payload is the same five-byte layout as mainline;
this provides no evidence for an offset/version rewrite. Mainline instead waits
for IF_ADD. Whether the actual firmware sends no event, or mainline discards an
event, remains unverified. Do not synthesize completion or ignore a timeout.

A future device test requires separate approval and an idle GPU test window:

1. Verify the intended model/kernel/module configuration and USB SSH fallback.
   Record current STA state privately without changing connection profiles.
2. Confirm no P2P device or concurrent P2P operation exists. Attempt one
   test-owned P2P-device creation with a short external deadline. Do not scan,
   form a group, connect a peer, restart NetworkManager, reload modules, replace
   firmware or change STA settings.
3. Remove only an interface whose creation by this test was confirmed. Keep USB
   control available; collect only the bounded diagnostic messages privately.
4. Recheck STA state and resource cleanup. An IF creation result is not proof of
   peer discovery, P2P group formation or traffic.

Broad FIL/EVENT debug is intentionally unnecessary: those existing paths also
contain payload and MAC-address output. The reviewed kernel has BRCMDBG,
dynamic debug and ftrace disabled, so those facilities cannot currently expose
the missing status at runtime.

## Host verification

Run with `WIFI_KERNEL_SOURCE=/path/to/pristine/kernel`:

```sh
python3 tests/test_wifi_diagnostics.py
```

The test also accepts a private fixture directory containing just the two exact
original files. It compiles the actual patched firmware-command function,
diagnostic helpers and event worker with AddressSanitizer and
UndefinedBehaviorSanitizer. Cases cover command-name bounds/NUL/allowlisting,
unchanged transport and raw firmware error returns, diagnostic suppression even with debug-style error output enabled,
all disposition values, absent private string output, short IF lengths zero
through four with no handler access and exactly one free, and valid five-byte
IF dispatch. Separate tests cover exact hashes, preserved source notices,
idempotence and refusing a second-file drift before modifying the first.

## Native follow-up: required setup and event-mask readback

2026-11-19 native31/32: scoped required setup stages DOWN/APSTA/UP/discovery-off/
address override all returned0. Native32 read-only event_msgs query returned0,
length27, IF-event bit1 before discovery-on. IF_ADD still timed out. Checked
setup propagation and subscription readback diagnose the failure; neither is
reported as working peer discovery/group formation/traffic. No firmware event
was synthesized or subscription mask changed. Next compatibility work needs
an actual qualified firmware discovery BSS query and primary-ifidx0 lifecycle
review, following the pinned source evidence above.

## Explicit firmware-backed control context

Native33 reads real p2p_dev BSS2 after timeout. `g965n-p2p-control.py` implements
a separate explicitly enabled control-only context, matching pinned firmware
protocol rather than synthesizing a completion. `brcmfmac.g965n_legacy_p2pdev`
defaults off; root may select it only for a qualified board/BOOT trial. Required
gates exclude BCDC, legacy netdev allocation, protocol data-interface cleanup
and any damaged primary mapping. A real query/free bounded nonzero BSS is
required; failure unwinds discovery and returns the real error. No primary
mapping replacement. A non-netdev duplicate guard prevents a null dereference.

A separately explicit `S9_EXPERIMENTAL_P2P_CONTROL=1` adds the kernel command-line
selection for the qualified native36 boot path. Builds do not enable it by default,
flash, deploy or publish firmware. Context creation and delete tests alone are
not evidence of peer discovery, GO/client negotiation or actual peer traffic.

## Latest hardware qualification and reproduction

Native35 passed two guarded create/start/one-channel scan/stop/delete cycles
with primary mapping unchanged and bound-WiFi HTTPS204 after each. Native36,
built with `S9_EXPERIMENTAL_P2P_CONTROL=1`, automatically creates the firmware-
backed P2P control context across initial and warm boots without IF_ADD timeout.
Native NetworkManager Find discovered Fold7; the owner confirmed reverse
visibility by an address privately matched to the actual S9 P2P device.

Add `S9_EXPERIMENTAL_P2P_CONTROL=1` to the existing reviewed G965N kernel build
recipe (retain its other required flags and own-firmware inputs). It adds
`brcmfmac.g965n_legacy_p2pdev=1`. The general build default remains off; no
installer/CI automatically flashes or changes firmware. The model/backup/
consent-guarded BOOT-only installer remains separate.

Already-configured APSTA1 is reused without primary DOWN/APSTA/UP. A connecting
or connected primary with unconfigured APSTA refuses instead of being reset;
initial idle setup retains upstream commands. A real firmware BSS query and
free bounded slot are mandatory. Removal uses the existing non-netdev lifecycle
and preserves primary data mappings; no firmware event is synthesized.

`p2p-control-trial.py` requires an opt-in-off exact-BOOT baseline and arms a90s
reboot fallback before its runtime opt-in. It changes only its own test context,
uses a valid Listen Channel IE for scans, and preserves raw wireless details
in private0600 logs. `p2p-peer-observe.py` operates through stock NetworkManager
on an already qualified enabled path, uses signed-int32 Find timeout, and
prints only counts/generic name-match; it never pairs or connects a peer.

These results qualify initialization, bounded scanning/lifecycle and real
bidirectional peer discovery. GO/client negotiation, peer IP/file transfer,
long-term concurrent use and cross-firmware/hardware variants remain open.

### Native36 real Fold7 connection and payload trial

A unique peer match from native NetworkManager discovery was used for one
volatile wifi-p2p PBC profile, autoconnect disabled, IPv4 auto/never-default and
IPv6 disabled. The expected Android connection dialog was accepted. Activation
and a dedicated p2p-wlp1s0-0 IPv4 succeeded. A P2P-bound HTTP download to Fold7 and
a reverse source-bound TCP transfer each moved1048576 deterministic bytes with
matching SHA256. Receiver also checked source peer. No private address, profile,
credential, Android dump or vendor firmware is included here.

Primary bound-WiFi HTTPS204 passed during and after the group. Owned profile,
servers and cleanup timers were removed/stopped; native P2P device disconnected,
primary Wi-Fi/USB stayed connected. This is one real group/data qualification;
repeated pairing, opposite GO roles, persistence and endurance remain pending.
Two action-frame retry batches preceded acceptance, and a chanspec-52 query
error occurred. They remain genuine residual errors, alongside an SSP retry in
the full boot, rather than being hidden or relabeled as repaired.

### Native37 repeat and channel-state correction

Two Fold7 groups on native37 passed dedicated-interface, source-bound1MiB
transfers in both directions with exact hashes. Explicit active-group channel
queries succeeded; cleanup preserved STA HTTPS204 and produced zero chanspec
errors. The scoped inactive-P2P ENODATA guard retains original error behavior
for active groups/primary/other chips. One action-frame retry batch remains
in that full boot; the second group added none. A cached-peer attempt failed
peer-not-found, then fresh NetworkManager Find and connection succeeded.
Do not reuse a stale peer address or infer all wireless errors are fixed.
The later native38 initial+warm boots have clean error-priority baselines,
but that does not substitute for another peer/endurance test on native38.

### Native44 bounded NetworkManager discovery with concurrent Wi-Fi

On the boot with the gyro and proximity profile, ran three 8-second
discovery cycles through `p2p-peer-observe.py` and the stock
[NetworkManager Wi-Fi P2P API](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Device.WifiP2P.html).
USB SSH provided the management path. Standard Wi-Fi returned HTTPS204
during and after every cycle, with the same active station connection
and interface index. The control device returned to its disconnected
state and the kernel recorded no new Wi-Fi/P2P warning or error.
The scan saw one peer; its identity was not verified. Connection and
payload transfer on native44 still require a confirmed peer.

After deliberately disconnecting and manually restoring the saved Wi-Fi
profile to qualify the recovery guard change, repeated three 10-second
find/stop cycles. The restored station profile, interface index and
Wi-Fi HTTPS204 held during and after each cycle. No new Wi-Fi/P2P
warning or error was logged. The reported peer did not match the
previously verified Fold7 name or address.
