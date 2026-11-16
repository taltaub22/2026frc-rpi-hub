#!/usr/bin/env bash
# Runs ON the Pi, as root. Installs a release tarball safely:
#   verify sha256 -> unpack to releases/<version> -> py_compile -> atomic switch of `current`
#   -> restart -> selfcheck -> roll back automatically if the new version is not healthy.
# Usage: fuelhub-apply <release.tar.gz> [--force] [--no-verify]
#   Tarball top level: fuelhub.py, VERSION.  Checksum: <release.tar.gz>.sha256 (sha256sum format).
# Refuses to restart while pulses were counted in the last 60 s (a match may be running) unless --force.
# Env for tests: FUELHUB_ROOT (default /opt/fuelhub), FUELHUB_ENV (/etc/fuelhub/role.env),
#                FUELHUB_STATUS (/run/fuelhub/status.json), NO_SERVICE=1 (skip systemctl + selfcheck),
#                FUELHUB_SELFCHECK_CMD (replace the selfcheck).
# Exit codes: 0 ok / already current, 1 failed and rolled back, 2 bad package, 3 busy (match running).
set -euo pipefail
tarball="${1:?usage: fuelhub-apply <release.tar.gz> [--force] [--no-verify]}"; shift || true
FORCE=0; VERIFY=1
for a in "$@"; do case "$a" in --force) FORCE=1;; --no-verify) VERIFY=0;; *) echo "unknown option $a"; exit 2;; esac; done
ROOT="${FUELHUB_ROOT:-/opt/fuelhub}"; ENVF="${FUELHUB_ENV:-/etc/fuelhub/role.env}"
STATUS="${FUELHUB_STATUS:-/run/fuelhub/status.json}"
[[ -f "$ENVF" ]] && source "$ENVF"
SERVE="${SERVE:-0}"
log() { echo "fuelhub-apply: $*"; logger -t fuelhub-apply "$*" 2>/dev/null || true; }
svc() { [[ "${NO_SERVICE:-0}" == 1 ]] || systemctl "$@"; }

selfcheck() {
  [[ -n "${FUELHUB_SELFCHECK_CMD:-}" ]] && { bash -c "$FUELHUB_SELFCHECK_CMD"; return; }  # tests only
  [[ "${NO_SERVICE:-0}" == 1 ]] && return 0
  local args=(--selfcheck --status-file "$STATUS"); [[ "$SERVE" == 1 ]] && args+=(--serve)
  for _ in $(seq 1 15); do
    python3 "$ROOT/current/fuelhub.py" "${args[@]}" && return 0
    sleep 1
  done
  return 1
}

# 1. verify
if [[ "$VERIFY" == 1 ]]; then
  [[ -f "$tarball.sha256" ]] || { log "missing $tarball.sha256 (use --no-verify to skip)"; exit 2; }
  (cd "$(dirname "$tarball")" && sha256sum -c "$(basename "$tarball").sha256" >/dev/null) || { log "checksum mismatch"; exit 2; }
fi

# 2. unpack + sanity
stage="$(mktemp -d "$ROOT/.stage.XXXXXX" 2>/dev/null || { mkdir -p "$ROOT"; mktemp -d "$ROOT/.stage.XXXXXX"; })"
trap 'rm -rf "$stage"' EXIT
tar -xzf "$tarball" -C "$stage"
[[ -f "$stage/fuelhub.py" && -f "$stage/VERSION" ]] || { log "package lacks fuelhub.py or VERSION"; exit 2; }
python3 -m py_compile "$stage/fuelhub.py" || { log "new fuelhub.py does not compile"; exit 2; }
find "$stage" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
ver="$(tr -cd 'A-Za-z0-9._-' < "$stage/VERSION")"; [[ -n "$ver" ]] || { log "empty VERSION"; exit 2; }

mkdir -p "$ROOT/releases"
prev=""; [[ -L "$ROOT/current" ]] && prev="$(basename "$(readlink "$ROOT/current")")"
if [[ "$prev" == "$ver" && "$FORCE" == 0 ]]; then log "version $ver already running"; exit 0; fi

# 3. busy guard: a restart zeroes this hub's counts, so never do it mid-match
if [[ "$FORCE" == 0 && -f "$STATUS" ]]; then
  age="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("last_activity_age_s"))' "$STATUS" 2>/dev/null || echo None)"
  if [[ "$age" != None ]] && python3 -c "import sys;sys.exit(0 if float('$age')<60 else 1)"; then
    log "pulses counted ${age}s ago: a match may be running. Retry later or use --force"; exit 3
  fi
fi

# 4. install and switch atomically
rm -rf "$ROOT/releases/$ver"; mv "$stage" "$ROOT/releases/$ver"; chmod -R go-w "$ROOT/releases/$ver"; trap - EXIT
ln -sfn "releases/$ver" "$ROOT/current.new" && mv -T "$ROOT/current.new" "$ROOT/current"
log "switched $prev -> $ver"
svc restart fuelhub

# 5. health check, roll back on failure
if selfcheck; then
  log "version $ver healthy"
else
  log "version $ver FAILED selfcheck"
  if [[ -n "$prev" && -d "$ROOT/releases/$prev" ]]; then
    ln -sfn "releases/$prev" "$ROOT/current.new" && mv -T "$ROOT/current.new" "$ROOT/current"
    svc restart fuelhub
    selfcheck && log "rolled back to $prev (healthy)" || log "ROLLBACK ALSO UNHEALTHY: check journalctl -u fuelhub"
  fi
  exit 1
fi

# 6. prune: keep current, previous, and the newest 3 overall
keep="$(ls -1t "$ROOT/releases" | head -3; echo "$ver"; echo "$prev")"
for d in "$ROOT/releases"/*; do b="$(basename "$d")"; grep -qx "$b" <<<"$keep" || rm -rf "$d"; done
exit 0
