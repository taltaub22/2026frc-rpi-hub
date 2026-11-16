#!/usr/bin/env bash
# Usage: sudo ./deploy/install.sh server|peer
set -euo pipefail
role="${1:?usage: install.sh server|peer}"
[ "$role" = server ] || [ "$role" = peer ] || { echo "role must be server or peer"; exit 1; }
here="$(cd "$(dirname "$0")/.." && pwd)"
apt-get install -y python3-gpiozero python3-lgpio
id fuelhub >/dev/null 2>&1 || useradd --system --groups gpio fuelhub
install -d /opt/fuelhub
install -m 0644 "$here/src/fuelhub.py" /opt/fuelhub/fuelhub.py
install -m 0644 "$here/deploy/fuelhub-$role.service" /etc/systemd/system/fuelhub.service
systemctl daemon-reload
systemctl enable --now fuelhub
systemctl --no-pager status fuelhub || true
