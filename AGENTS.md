# SM-G965N port maintenance

Record every device change, failure, fix, and verification in docs/g965n/CHANGELOG.md.
Keep the validation matrix current. A successful build is not a successful device boot.
Never label G965N installation, LTE, audio, or suspend working without hardware evidence.
Never commit private logs, identifiers, backups, credentials or extracted firmware.
Keep upstream attribution, original source notices and GPL-2.0-only terms.
Build scripts must never flash. Device writes require explicit model, backup and consent checks.
Preserve RECOVERY, EFS, CPEFS and RADIO during Ubuntu installation.
Do not update or relock Samsung bootloaders as a workaround.
Do not enable firmware/image publishing in CI without reviewing redistribution rights.

For continuation, read docs/g965n/STATUS.md and docs/g965n/HANDOFF.md first.
Keep those latest-state summaries current alongside CHANGELOG.md and VALIDATION.md.
Historical failures in the validation timeline may be superseded by later hardware evidence.
The current user-authorized scope excludes camera/fingerprint and uses Wi-Fi for GPS tests.
