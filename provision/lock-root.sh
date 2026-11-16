#!/usr/bin/env bash
# Runs ON the Pi, as root. Makes the root filesystem read-only (overlayfs) so a power cut cannot corrupt the SD card.
# Do this LAST, after verify. Use --unlock to make changes later (reboots both times).
# Note: with the overlay on, anything written outside tmpfs is lost at reboot (including future audit CSVs).
set -euo pipefail
case "${1:-lock}" in
  lock)   raspi-config nonint enable_overlayfs; raspi-config nonint enable_bootro ;;
  --unlock) raspi-config nonint disable_bootro; raspi-config nonint disable_overlayfs ;;
  *) echo "usage: lock-root.sh [--unlock]"; exit 1 ;;
esac
echo "Rebooting to apply..."; reboot
