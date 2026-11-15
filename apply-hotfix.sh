#!/usr/bin/env bash
set -euo pipefail
PATCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="${1:-}"
[[ -n "$PROJECT_ROOT" && -d "$PROJECT_ROOT/BUILD_ISO" ]] || {
  echo "Usage: $0 /path/to/MATH_GROOVEBOX-v3" >&2
  exit 2
}
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -P)"
TARGET="$PROJECT_ROOT/BUILD_ISO/RUN_ME_v35_22.sh"
PATCH="$PATCH_ROOT/BUILD_ISO/RUN_ME_v35_22.sh"
[[ -f "$TARGET" && -f "$PATCH" ]] || { echo 'FAIL: target runner or replacement missing' >&2; exit 2; }
if grep -Fq 'python3 "$ROOT/scripts/sync_runtime_payload.py"' "$TARGET"; then
  echo 'Already patched; no changes made.'
  exit 0
fi
cp -p "$TARGET" "$TARGET.before-r56-sync-hotfix"
cp "$PATCH" "$TARGET"
chmod +x "$TARGET"
echo "Applied R56 builder sync hotfix to $TARGET"
echo "Backup: $TARGET.before-r56-sync-hotfix"
