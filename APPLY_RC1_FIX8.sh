#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="${1:-$(pwd -P)}"
ROOT="$(cd "$ROOT" && pwd -P)"
BACKUP="$ROOT/.matgroovebox-fix8-backup/$(date +%Y%m%d-%H%M%S)"
[[ -f "$ROOT/BUILD_ISO/RUN_ME_v35_22.sh" && -f "$ROOT/BUILD_ISO/secure_boot_v1.sh" ]] || {
  echo "FAIL: expected MATGROOVEBOX project root, got $ROOT" >&2; exit 2;
}
copy_rel() {
  local rel="$1"
  [[ -s "$HERE/$rel" ]] || { echo "FAIL: patch source missing: $rel" >&2; exit 3; }
  mkdir -p "$(dirname "$ROOT/$rel")"
  if [[ -f "$ROOT/$rel" ]]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -p "$ROOT/$rel" "$BACKUP/$rel"
  fi
  install -m 0644 "$HERE/$rel" "$ROOT/$rel"
}
for rel in \
  BUILD_ISO/secure_boot_v1.sh \
  BUILD_ISO/verify_secure_boot_contract_r49_26.py \
  BUILD_ISO/RUN_ME_v35_22.sh \
  BUILD_ISO/sync_overlay_to_root.sh \
  BUILD_ISO/verify_r56_expansion.py \
  dev_overlay.py groovebox_subprocess.py import_fabric.py \
  BUILD_ISO/app-overlay-v35.22zz/dev_overlay.py \
  BUILD_ISO/app-overlay-v35.22zz/groovebox_subprocess.py \
  BUILD_ISO/app-overlay-v35.22zz/import_fabric.py \
  R64-FINALIZATION-CHECKPOINT-20261114.md; do
  copy_rel "$rel"
done
bash -n "$ROOT/BUILD_ISO/secure_boot_v1.sh" "$ROOT/BUILD_ISO/RUN_ME_v35_22.sh"
python3 -m py_compile "$ROOT/BUILD_ISO/verify_secure_boot_contract_r49_26.py" "$ROOT/BUILD_ISO/verify_r56_expansion.py"
python3 "$ROOT/BUILD_ISO/verify_secure_boot_contract_r49_26.py"
python3 "$ROOT/BUILD_ISO/verify_r56_expansion.py"
python3 "$ROOT/scripts/sync_runtime_payload.py" --check
echo "Backup of replaced files: $BACKUP"
echo "PASS: R64 RC1 FIX8 source patch applied to $ROOT"
