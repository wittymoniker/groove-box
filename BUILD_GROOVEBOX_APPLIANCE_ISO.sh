#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ISOBASE="$ROOT/APPLIANCE_ISO"
OUT="${1:-$ROOT/dist/Groovebox-sCode-Appliance-x86_64.iso}"
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo/root: sudo ./BUILD_GROOVEBOX_APPLIANCE_ISO.sh" >&2; exit 3; }
[ -x "$ROOT/sCode/bootstrap/linux-x86_64/scode0" ] || { echo "Bundled required sCode runtime missing." >&2; exit 4; }
# Verify the optimizer before spending time downloading/installing the rootfs.
_SCODE_PLAN=$(cd "$ROOT/sCode" && GB_OPT_ID=1 GB_OPT_DIRTY=255 GB_OPT_FRAME=0 GB_OPT_LANES=4 GB_OPT_POOL=64 GB_OPT_SHAPE=1 \
  ./bootstrap/linux-x86_64/scode0 run apps/groovebox/groovebox_optimizer.sC) \
  || { echo "sCode optimizer execution failed." >&2; exit 5; }
printf '%s\n' "$_SCODE_PLAN" | grep -q '^scode_optimizer_abi=9$' \
  || { echo "sCode optimizer ABI9 preflight failed." >&2; exit 5; }
for _k in pool_slot audio_lane visual_lane game_lane media_lane run_audio run_media coalesce_bucket canonical_pool_slot background_cadence parallel_width symbol_pool_slot symbol_base symbol_full_cycle symbol_half_denominator symbol_subscale_bits symbol_variant_count symbol_pool_key completion_abi completion_policy_count pool_abi scheduler_abi symbol_abi symbol_crossbar_count symbol_crossbar_state_count symbol_full_cycle_main_strokes symbol_full_cycle_main_strokes_solid symbol_full_cycle_solid_mask symbol_full_cycle_dotted_mask; do
  printf '%s\n' "$_SCODE_PLAN" | grep -Eq "^${_k}=[0-9-]+$" \
    || { echo "sCode optimizer returned a non-concrete field: $_k" >&2; printf '%s\n' "$_SCODE_PLAN" >&2; exit 5; }
done

# Static app preflight before staging.
python3 -m py_compile "$ROOT/groovebox.py" "$ROOT/run_groovebox.py" "$ROOT/scode_optimizer_bridge.py" \
  "$ROOT/performance.py" "$ROOT/video_clip_studio.py" "$ROOT/layered_signal_lab.py" "$ROOT/media_layer_engine.py" "$ROOT/parametric_file_remix.py" \
  "$ROOT/author_number_codec.py" "$ROOT/author_numeric_font.py"

echo '[Groovebox Appliance] staging application + sCode into ISO rootfs...'
rm -rf "$ISOBASE/source/rootfs/opt/groovebox" "$ISOBASE/source/sCode"
mkdir -p "$ISOBASE/source/rootfs/opt/groovebox" "$ISOBASE/source/sCode" "$ROOT/dist"
# Avoid recursively embedding the ISO builder and transient outputs in /opt/groovebox.
tar -C "$ROOT" \
  --exclude='./APPLIANCE_ISO' --exclude='./dist' --exclude='./build_executable' \
  --exclude='./.groovebox-build-venv' --exclude='./__pycache__' --exclude='*.pyc' \
  -cf - . | tar -C "$ISOBASE/source/rootfs/opt/groovebox" -xf -
cp -a "$ROOT/sCode/." "$ISOBASE/source/sCode/"
# sCode optimizer is required, not optional.
install -m755 "$ROOT/sCode/bootstrap/linux-x86_64/scode0" "$ISOBASE/source/rootfs/opt/groovebox/sCode/bootstrap/linux-x86_64/scode0"
# Offline runtime check from the staged copy. Imports resolve from the sCode
# root; running from /opt/groovebox would leave imported optimizer helpers null.
_STAGE_PLAN=$(cd "$ISOBASE/source/rootfs/opt/groovebox/sCode" && GB_OPT_ID=2 GB_OPT_DIRTY=255 GB_OPT_FRAME=0 GB_OPT_LANES=4 GB_OPT_POOL=64 GB_OPT_SHAPE=2 \
  ./bootstrap/linux-x86_64/scode0 run apps/groovebox/groovebox_optimizer.sC)
printf '%s\n' "$_STAGE_PLAN" | grep -q '^scode_optimizer_abi=9$'
for _k in pool_slot audio_lane visual_lane game_lane media_lane run_audio run_media coalesce_bucket canonical_pool_slot background_cadence parallel_width symbol_pool_slot symbol_base symbol_full_cycle symbol_half_denominator symbol_subscale_bits symbol_variant_count symbol_pool_key completion_abi completion_policy_count pool_abi scheduler_abi symbol_abi symbol_crossbar_count symbol_crossbar_state_count symbol_full_cycle_main_strokes symbol_full_cycle_main_strokes_solid symbol_full_cycle_solid_mask symbol_full_cycle_dotted_mask; do
  printf '%s\n' "$_STAGE_PLAN" | grep -Eq "^${_k}=[0-9-]+$"
done
# Build using the hardened Fedora43/sOS fat-rootfs path (usr-merge, /var/tmp,
# mounted virtual filesystems, native-transfer hash parser fixes).
"$ISOBASE/BUILD_GAME_READY_ISO.sh" --profile game-ready --output "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
echo "Groovebox appliance ISO: $OUT"
cat "$OUT.sha256"
