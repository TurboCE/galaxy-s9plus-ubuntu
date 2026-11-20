# SM-G965N secondary GPT maintenance

`gpt-backup.py` is an opt-in device maintenance tool. Image builds never call it.
It does not resize/move partitions or change primary GPT entries, GUIDs,
bootloaders or filesystems. It only reconstructs an entirely empty secondary
partition array/header from a CRC-valid, non-overlapping primary GPT.
Nonempty secondary metadata is a refusal, even when it looks invalid.

The qualified device has 4096-byte logical sectors, 128 entries of 128 bytes,
25 occupied entries, and a Samsung 512-byte GPT header with a zero extension.
The earlier 512-byte **sector** assumption was incorrect; header and sector
sizes are different. The correction preserves header length 512 and its CRC.

## Reviewed workflow

1. Verify native SM-G965N, the current BOOT receipt and a complete nine-partition
   private backup. Keep RECOVERY/EFS/CPEFS/RADIO backups on the host.
2. Copy this source to the handset. Run a read-only snapshot into a new root-only
   directory, then copy the metadata backup to private host storage and verify
   the receipt hashes and independently regenerated candidate:

   ```sh
   sudo python3 gpt-backup.py --snapshot "$NEW_PRIVATE_AUDIT_DIR"
   ```

3. Only after model, backup and explicit maintenance consent checks, use a
   **different new directory** for the actual guarded maintenance:

   ```sh
   sudo python3 gpt-backup.py --snapshot "$NEW_PRIVATE_APPLY_DIR" \
     --backup-manifest "$PRIVATE_VERIFIED_BACKUP_MANIFEST" \
     --profile-root /var/lib/g965n-sensors/kernel48-rtc-irq \
     --apply-sm-g965n-secondary-only
   ```

The tool saves original primary/tail metadata and the candidate before writing,
checks that the disk metadata did not change during preparation, writes only
five reserved tail sectors (20KiB), flushes and verifies readback, and rechecks
six protected partitions. Existing snapshot directories are refused. It does
not perform an online partition rescan. A partial/failed write requires review
using the private snapshot; do not run a generic partition-repair command.

4. Reboot normally. Confirm the alternate-GPT warning is absent, original
   primary metadata is byte-identical, both header/array CRCs are valid and
   every partition entry matches. Check BOOT, protected partitions and driver
   services again. Retain private snapshots; never commit them.

Hardware verification on 2026-11-20 passed those checks and Wi-Fi/driver startup.
This repairs one handset's missing backup metadata; it is not evidence of a
universal problem with every S9+ installation or long-term storage health.
