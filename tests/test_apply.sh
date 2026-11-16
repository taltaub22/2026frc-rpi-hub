#!/usr/bin/env bash
# Tests deploy/fuelhub-apply.sh against a temp root (no systemd). Run: bash tests/test_apply.sh
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; apply="$here/deploy/fuelhub-apply.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export FUELHUB_ROOT="$T/opt" FUELHUB_ENV="$T/none" FUELHUB_STATUS="$T/status.json" NO_SERVICE=1
mkdir -p "$FUELHUB_ROOT"; fails=0
check() { if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1 (got '$2', want '$3')"; fails=$((fails+1)); fi; }
mkpkg() { # mkpkg <version> [source]
  local d="$T/pkg-$1"; mkdir -p "$d"; printf '%s\n' "${2:-print(1)}" > "$d/fuelhub.py"; echo "$1" > "$d/VERSION"
  tar -C "$d" -czf "$T/$1.tar.gz" fuelhub.py VERSION; (cd "$T" && sha256sum "$1.tar.gz" > "$1.tar.gz.sha256"); }
cur() { basename "$(readlink "$FUELHUB_ROOT/current")"; }

mkpkg v1; "$apply" "$T/v1.tar.gz" >/dev/null; check "first install" "$(cur)" v1
"$apply" "$T/v1.tar.gz" >/dev/null; check "same version is a no-op" "$?" 0
mkpkg v2; "$apply" "$T/v2.tar.gz" >/dev/null; check "upgrade" "$(cur)" v2
mkpkg v3 "def broken(:"; "$apply" "$T/v3.tar.gz" >/dev/null 2>&1; check "syntax error rejected (rc)" "$?" 2; check "still v2" "$(cur)" v2
mkpkg v4; echo tampered >> "$T/v4.tar.gz"; "$apply" "$T/v4.tar.gz" >/dev/null 2>&1; check "bad checksum rejected (rc)" "$?" 2
check "no v4 dir" "$([[ -d $FUELHUB_ROOT/releases/v4 ]] && echo yes || echo no)" no
mkpkg v5; export FUELHUB_SELFCHECK_CMD='! grep -q v5 "$FUELHUB_ROOT/current/VERSION"'
"$apply" "$T/v5.tar.gz" >/dev/null 2>&1; check "unhealthy update fails (rc)" "$?" 1; check "rolled back to v2" "$(cur)" v2
unset FUELHUB_SELFCHECK_CMD
mkpkg v6; echo '{"last_activity_age_s": 5.0}' > "$FUELHUB_STATUS"
"$apply" "$T/v6.tar.gz" >/dev/null 2>&1; check "busy guard (rc)" "$?" 3; check "still v2 when busy" "$(cur)" v2
"$apply" "$T/v6.tar.gz" --force >/dev/null 2>&1; check "--force overrides busy" "$(cur)" v6
echo '{"last_activity_age_s": null}' > "$FUELHUB_STATUS"; mkpkg v7; "$apply" "$T/v7.tar.gz" >/dev/null; check "idle hub updates" "$(cur)" v7
check "pruned to <=4 releases" "$([[ $(ls "$FUELHUB_ROOT/releases" | wc -l) -le 4 ]] && echo yes || echo no)" yes
exit $fails
