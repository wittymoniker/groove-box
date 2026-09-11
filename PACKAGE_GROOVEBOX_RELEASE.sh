#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTDIR="${1:-$ROOT/dist_release}"
mkdir -p "$OUTDIR"
PARENT="$(dirname "$ROOT")"
BASE="$(basename "$ROOT")"
ZIP="$OUTDIR/groovebox.zip"
TGZ="$OUTDIR/groovebox.tar.gz"
IZIP="$OUTDIR/BUILD_ISO.zip"
ITGZ="$OUTDIR/BUILD_ISO.tar.gz"
SUMS="$OUTDIR/SHA256SUMS.txt"

rm -f "$ZIP" "$TGZ" "$IZIP" "$ITGZ" "$SUMS"
cd "$PARENT"

# Main GitHub release: keep all application/runtime/build entry points but split
# the heavy APPLIANCE_ISO builder tree into the companion BUILD_ISO archives.
MAIN_EX=(
  "$BASE/APPLIANCE_ISO/" "$BASE/APPLIANCE_ISO/*"
  "$BASE/__pycache__/*" "$BASE/.pytest_cache/*" "$BASE/.groovebox-build-venv/*"
  "$BASE/dist_release/*" "$BASE/dist/*" "$BASE/build_executable/*"
  "$BASE/projects/*" "$BASE/samples/*" "$BASE/exports/*"
)
zip_args=(); for e in "${MAIN_EX[@]}"; do zip_args+=( -x "$e" ); done
zip -qr "$ZIP" "$BASE" "${zip_args[@]}"
tar -czf "$TGZ" \
  --exclude="$BASE/APPLIANCE_ISO" \
  --exclude="$BASE/__pycache__" --exclude="$BASE/.pytest_cache" --exclude="$BASE/.groovebox-build-venv" \
  --exclude="$BASE/dist_release" --exclude="$BASE/dist" --exclude="$BASE/build_executable" \
  --exclude="$BASE/projects" --exclude="$BASE/samples" --exclude="$BASE/exports" \
  "$BASE"

# Companion ISO builder: paths intentionally begin with groovebox/APPLIANCE_ISO
# so extracting beside the main archive merges directly into the same tree.
# The top-level ISO builder recreates these duplicate staging copies before use.
ISO_EX=(
  "$BASE/APPLIANCE_ISO/.fat-build/" "$BASE/APPLIANCE_ISO/.fat-build/*"
  "$BASE/APPLIANCE_ISO/dist/*.iso" "$BASE/APPLIANCE_ISO/dist/*.iso.sha256"
  "$BASE/APPLIANCE_ISO/source/rootfs/opt/groovebox/" "$BASE/APPLIANCE_ISO/source/rootfs/opt/groovebox/*"
  "$BASE/APPLIANCE_ISO/source/sCode/" "$BASE/APPLIANCE_ISO/source/sCode/*"
  "$BASE/APPLIANCE_ISO/iso-root/boot/initramfs.img"
  "$BASE/APPLIANCE_ISO/iso-root/boot/initramfs.img.orig-backup"
  "$BASE/APPLIANCE_ISO/dist/initramfs-sOS-scode.img"
  "$BASE/APPLIANCE_ISO/dist/initramfs-sOS-scode.img.sha256"
)
iso_zip_args=(); for e in "${ISO_EX[@]}"; do iso_zip_args+=( -x "$e" ); done
zip -qr "$IZIP" "$BASE/APPLIANCE_ISO" "${iso_zip_args[@]}"
tar -czf "$ITGZ" \
  --exclude="$BASE/APPLIANCE_ISO/.fat-build" \
  --exclude="$BASE/APPLIANCE_ISO/dist/*.iso" --exclude="$BASE/APPLIANCE_ISO/dist/*.iso.sha256" \
  --exclude="$BASE/APPLIANCE_ISO/source/rootfs/opt/groovebox" \
  --exclude="$BASE/APPLIANCE_ISO/source/sCode" \
  --exclude="$BASE/APPLIANCE_ISO/iso-root/boot/initramfs.img" \
  --exclude="$BASE/APPLIANCE_ISO/iso-root/boot/initramfs.img.orig-backup" \
  --exclude="$BASE/APPLIANCE_ISO/dist/initramfs-sOS-scode.img" \
  --exclude="$BASE/APPLIANCE_ISO/dist/initramfs-sOS-scode.img.sha256" \
  "$BASE/APPLIANCE_ISO"

sha256sum "$ZIP" "$TGZ" "$IZIP" "$ITGZ" > "$SUMS"
printf '%s\n' "$ZIP" "$TGZ" "$IZIP" "$ITGZ" "$SUMS"
