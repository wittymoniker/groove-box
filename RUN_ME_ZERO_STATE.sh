#!/usr/bin/env bash
# R28.4.50 HF3: project-root convenience entry point for the sOS zero-state builder.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BUILDER_ENTRY="$ROOT_DIR/BUILD_ISO/RUN_ME_ZERO_STATE.sh"
if [[ ! -f "$BUILDER_ENTRY" ]]; then
  echo "FAIL: missing sOS builder entry point: $BUILDER_ENTRY" >&2
  echo "Extract the complete Groovebox source archive and keep BUILD_ISO beside this file." >&2
  exit 127
fi
# Keep the first actionable error, including early source/preflight failures.
# Logs start before the builder enters sudo, so they belong to the caller.
case "${1:-}" in
  --help|-h) exec bash "$BUILDER_ENTRY" "$@" ;;
esac
LOG_DIR="$ROOT_DIR/BUILD_ISO/logs"
mkdir -p "$LOG_DIR"
BUILD_LOG="$LOG_DIR/iso-build-$(date +%Y%m%d-%H%M%S)-$$.log"
echo "ISO build log: $BUILD_LOG"
set +e
bash "$BUILDER_ENTRY" "$@" 2>&1 | tee "$BUILD_LOG"
status=${PIPESTATUS[0]}
set -e
if [[ "$status" -ne 0 ]]; then
  printf '\nISO builder exited %s. Full diagnostic log: %s\n' "$status" "$BUILD_LOG" >&2
fi
exit "$status"
