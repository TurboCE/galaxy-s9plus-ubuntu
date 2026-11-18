# G965N Bluetooth bring-up

The explicitly GPL-2.0 board glue is pinned in SOURCES.json. The G965N stock
revision-26 tree confirms UART 0x10840000 / SPI422, PCAL6524@0x22 BT_EN bit7,
BT_WAKE gpg2-0, HOST_WAKE gpa2-3, and the expander reset retention pin gpg3-6.
This is a board comparison, not a working-controller claim.

Local changes: star2lte + enable_g965n=1 guard before MMIO; disallow diagnostic
test_skip modes; release clock/device resources on partial UART registration.
The kernel recipe enables the Samsung UART/Broadcom HCI stack and applies
board-scoped LE transmit-power and 3Mbaud quirks. No module is auto-loaded.
Both full module linking and kernel packaging passed on 2026-11-18.

Build with S9_EXPERIMENTAL_BLUETOOTH=1. Stage only your own BCM4361 HCD using
scripts/g965n/stage-native-firmware.sh and an explicit semco/murata choice.
An unverified vendor choice is a test candidate, not established hardware ID.
After a controlled module load, attach ttySAC0 with btattach, wait for firmware
setup before management queries, then test scanning, pairing and actual audio.
Do not unload/reload the Samsung UART in the same boot as a recovery shortcut.
The first G965N manual test registered hci0, loaded firmware and discovered 12
peers. CRYPTO_AES was unexpectedly modular; building/loading crypto/aes.ko fixed
the missing CMAC implementation and power cycling passed. Future recipes force
AES built in. Peer addresses remain private. Pairing/A2DP/reboot persistence
and suspend remain unqualified; discovery alone is not full Bluetooth support.

Reference investigation:
https://github.com/Zerone-Laboratories/ztOS/tree/8bfb09011757f06c68a055fbfd95ea07d5e4fbe1/bluetooth
