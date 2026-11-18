# Timed per-user Mesa desktop trial

This is an explicit experimental deployment, not a build or installation step.
The isolated diagnostic Mesa passing a bounded test does not prove that GNOME,
browsers, video decoding or long-running desktop use work. Never activate this
helper from a build script. Keep logs, backup manifests and evidence private.

`scripts/g965n/mesa-session-trial.py` stages new files for **ubuntu UID 1000**
only. It does not replace system libraries, change the GDM greeter, write phone
partitions, install firmware or alter personal application preferences. It
restarts `gdm.service`, ending the current graphical session: save work first.
Do not directly restart `org.gnome.Shell@wayland.service`; this service may
refuse manual start/stop and its failure can log out the session. The inspected
Wayland unit starts `/usr/bin/gnome-shell` with no additional arguments; the
new drop-in preserves that command and leaves Type, stop actions, failure
policy and all other inherited unit settings unchanged.

## Preconditions and review

Use an existing coherent isolated Mesa build with its original `receipt.json`,
outputs and runtime links intact. Runtime links must resolve inside that build.
The helper verifies these hashes and emits a
new private vendor JSON and Shell wrapper that also pins the active JSON
hash, without modifying that build or its
old launcher. The wrapper clears forced driver selection, preloads and software
rendering flags, then selects private EGL, Gallium and GBM together, normal DRM
FD discovery, and `PAN_MESA_DEBUG=nocrc,noafbc`. Shader caching is enabled in a
separate trial cache, not globally disabled.

Before applying, independently verify the complete private nine-partition
backup on the host and copy only its manifest to the handset. Pin that
manifest's SHA256. The helper requires its model/completeness/metadata and
compares current EFS, CPEFS and RADIO labels, sizes and hashes; it does not
write or mount them. Any mismatch stops the trial. An older backup BOOT is
allowed: the **installed startup receipt and explicitly selected BOOT SHA256**
are separately checked against the actual running kernel and BOOT using
`deploy-drivers.py`. Do not revalidate unrelated modem runtime or start CP.

## Explicit trial

Run the reviewed helper and its sibling `deploy-drivers.py` on the handset as
root. Substitute private absolute paths and verified fingerprints:

```sh
sudo python3 /private/source/scripts/g965n/mesa-session-trial.py apply \
  --trial mesa-desktop-one \
  --build /home/ubuntu/private-isolated-mesa/patched \
  --model SM-G965N \
  --kernel-receipt /usr/lib/g965n-experiments/BOOT_PREFIX/manifest.json \
  --expected-boot-sha256 VERIFIED_CURRENT_BOOT_SHA256 \
  --backup-manifest /private/latest-nine-partition-manifest.json \
  --backup-manifest-sha256 VERIFIED_BACKUP_MANIFEST_SHA256 \
  --consent-restart-desktop-trial
```

Before any user profile/environment change, the helper saves the previous GPU
variable whitelist in a root-owned mode-0700 state directory and reserves an
independent **system** rollback timer for 300 seconds. It checks that the timer
is active, creates unique user environment.d/Shell drop-in/wrapper/vendor files,
updates only the user manager's GPU whitelist, and restarts GDM. Nonempty
pre-existing GPU overrides other than the known `PAN_MESA_DEBUG=nocrc` are
refused for review, rather than silently replaced. Existing file
or symlink conflicts are refused. Another pending or accepted trial must be
rolled back before applying a new trial. A global root reservation lock covers
the existing-state scan, new-state creation and timer reservation, so concurrent
commands with different trial names cannot stage competing profiles. The lock
is released before application or rollback calls.

The five-minute interval starts when the timer is reserved, before staging and
GDM restart. Do not assume five minutes remain after the login screen appears.
Keep independent SSH access available. No source check cancels this timer.

## Evidence and explicit acceptance

Before acceptance, reconnect through a **fresh SSH connection**, find the new
GNOME Shell process and inspect its actual `/proc/PID/maps`: private patched
EGL/Gallium/GBM must be loaded, not merely selected in environment variables.
Check the current BOOT/kernel and kernel-log boundary, failed units, session
health and display. Preserve the private map/log evidence. Interpret the
100-microsecond DECON latch-check rejection counter separately from 40ms IRQ
wait failures and actual display faults; do not conceal new observations.

A root reviewer must create a private evidence JSON attesting actual
post-restart checks, rather than copying these booleans after source review:

```json
{
  "trial": "mesa-desktop-one",
  "boot_sha256": "VERIFIED_CURRENT_BOOT_SHA256",
  "captured_at_unix": 0,
  "fresh_ssh": true,
  "shell_private_dso_maps": true,
  "kernel_health_reviewed": true
}
```

Replace `captured_at_unix` with the actual evidence capture time after staging.
The helper checks the trial/BOOT/time scope and booleans; these are explicit
operator attestations, not an automatic hardware validator. Accept only after
reviewing the actual private artifacts:

```sh
sudo python3 /private/source/scripts/g965n/mesa-session-trial.py accept \
  --state /var/lib/g965n-mesa-trial/mesa-desktop-one \
  --evidence /private/post-restart-evidence.json
```

Acceptance is the only action stopping this trial's timer. It is serialized
against rollback; acceptance refuses an already-running rollback or changed
owned files. It does not turn bounded rendering evidence into broad desktop
qualification.

## Rollback and limits

If not accepted, the system timer removes only newly owned files whose hashes
still match, restores the saved user-manager GPU whitelist, reloads the user
manager and restarts GDM. It runs independently of the graphical user session.
Generated shader cache and empty directories are retained. Unknown files and
modified owned files are preserved and reported for manual review; therefore
changed configuration can prevent a complete automatic return to stock. Never
force deletion or claim rollback succeeded in that case.

Explicit manual rollback remains available even after acceptance:

```sh
sudo python3 /private/source/scripts/g965n/mesa-session-trial.py rollback \
  --state /var/lib/g965n-mesa-trial/mesa-desktop-one
```

A reboot or system failure can remove a transient systemd timer; this trial
requires no reboot and does not promise recovery from those events. Review
other user/system environment generators for conflicting graphics variables
before approval. Systemd activation and GNOME environment import behavior,
Shell startup and rollback still require real device verification. The helper
does not update the legacy D-Bus activation environment: its API cannot fully
restore absent variables. Legacy D-Bus activated applications are not
automatically qualified and need actual per-process library-map checks. Record
every deployment, failure, restoration and hardware result in CHANGELOG and
the validation matrix; do not describe this source-only helper as deployed.
