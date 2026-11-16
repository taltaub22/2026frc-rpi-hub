#!/usr/bin/env bash
# Runs ON the Pi, as root. Usage: sudo ./deploy/install.sh server|peer [--no-network]
# Fallback to the zero-touch cloud-init image (docs/flashing.md): same result, done over SSH on an already-running Pi.
# Installs fuelhub as a systemd service, sets hostname and static IP from provision/roles/<role>.conf.
# DRY_RUN=1 prints what would be done without changing anything.
set -euo pipefail
role="${1:-}"; shift || true
[[ "$role" == server || "$role" == peer ]] || { echo "usage: install.sh server|peer [--no-network]"; exit 1; }
NETWORK=1; [[ "${1:-}" == "--no-network" ]] && NETWORK=0
here="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1090
source "$here/provision/roles/$role.conf"

run() { if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "+ $*"; else "$@"; fi; }
write() { # write <path> <content>
  if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "--- $1"; printf '%s\n' "$2"; else printf '%s\n' "$2" > "$1"; fi
}

serve_flag=""; [[ "$SERVE" == 1 ]] && serve_flag="--serve "
unit="$(sed -e "s|@ROLE@|$ROLE|g" -e "s|@ALLIANCE@|$ALLIANCE|g" -e "s|@PEER_IP@|$PEER_IP|g" \
            -e "s|@SERVE_FLAG@|$serve_flag|g" "$here/deploy/fuelhub.service.in")"

# 1. Dependencies: Raspberry Pi OS Lite ships python3-gpiozero + lgpio; only install if missing.
python3 -c "import gpiozero" 2>/dev/null || run apt-get install -y python3-gpiozero python3-lgpio

# 2. User, role settings, updater, unit, first release (same layout the cloud-init image uses)
id fuelhub >/dev/null 2>&1 || run useradd --system --groups gpio --shell /usr/sbin/nologin fuelhub
run install -d /etc/fuelhub /var/lib/fuelhub
write /etc/fuelhub/role.env "$(sed 's/#.*//' "$here/provision/roles/$role.conf" | grep =; echo PORT=502)"
run install -m 0755 "$here/deploy/fuelhub-apply.sh" /usr/local/sbin/fuelhub-apply
write /etc/systemd/system/fuelhub.service "$unit"
ver="$(cat "$here/VERSION" 2>/dev/null || echo manual-$(date +%Y%m%d%H%M%S))"
if [[ "${DRY_RUN:-0}" != 1 ]]; then
  tmp="$(mktemp -d)"; cp "$here/src/fuelhub.py" "$tmp/"; echo "$ver" > "$tmp/VERSION"
  tar -C "$tmp" -czf /var/lib/fuelhub/seed.tar.gz fuelhub.py VERSION
  (cd /var/lib/fuelhub && sha256sum seed.tar.gz > seed.tar.gz.sha256); rm -rf "$tmp"
else
  echo "+ build /var/lib/fuelhub/seed.tar.gz ($ver)"
fi
run systemctl daemon-reload
run systemctl enable fuelhub
run /usr/local/sbin/fuelhub-apply /var/lib/fuelhub/seed.tar.gz --force

# 3. Hostname
run hostnamectl set-hostname "$HOSTNAME_NEW"

# 4. Static IP (NetworkManager, Raspberry Pi OS Bookworm or newer). Takes effect at next boot.
if [[ "$NETWORK" == 1 ]]; then
  if command -v nmcli >/dev/null; then
    con="$(nmcli -g NAME,TYPE connection show | awk -F: '$2 ~ /ethernet/ {print $1; exit}')"
    con="${con:-Wired connection 1}"
    run nmcli connection modify "$con" ipv4.method manual ipv4.addresses "$IP/$PREFIX" \
        ipv4.gateway "$GATEWAY" ipv4.dns "" ipv6.method disabled connection.autoconnect yes
  else
    echo "WARNING: nmcli not found; set $IP/$PREFIX gw $GATEWAY by hand" >&2
  fi
fi

echo "Installed $ROLE ($ALLIANCE hub). Reboot to apply the static IP $IP, then run provision/verify.sh."
