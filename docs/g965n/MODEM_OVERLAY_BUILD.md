# Reproduce the experimental modem package

The modem module requires `g965n/modem.dtbo`. The build now compiles this file
from `experiments/modem/g965n-modem-overlay.dts`; a private, manually generated
DTBO is not an input. The tracked source retains its GPL-2.0-only notice and
LineageOS revision-26 device-tree attribution. No extracted firmware, vendor
executables, stock BOOT or identity backups belong in Git or published artifacts.

## Build and compare the owner's stock hardware description

Prepare the documented builder and import the handset's own firmware first.
Use the **original Samsung BOOT**, not a subsequently installed Ubuntu BOOT,
for the optional stock comparison:

```bash
S9_EXPERIMENTAL_MODEM=1 \
S9_MODEM_STOCK_BOOT=/absolute/private/path/to/original-BOOT.img \
bash scripts/g965n/build.sh kernel
```

The host checks the private input's file type, Android BOOT header and size,
then mounts only that file read-only at `/run/g965n-stock-boot.img`. No cached
stock image is implicitly selected. These commands only build files.

Outputs include:

- `dist/experimental/modem/g965n-modem.ko`
- `dist/experimental/modem/modem.dtbo`
- `dist/experimental/manifest.json`, associated with the exact generated BOOT
- `dist/uniloader/boot-g965n-experimental-*.img`

The manifest preserves the existing `modules` entries and adds
`artifacts.modem_overlay`: artifact size/hash/path, requested firmware name,
tracked source hash, original source attribution and stock-comparison result.
FDT structure, the three required hardware nodes and revision 26 are checked
even without a stock input. Without `S9_MODEM_STOCK_BOOT`, the build still works
but records `stock_verification.status = "not-performed"`. That package has not
qualified its hardware properties for probing. A failed comparison aborts
packaging; `passed` means only those properties match, not that CP boot or LTE
works. Existing dtc layout warnings remain visible.

The comparison now also requires one narrow mainline interrupt migration:
stock NONE flags become explicit LEVEL_HIGH for only SPI69/74/440
(hardware IRQ101/106/472). Native read-only GICD configuration showed level
mode for those three lines. IDs and all remaining properties must still match.
The old NONE overlay triggers mainline irq-gic WARNs and is no longer accepted
by this verifier. This explicit migration is reported separately in each row;
it does not qualify CP boot, SIM detection or radio traffic.

For a separate comparison of an already built artifact:

```bash
python3 experiments/modem/verify-overlay.py \
  /absolute/private/path/to/original-BOOT.img \
  dist/experimental/modem/modem.dtbo --revision 26
```

To regenerate the receipt after this comparison, use the same kernel output,
BOOT image, source commit and complete feature list that produced the package:

```bash
python3 scripts/g965n/package-experiments.py \
  --kernel-out /build/src/mainline/out \
  --boot dist/uniloader/boot-g965n-experimental-TIMESTAMP.img \
  --output dist/experimental --source-commit SOURCE_COMMIT \
  --features audio bluetooth sensors modem \
  --stock-boot /absolute/private/path/to/original-BOOT.img
```

Run this inside the prepared build container when `/build` is a Docker volume.
Only list features actually built. The stock verifier reads the original image;
it never modifies or copies its contents into the package.

## Explicit installation and manual staging

Build success does not verify a device boot. After checking the exact SM-G965N
identity, preserving a verified nine-partition backup and explicitly choosing a
kernel update, use the existing guarded installer:

```bash
python3 scripts/g965n/install.py --serial DEVICE_SERIAL \
  --backup /absolute/private/path/to/verified-backup \
  --boot dist/uniloader/boot-g965n-experimental-TIMESTAMP.img \
  --update-kernel-experimental-g965n
```

This is a separate, explicit device-write command; the builder never invokes it.
Keep RECOVERY, EFS, CPEFS and RADIO intact. Confirm the actual Ubuntu boot before
staging modules. Copy the package and reviewed repository to the phone through
your authenticated connection. From that repository on the handset, the
following manual staging step checks actual model/kernel/BOOT, artifact hashes
and the successful stock comparison before creating any files. Stop modem
experiments first. It refuses existing targets, so preserve and review any old
staging instead of overwriting it.

```bash
sudo python3 - /absolute/path/to/experimental-package <<'PY'
import hashlib, importlib.util, json, sys
from pathlib import Path
pkg = Path(sys.argv[1]).resolve()
receipt = json.loads((pkg / 'manifest.json').read_text())
spec = importlib.util.spec_from_file_location('guard', 'scripts/g965n/deploy-drivers.py')
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
guard.verify_kernel(receipt)
if Path('/sys/module/g965n_modem').exists():
    raise SystemExit('Stop and review the loaded modem experiment first')
artifact = receipt['artifacts']['modem_overlay']
if artifact['stock_verification']['status'] != 'passed':
    raise SystemExit('Owner stock BOOT comparison is required before staging')
if artifact['path'] != 'modem/modem.dtbo':
    raise SystemExit('Unexpected overlay path')
module = receipt['modules']['modem']
if module['path'] != 'modem/g965n-modem.ko':
    raise SystemExit('Unexpected modem module path')
payloads = []
for item in (module, artifact):
    source = (pkg / item['path']).resolve()
    if not source.is_relative_to(pkg):
        raise SystemExit('Artifact is outside the package')
    data = source.read_bytes()
    if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise SystemExit('Artifact checksum mismatch')
    payloads.append(data)
stage = Path('/usr/lib/g965n-experiments') / receipt['boot_sha256'][:16] / 'modem'
firmware = Path('/lib/firmware/g965n/modem.dtbo')
if stage.exists() or stage.is_symlink() or firmware.exists() or firmware.is_symlink():
    raise SystemExit('Existing modem staging requires preservation and review')
stage.mkdir(parents=True, mode=0o755)
firmware.parent.mkdir(parents=True, exist_ok=True)
for target, data in ((stage / 'g965n-modem.ko', payloads[0]),
                     (stage / 'manifest.json', json.dumps(receipt, indent=2).encode()),
                     (firmware, payloads[1])):
    with target.open('xb') as stream:
        stream.write(data)
print('Files staged only; no module loaded, CP powered or daemon started.')
PY
```

Modem loading and CBD/RIL tests remain separate, explicit hardware experiments
under the exact module/BOOT and private-NV guards in `vendor-runtime.py`,
`run-cbd-test.py` and `run-ril-test.py`. Keep their private logs and NV working
copies off Git. A compiled or staged overlay must never be described as working
LTE, a successful cold boot, or permission to bypass a failed CP power sequence.
