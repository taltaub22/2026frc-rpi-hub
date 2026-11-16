# Flashing the Pis: zero-touch

Goal: flash the SD card, put it in the Pi, power it. No keyboard, mouse, monitor, or SSH session.
On first boot the Pi sets its own hostname, static IP, SSH key and the fuelhub service (cloud-init,
built into Raspberry Pi OS Trixie / Imager 2.0+). No internet needed; the code travels on the card.

## You need
- A microSD card per Pi, a card reader, a laptop with Python 3 and Raspberry Pi Imager 2.0+
- An SSH public key (`~/.ssh/id_ed25519.pub`; create one with `ssh-keygen -t ed25519`)
- ❓ Pi model: the plain PoE HAT fits Pi 3B+/4; a Pi 5 needs the PoE+ HAT. Confirm what is in hand.

## Option A: one command (Imager CLI)
```
sudo ./provision/flash.sh server /dev/sdX      # red hub, 10.0.100.40, the "PLC"
sudo ./provision/flash.sh peer   /dev/sdY      # blue hub, 10.0.100.41
```
It generates the config, downloads Raspberry Pi OS Lite (64-bit), and flashes with the config baked in.
⚠️ The Imager CLI option names (`--cloudinit-userdata`, `--cloudinit-networkconfig`) come from community
reports, not the man page. The script checks `rpi-imager --help` and falls back to Option B if missing.

## Option B: Imager GUI + one command (works everywhere)
1. Raspberry Pi Imager: choose Raspberry Pi OS Lite (64-bit) for your Pi, no customisation needed. Write.
2. Re-insert the card so the `bootfs` partition mounts, then:
   ```
   ./provision/make_sd_config.py server --boot /Volumes/bootfs     # macOS
   ./provision/make_sd_config.py peer   --boot /media/$USER/bootfs # Linux
   python provision\\make_sd_config.py server --boot E:\\            # Windows
   ```
   This overwrites `user-data`, `network-config`, `meta-data` on the card. Eject.
   (Use `--out DIR` instead of `--boot` to just generate the files.)

## First boot
Insert the card, connect Ethernet (PoE switch port or a direct cable), power on. About 2 minutes later:
- hostname `fuelhub-red` / `fuelhub-blue`, static IP 10.0.100.40 / .41 (from `provision/roles/*.conf`)
- SSH on, key-only, user `pi` (`--user` to change), passwordless sudo
- persistent logs (journald, capped at 100 MB, so they survive a power cut), `fuelhub` service enabled and running
- full read/write root filesystem (no read-only overlay)

Check from a laptop on 10.0.100.0/24 (set your laptop to e.g. 10.0.100.99/24 for a direct cable):
```
./provision/verify.sh server        # ping, ssh, service, selfcheck, Modbus poll (fieldIoConnection 0x1F)
./provision/verify.sh peer
```
If the Pi is not reachable: the config only lives in the first-boot files, so re-flash. The first-boot log is
in `/var/log/cloud-init-output.log` on the card's root partition (or over SSH once it is up).

## After that
Code updates are over the network, no re-flashing: see `docs/ota.md`.

## Fallback: Pi already running
Any Pi that already has SSH can be set up with `./provision/deploy.sh server user@host`, which does the same
install over SSH (add `--no-network` to leave its IP alone).

## Known unknowns (nothing here has run on a real Pi yet)
- Ethernet interface name is assumed to be `eth0` (true on Pi OS); edit `network-config` if not.
- cloud-init `enable_ssh`, `users`, `write_files`, `runcmd` follow Raspberry Pi's documented format.
