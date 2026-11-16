#!/usr/bin/env bash
# Runs on your LAPTOP. Copies this repo to a freshly flashed Pi over SSH and installs it.
# Usage: ./provision/deploy.sh server|peer <user@host-or-ip> [--no-network]
set -euo pipefail
role="${1:?usage: deploy.sh server|peer user@host [--no-network]}"; target="${2:?user@host}"; shift 2
root="$(cd "$(dirname "$0")/.." && pwd)"
tar -C "$root" --exclude=.git --exclude=__pycache__ -czf - . \
  | ssh "$target" 'rm -rf /tmp/fuelhub-src && mkdir /tmp/fuelhub-src && tar -xzf - -C /tmp/fuelhub-src'
ssh -t "$target" "sudo /tmp/fuelhub-src/deploy/install.sh $role $*"
echo "Done. Reboot the Pi ('ssh $target sudo reboot'), then: ./provision/verify.sh $role"
