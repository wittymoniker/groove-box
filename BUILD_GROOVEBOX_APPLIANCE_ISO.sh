#!/usr/bin/env bash
# v35.22: legacy entry point forwards to the maintained zero-state sOS builder.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# GROOVEBOX_R101_RESTORE_EXEC_BITS: zip tools often drop the executable bit; every script that starts with #!
# under BUILD_ISO and scripts/ gets it back before anything checks [ -x ] (build entry, staged boot helpers).
find "$ROOT/BUILD_ISO" "$ROOT/scripts" -type f -size -4M 2>/dev/null | while IFS= read -r _f; do
  [ -x "$_f" ] || { [ "$(head -c 2 "$_f" 2>/dev/null | tr -d '\0')" = '#!' ] && chmod a+x "$_f"; } || true
done
[[ -x "$ROOT/BUILD_ISO/RUN_ME_ZERO_STATE.sh" ]] || {
  echo 'FAIL: BUILD_ISO/RUN_ME_ZERO_STATE.sh is missing or not executable.' >&2
  exit 4
}
exec bash "$ROOT/BUILD_ISO/RUN_ME_ZERO_STATE.sh"
