#!/usr/bin/env bash
# v35.22: legacy entry point forwards to the maintained zero-state sOS builder.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ -x "$ROOT/BUILD_ISO/RUN_ME_ZERO_STATE.sh" ]] || {
  echo 'FAIL: BUILD_ISO/RUN_ME_ZERO_STATE.sh is missing or not executable.' >&2
  exit 4
}
exec "$ROOT/BUILD_ISO/RUN_ME_ZERO_STATE.sh" "$ROOT"
