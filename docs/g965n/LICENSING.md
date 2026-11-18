# Source and redistribution

This repository distributes source, not ready-made phone firmware. Public availability of an
upstream file alone is not evidence of permission to redistribute it elsewhere.

| Component | Treatment |
|---|---|
| Port drivers/scripts/docs | Upstream declares GPL-2.0-only; original notices retained, original hashes recorded |
| New G965N automation/docs | GPL-2.0-only, TurboCE 2026; complete text in LICENSE |
| uniLoader | Original GPL-2.0 source and licence retained |
| Linux kernel | Downloaded from kernel.org at a fixed tag/commit with original notices |
| Samsung UFS calibration / Linux charger reference | Original source preserved; upstream GPL provenance recorded in THIRD-PARTY.md |
| Samsung/Broadcom firmware and NVRAM | Omitted from this repository AND its Git history; user extracts locally from own phone |
| regulatory database | Not tracked; prepared locally from Ubuntu wireless-regdb package |
| TWRP / samloader / platform-tools | Not redistributed; obtained from official sources under their own terms |
| Ubuntu packages / Firefox | Downloaded from official package repositories under package-specific licences |

NOTICE and THIRD-PARTY.md preserve attribution. LICENSE.upstream preserves the original abbreviated
notice; LICENSE contains full GPL-2.0-only text from the SPDX licence-list project:
https://github.com/spdx/license-list-data/blob/main/text/GPL-2.0-only.txt

No built kernel, Ubuntu image, proprietary blob or personal data is published here. Before any binary
release, review all included firmware/package terms, preserve notices and provide exact corresponding
GPL source, patches/configuration and build instructions for that release. Do not copy an unrelated
Broadcom licence onto Samsung-specific binaries without evidence that it applies.

CI rejects firmware and private paths in Git. This reduces accidental publication; it is not a legal
opinion or a guarantee of every upstream contributor's provenance. Binary releases remain disabled.

References:
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
