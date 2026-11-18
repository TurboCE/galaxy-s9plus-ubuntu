# G965N first-boot hardware comparison

Observed on 2026-11-18 from the handset's own stock BOOT backup, TWRP runtime
device tree and /proc/iomem. Full binary dumps and command lines stay private.

| Item | G965N observation | Existing mainline/uniLoader assumption |
|---|---|---|
| Samsung DTBH chip | 0x2652 | Same |
| Board selection | rev26, entry range 26–255 | Same range |
| Touch I2C | 0x104b0000, device address 0x48 | Same addresses |
| Boot framebuffer | 0xcc000000 | Same base; 1440x2960 mode |
| Firmware debug reservation end | 0x9179c000 | Loader payload 0x92000000 clears it |
| RAM low banks | 0x80000000–0xbc7fffff with reserved hole; 0xc0000000–0xdfffffff; 0xe1900000–0xffffffff | Corresponding banks and reserved regions |
| RAM high banks | 0x880000000–0x97fffffff | Two consecutive 2GiB banks |
| Partition nodes | BOOT sda10, USERDATA sda25, RECOVERY sda11 | Same nodes; capacity checked on device |
| Wi-Fi firmware/NVRAM | Differs from upstream G965F inputs | Own G965N inputs used for experimental rebuild |

The structural checks support a controlled first-boot attempt. They do not certify
power sequencing, GPU/display operation, cellular radio, audio or stability.
Samsung stock touch compatible is sec,sec_ts; the mainline driver uses samsung,s6sy761.
Matching addresses alone is not proof that the entire touch protocol works.

Reproduce the stock boot-table inspection without a device write:

```bash
python3 scripts/g965n/inspect-stock-boot.py .local/backup/BOOT.img
```

The Samsung firmware/runtime debug reservations are why this port's uniLoader payload
address must be retained rather than using the smaller S9/starlte placement.
