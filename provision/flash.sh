#!/usr/bin/env bash
# Runs on your LAPTOP. One command: download Raspberry Pi OS Lite and flash an SD card, with the fuelhub
# first-boot config baked in (needs the Raspberry Pi Imager CLI, v2.0 or newer: `rpi-imager --cli`).
#   sudo ./provision/flash.sh server /dev/sdX            (Linux; macOS: /dev/diskN, Windows: use the manual path)
# Options: --image FILE_OR_URL   (default: latest Raspberry Pi OS Lite 64-bit)   --ssh-key-file FILE
# If your Imager lacks the cloud-init options, the script stops and prints the manual path (docs/flashing.md).
set -euo pipefail
role="${1:?usage: flash.sh server|peer /dev/DEVICE [--image X] [--ssh-key-file F]}"; dev="${2:?device}"; shift 2
image="https://downloads.raspberrypi.com/raspios_lite_arm64_latest"; keyargs=()
while [[ $# -gt 0 ]]; do case "$1" in
  --image) image="$2"; shift;; --ssh-key-file) keyargs+=(--ssh-key-file "$2"); shift;; *) echo "unknown option $1"; exit 1;; esac; shift; done
root="$(cd "$(dirname "$0")/.." && pwd)"; out="$(mktemp -d)"; trap 'rm -rf "$out"' EXIT
command -v rpi-imager >/dev/null || { echo "rpi-imager not found. Install Raspberry Pi Imager 2.0+ (CLI), or use the manual path in docs/flashing.md"; exit 1; }
if ! rpi-imager --help 2>&1 | grep -q -- --cloudinit-userdata; then
  echo "This rpi-imager has no --cloudinit-userdata option. Use the manual path in docs/flashing.md:"
  echo "  flash with the Imager GUI (no customisation), then: ./provision/make_sd_config.py $role --boot <bootfs mount>"
  exit 1
fi
python3 "$root/provision/make_sd_config.py" "$role" --out "$out" "${keyargs[@]}"
read -r -p "Erase $dev and write the $role image? [type yes] " ok; [[ "$ok" == yes ]] || exit 1
rpi-imager --cli --cloudinit-userdata "$out/user-data" --cloudinit-networkconfig "$out/network-config" "$image" "$dev"
echo "Done. Put the card in the $role Pi, connect Ethernet (PoE or power). It configures itself on first boot (about 2 minutes)."
echo "Then: ./provision/verify.sh $role"
