#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STAMP="${1:-$(date +%Y%m%d-%H%M%S)}"
OUTDIR="$ROOT/dist_release"
mkdir -p "$OUTDIR"
ZIP="$OUTDIR/groovebox_STORAGE_RECOVERY_APPLIANCE_${STAMP}.zip"
TGZ="$OUTDIR/groovebox_STORAGE_RECOVERY_APPLIANCE_${STAMP}.tar.gz"
cd "$(dirname "$ROOT")"
BASE="$(basename "$ROOT")"
# Keep the complete APPLIANCE_ISO builder tree and its seed initramfs. Exclude
# only transient build roots, generated ISO images, caches and user data.
EX=(
  "$BASE/__pycache__/*" "$BASE/.pytest_cache/*" "$BASE/.groovebox-build-venv/*"
  "$BASE/dist_release/*" "$BASE/APPLIANCE_ISO/.fat-build/*" "$BASE/APPLIANCE_ISO/dist/*.iso"
  "$BASE/APPLIANCE_ISO/dist/*.iso.sha256" "$BASE/projects/*" "$BASE/samples/*" "$BASE/exports/*"
)
rm -f "$ZIP" "$TGZ"
if command -v zip >/dev/null 2>&1; then
  args=(); for e in "${EX[@]}"; do args+=( -x "$e" ); done
  zip -qr "$ZIP" "$BASE" "${args[@]}"
else
  echo 'zip command is required for release ZIP' >&2; exit 2
fi
TEX=(); for e in "${EX[@]}"; do TEX+=( --exclude="$e" ); done
tar -czf "$TGZ" "${TEX[@]}" "$BASE"
sha256sum "$ZIP" "$TGZ" > "$OUTDIR/SHA256SUMS_${STAMP}.txt"
echo "$ZIP"
echo "$TGZ"
