# Local device firmware — not redistributed

Samsung/Broadcom firmware and NVRAM are omitted from this source-only repository and Git history.
Use `python3 scripts/g965n/extract-firmware.py --serial SERIAL` with your own G965N in TWRP.
It mounts VENDOR read-only without journal replay, extracts and verifies three Wi-Fi inputs:

- bcmdhd_sta.bin_b2 → brcm/brcmfmac4361-pcie.bin
- nvram.txt_r02a_b2 → brcm/brcmfmac4361-pcie.txt
- bcmdhd_clm.blob → brcm/brcmfmac4361-pcie.clm_blob

Or use `python3 scripts/g965n/firmware.py DIRECTORY` with your own copies of those filenames.
Conflicting existing files are rejected. Stock bytes are preserved; the kernel builder normalizes
CRLF in its separate NVRAM build copy. Extraction success does not prove mainline Wi-Fi operation.
`build.sh prepare` obtains regulatory.db and regulatory.db.p7s locally from Ubuntu's wireless-regdb.
Bluetooth is disabled in this baseline, so no Bluetooth patchram is required.

All extracted files and device/base/lib/firmware/ are ignored. Never force-add them or publish images
containing them without reviewing redistribution permissions.
