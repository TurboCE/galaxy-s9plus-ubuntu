# G965N built-in initramfs contract

The Ubuntu/probe entry point is built into the kernel with
`CONFIG_INITRAMFS_SOURCE`. uniLoader also passes an intentionally empty gzip
stream through `linux,initrd-start/end`. This external stream is a compatibility
placeholder, not a second initramfs archive.

The existing wrapper BOOT has a valid 20-byte gzip stream that decompresses to
zero bytes. `scripts/build/build_uniloader.sh` generates the embedded loader
placeholder with `printf '' | gzip -n`; `pack_uniloader.sh` generates an empty
gzip for the Android envelope as well. Those commands, the loader, memory
layout, addresses and payload remain unchanged. In particular, do not replace
the loader placeholder with a real empty CPIO archive: the existing build script
records a previous pre-console boot failure from that change.

In the pinned Linux source, `init/initramfs.c:unpack_to_rootfs` starts its CPIO
parser in `Start`. A zero-byte decompressed stream never delivers a CPIO trailer
and never transitions to `Reset`, so the external unpacker reports “junk at the
end of compressed archive”. This is distinct from corrupt data in the built-in
archive: a built-in extraction failure remains fatal before the external-image
branch.

The build now explicitly selects `CONFIG_INITRAMFS_FORCE=y`, using Linux's
existing option to ignore the bootloader-supplied initramfs. Its dependency is
satisfied by the port's existing `CONFIG_CMDLINE_FORCE=y`. This expresses the
existing built-in-only design without changing the dummy bytes or suppressing
kernel errors. The kernel still extracts and checks its internal archive first;
only the unused external placeholder is excluded.

After the final `olddefconfig`, before any Image build, a contract check requires:

- `BLK_DEV_INITRD=y`, `INITRAMFS_FORCE=y` and `CMDLINE_FORCE=y`;
- `INITRAMFS_SOURCE` exactly equal to the staged port initramfs directory;
- a nonempty executable ordinary `/init` matching the selected tracked entry,
  either `device/mainline-init-boot` for `INIT=boot` or `device/mainline-init`
  for the default probe. The same existing CR normalization is accepted.

A missing flag, changed source directory, symlink, wrong entry or empty init
stops the build. This prevents an override from silently discarding an external
initramfs while leaving no intended internal entry point.

## Verification and limits

`python3 tests/test_initramfs_contract.py` executes the actual embedded build
check against valid boot/probe fixtures and rejected flags/entries. If the
existing private wrapper BOOT is available (or supplied through
`G965N_WRAPPER_BOOT`), it verifies that its external gzip is still 20 bytes,
decompresses to zero bytes and is unchanged by the check. No BOOT, native config
or raw log is committed.

A separate host check copied native #21's config into an isolated temporary
output directory and ran the real Linux `olddefconfig` with FORCE enabled. The
final config retained FORCE=y, CMDLINE_FORCE=y and the nonempty intended source;
the staged boot init matched the tracked boot entry. The original #21 build
volume was mounted read-only and its config hash stayed unchanged. No Image,
module or firmware was built and no device was changed for that check.

A later hardware boot is still required to verify that the external-image
warning disappears and Ubuntu/USB/display/drivers retain their behavior. A
successful configuration check is not a successful boot. This change does not
qualify CLKOUT, modem, GPU stability, suspend or any unrelated peripheral.
