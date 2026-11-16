#!/usr/bin/env bash
# Runs on your LAPTOP (on the field network or a direct link to the Pi) after the Pi has its static IP.
# Usage: ./provision/verify.sh server|peer [ssh-user]
set -uo pipefail
role="${1:?server|peer}"; user="${2:-pi}"
root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1090
source "$root/provision/roles/$role.conf"
fail=0; ok() { echo "ok   $*"; }; bad() { echo "FAIL $*"; fail=1; }
ping -c1 -W2 "$IP" >/dev/null 2>&1 && ok "ping $IP" || bad "ping $IP"
ssh -o ConnectTimeout=5 "$user@$IP" 'systemctl is-active fuelhub && hostname' 2>/dev/null | tr '\n' ' ' | grep -q "^active $HOSTNAME_NEW" \
  && ok "service active, hostname $HOSTNAME_NEW" || bad "service/hostname over ssh"
if [[ "$SERVE" == 1 ]]; then
  python3 "$root/tools/modbus_probe.py" "$IP" --once && ok "Modbus poll on $IP:502" || bad "Modbus poll"
else
  echo "peer has no Modbus; check blue counts appear on the server Pi's registers (probe $PEER_IP while pulsing a blue sensor)"
fi
exit $fail
