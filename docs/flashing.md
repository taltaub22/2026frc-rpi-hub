# Flashing and provisioning the two Pis

Two Pis, one flow. Do server (red, 10.0.100.40) and peer (blue, 10.0.100.41) the same way.
Everything needed is in this repo; the Pi does NOT need internet (Raspberry Pi OS Lite already
includes python3-gpiozero and lgpio).

## You need
- microSD card per Pi (16 GB or more, A1/A2 rated), card reader, a laptop with Raspberry Pi Imager
- The Pi, its PoE HAT (or a USB-C supply for desk work), Ethernet cable
- Your SSH public key (`~/.ssh/id_ed25519.pub`; create with `ssh-keygen -t ed25519` if you have none)
- ❓ Pi model: a PoE HAT (not PoE+) fits Pi 3B+/4; a Pi 5 needs the newer PoE+ HAT. Check what is in hand.

## 1. Flash the OS
1. Raspberry Pi Imager: choose your Pi model, then **Raspberry Pi OS Lite (64-bit)**.
2. Edit settings (Ctrl+Shift+X or "Edit settings"):
   - Hostname: `fuelhub-red` (server) or `fuelhub-blue` (peer)
   - Username `pi` (or your own; `verify.sh` takes the username as 2nd argument), and a password
   - Services: enable SSH, **public-key only**, paste your public key
   - Wi-Fi: leave empty. Locale/timezone: Asia/Jerusalem
3. Write. Label the SD card and the Pi "RED / server" or "BLUE / peer".

## 2. First boot and deploy (laptop on the same network)
1. Plug the Pi into your laptop's network (a switch with DHCP, or a direct cable; direct needs
   link-local, `ssh user@fuelhub-red.local` usually works). Wait about 90 s.
2. From this repo:
   ```
   ./provision/deploy.sh server user@fuelhub-red.local     # or: peer user@fuelhub-blue.local
   ```
   This copies the repo, installs `/opt/fuelhub/fuelhub.py`, creates the `fuelhub` user, renders
   the systemd unit from `provision/roles/<role>.conf`, sets hostname, and sets the static IP
   (NetworkManager). Add `--no-network` to skip the IP change (for bench work).
3. `ssh user@fuelhub-red.local sudo reboot`. The Pi now has its static IP (10.0.100.40 / .41).

## 3. Verify (laptop on 10.0.100.0/24)
```
./provision/verify.sh server user
./provision/verify.sh peer user
```
Checks ping, service active, hostname, and a Modbus poll (28 DI, 11 HR; fieldIoConnection 0x1F).
Then wire sensors and bench-test (docs/wiring.md, README validation plan).

## 4. Lock the root filesystem (last step)
```
scp provision/lock-root.sh user@10.0.100.40:/tmp/ && ssh -t user@10.0.100.40 sudo /tmp/lock-root.sh
```
This enables the overlay filesystem and read-only /boot so a power cut cannot corrupt the card.
To change anything later, run it with `--unlock`, update, then lock again.
⚠️ With the overlay on, files written at runtime are lost at reboot. Per-pulse audit CSVs (not built
yet) will need a separate writable location.

## Updating the code on a Pi
`--unlock` (if locked) -> `./provision/deploy.sh <role> user@IP --no-network` -> verify -> lock.

## Cloning a card instead
After step 3 works on one Pi you can image the SD card, but you must then change the hostname and
static IP (re-run deploy.sh for the other role). Flashing fresh from Imager is just as fast.

## Peer link check
The peer sends UDP (port 5021) to 10.0.100.40 about 10x/s. On the server Pi,
`sudo journalctl -u fuelhub -f` shows resets; blue totals appear in holding register 2 via
`tools/modbus_probe.py 10.0.100.40`.
