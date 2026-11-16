#!/usr/bin/env bash
# Runs on your LAPTOP. Pushes the current checkout to the Pis as a verified, versioned release.
# Usage: ./provision/ota.sh [--force] [--only server|peer] [--user pi] [--host-server IP] [--host-peer IP]
# Order: peer first, then server (the server is the one Cheesy Arena talks to).
# Each Pi: verify sha256 -> new release dir -> atomic switch -> restart -> selfcheck -> auto rollback on failure.
# Refuses (exit 3) if a Pi counted pulses in the last 60 s, i.e. a match may be running; --force overrides.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
USER_="pi"; ONLY=""; FORCE=""; HS=""; HP=""
while [[ $# -gt 0 ]]; do case "$1" in
  --force) FORCE="--force";; --only) ONLY="$2"; shift;; --user) USER_="$2"; shift;;
  --host-server) HS="$2"; shift;; --host-peer) HP="$2"; shift;; *) echo "unknown option $1"; exit 1;; esac; shift; done
# shellcheck disable=SC1091
HS="${HS:-$(source "$root/provision/roles/server.conf"; echo "$IP")}"
HP="${HP:-$(source "$root/provision/roles/peer.conf"; echo "$IP")}"

ver="$(git -C "$root" describe --always --dirty --abbrev=7 2>/dev/null || date +%Y%m%d%H%M%S)"
[[ "$ver" == *-dirty ]] && ver="$ver-$(date +%H%M%S)"   # a dirty tree gets a unique name
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
cp "$root/src/fuelhub.py" "$work/fuelhub.py"; echo "$ver" > "$work/VERSION"
tar -C "$work" -czf "$work/fuelhub-$ver.tar.gz" fuelhub.py VERSION
(cd "$work" && sha256sum "fuelhub-$ver.tar.gz" > "fuelhub-$ver.tar.gz.sha256")
python3 -m py_compile "$work/fuelhub.py"
echo "release $ver"

push() { # push <host>
  local host="$1" t="$USER_@$1"
  scp -q "$work/fuelhub-$ver.tar.gz" "$work/fuelhub-$ver.tar.gz.sha256" "$t:/tmp/"
  ssh "$t" "sudo /usr/local/sbin/fuelhub-apply /tmp/fuelhub-$ver.tar.gz $FORCE; rc=\$?; rm -f /tmp/fuelhub-$ver.tar.gz*; exit \$rc"
}
rc=0
if [[ -z "$ONLY" || "$ONLY" == peer ]];   then echo "== peer   $HP"; push "$HP" || rc=$?; fi
if [[ $rc -eq 0 && ( -z "$ONLY" || "$ONLY" == server ) ]]; then echo "== server $HS"; push "$HS" || rc=$?; fi
[[ $rc -eq 0 ]] && echo "OTA done: $ver" || echo "OTA stopped (exit $rc); see message above. 3 = match running, 1 = rolled back, 2 = bad package"
exit $rc
