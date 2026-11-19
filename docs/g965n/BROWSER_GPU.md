# Visible Firefox WebGL validation

The normal diagnostic URL launcher once timed out on native43. A timeout alone
is not a GPU fault or a pixel pass. The controlled runner instead navigates an
actual visible Firefox window, verifies page visibility/focus and compares
120 frames/31,457,280 bytes. It rejects software renderer labels, incomplete
reports, context loss, hidden/unfocused pages and headless sessions. It audits
both temporary preference files and refuses forced WebGL/acceleration or an
explicitly disabled content sandbox. No personal profile is passed or changed.

Use a separately verified Mozilla geckodriver. The native test used Firefox
160.0.1 and [geckodriver0.37.1](https://github.com/mozilla/geckodriver/releases/tag/v0.37.1),
asset `geckodriver-v0.37.1-linux-aarch64.tar.gz`, SHA256
`8fd90b951422fbad5b56539fb344dff66eb3f986d615d8d6fde9f1f62dad610c`.
That MPL2 executable is not redistributed here. Mozilla documents its
[throwaway profiles](https://firefox-source-docs.mozilla.org/testing/geckodriver/Profiles.html)
and [capabilities](https://firefox-source-docs.mozilla.org/testing/geckodriver/Capabilities.html).

With the screen awake/unlocked and app overview closed, run as desktop user
ubuntu (not root), from a terminal inheriting the selected Mesa environment:

```sh
python3 /private/source/scripts/g965n/browser-webdriver-test.py \
  --model SM-G965N --consent-browser-trial \
  --geckodriver /private/verified/geckodriver \
  --output /private/new-browser-result.json
```

For SSH use, launch through the configured user manager or explicitly pass its
verified GPU whitelist; SSH does not automatically inherit the desktop's
private EGL/Gallium/GBM settings. The runner temporarily inhibits idle blanking
and requires a real local Wayland session. The owner-authorized remote trials
used normal login-session unlock/display-power APIs and restored their prior
state afterward; idle/lock preferences were not rewritten.

Control and page servers bind only loopback on ephemeral ports. The page uses
a fresh per-run route, and both control requests and Firefox bypass proxies.
Driver logs/results are private; session/profile/server processes are cleaned
up. Never commit their output, session tokens or profiles. The browser build
and normal sandbox remain in use; no headless or GPU-force option is supplied.

Native43 with accepted private Mesa, after a distinct normal reboot, passes
visible/focused120-frame tests with zero mismatches/context loss and no new
kernel GPU error. The returned `Mali-G51, or similar` is a generic reported family
label, not evidence that this handset has changed GPU model. The exact board
remains G965N/Mali-G72; the standalone native render suite is separate evidence.

Optional `--cadence` also measures120 animation callbacks while clearing a
small canvas and requires54fps minimum. One native run passed with70.5 callbacks/s,
median15ms/p95 21ms, visibility/focus retained. These browser timestamps are
not physical display scanout proof. A separate post-reboot fullscreen glmark
FIFO trial fell to11fps in all three scenes despite zero GPU faults; a later
single build scene returned60fps without policy changes. That intermittent
presentation problem remains unresolved. Do not call all animations smooth,
video decoding supported or browser/desktop endurance qualified from these tests.
