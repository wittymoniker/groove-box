#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ISO="$ROOT/APPLIANCE_ISO"
STAGE="$ISO/source/rootfs/opt/groovebox"
fail(){ echo "FAIL: $*" >&2; exit 1; }
pass(){ echo "PASS: $*"; }

cd "$ROOT"
python3 -m py_compile groovebox.py run_groovebox.py scode_optimizer_bridge.py \
  performance.py performance_box.py layered_signal_lab.py media_layer_engine.py media_cutup_engine.py parametric_file_remix.py \
  author_number_codec.py author_numeric_font.py test_scode_completion_bridge.py \
  test_scode_pool_descriptor_parity.py test_heuristic_writer_split.py test_full_cycle_renderer_contract.py test_project_media_contract.py test_algorithm_automation_parity.py groovebox_media_tools.py groovebox_paths.py videogame_engine.py standalone_import_audit.py
pass 'Python compile surface'

(cd sCode && bash scripts/test.sh >/tmp/groovebox-scode-abi9-test.log)
grep -q 'PASS: sCode optimizer/runtime contract ABI 9' /tmp/groovebox-scode-abi9-test.log || fail 'sCode ABI9 suite'
pass 'sCode strict ABI9 suite'

python3 test_scode_pool_descriptor_parity.py >/tmp/groovebox-pool-parity.log
grep -q 'PASS: host universal pool descriptor parity with sCode stage-0' /tmp/groovebox-pool-parity.log || fail 'pool descriptor parity'
pass 'host/stage-0 universal pool descriptor parity'

python3 test_scode_completion_bridge.py >/tmp/groovebox-completion.log
grep -q 'PASS sCode completion bridge ABI9' /tmp/groovebox-completion.log || fail 'completion bridge'
pass 'worker/completion bridge semantics'

python3 test_author_number_codec.py >/tmp/groovebox-symbols.log
grep -q 'PASS author number codec crossbars 5188' /tmp/groovebox-symbols.log || fail 'author symbol codec'
pass '5,188-state four-crossbar author symbol codec'
python3 test_full_cycle_renderer_contract.py >/tmp/groovebox-full16-render.log
grep -q 'PASS renderer full-cycle 16 = 12 solid main strokes + invariant 4 solid subdividers' /tmp/groovebox-full16-render.log || fail 'full-cycle renderer contract'
python3 test_heuristic_writer_split.py >/tmp/groovebox-heuristic-split.log
grep -q 'PASS heuristic STEP/AUTOMATION independent revert' /tmp/groovebox-heuristic-split.log || fail 'heuristic writer split/revert'
pass 'full-cycle renderer + independent heuristic writers'

python3 test_project_media_contract.py >/tmp/groovebox-project-media.log
grep -q 'PASS project-local paths + media index contract' /tmp/groovebox-project-media.log || fail 'project/media path contract'
# Runtime may not download during validation, but source/stage must enforce local-only resolution.
! grep -R --include='*.py' -nE 'shutil\.which\(["'"'"']ff(mpeg|probe)|\[["'"'"']ff(mpeg|probe)["'"'"']' . --exclude-dir=APPLIANCE_ISO --exclude=videogame_engine.py --exclude=provision_first_launch.py >/tmp/groovebox-ffmpeg-fallbacks.log || { cat /tmp/groovebox-ffmpeg-fallbacks.log; fail 'system ffmpeg/ffprobe fallback remains'; }
grep -q 'require_local_pair' run_groovebox.py || fail 'first-launch local ffmpeg preflight'
grep -q 'ensure_local_ffmpeg' BUILD_KIT/build.py || fail 'build local ffmpeg preflight'
grep -q 'setup_ffmpeg' launch_desktop.sh || fail 'desktop local ffmpeg preflight'
grep -q 'setup_ffmpeg' launch_mobile.sh || fail 'mobile local ffmpeg preflight'
! grep -q 'provision_first_launch.py.*|| true' run_hybrid.sh || fail 'hybrid launcher ignores codec provision failure'
python3 test_algorithm_automation_parity.py >/tmp/groovebox-algorithm-parity.log
grep -q 'PASS algorithm XMOD step/automation variable parity without lane composition' /tmp/groovebox-algorithm-parity.log || fail 'algorithm step/automation parity'
pass 'project-local storage + strict local FFmpeg + algorithm automation parity'

python3 test_final_determinism.py >/tmp/groovebox-determinism.log
grep -q 'RESULT: 7/7 final determinism purity groups passed' /tmp/groovebox-determinism.log || fail 'determinism'
python3 test_composition_parity.py >/tmp/groovebox-parity.log
grep -qx 'PASS' /tmp/groovebox-parity.log || fail 'composition parity'
pass 'Groovebox determinism + composition parity'

python3 test_sequence_conductor.py >/tmp/groovebox-sequence-conductor.log
python3 test_game_runtime.py >/tmp/groovebox-game-runtime.log
python3 test_open_world_sandbox.py >/tmp/groovebox-open-world.log
python3 tests.py >/tmp/groovebox-unified.log
python3 standalone_import_audit.py >/tmp/groovebox-import-audit.json
python3 - <<'PY_AUDIT'
import json
rows=json.load(open('/tmp/groovebox-import-audit.json'))
assert not [r for r in rows if r.get('class')=='review']
PY_AUDIT
grep -q 'ALL AVAILABLE TESTS PASSED' /tmp/groovebox-unified.log || fail 'unified determinism/game battery'
pass 'generated-game + unified determinism + standalone import audit'

# sOS/appliance static safety/boot checks.
for pkg in kernel-core kernel-modules grub2-efi-x64 grub2-pc dracut dosfstools e2fsprogs parted util-linux; do
  grep -qx "$pkg" "$ISO/profiles/packages/game-ready-fedora.txt" || fail "missing installed-appliance package $pkg"
done
bash -n "$ISO/source/rootfs/usr/bin/sos-install-appliance"
bash -n "$ISO/source/rootfs/usr/bin/sos-appliance-preflight"
grep -q 'search --no-floppy --fs-uuid --set=root \$ROOT_UUID' "$ISO/source/rootfs/usr/bin/sos-install-appliance" || fail 'installed GRUB root UUID search'
grep -q 'sos-appliance-preflight' "$ISO/source/rootfs/usr/bin/sos-install-appliance" || fail 'installer preflight guard'
grep -q 'scode_optimizer_abi=9' "$ISO/source/rootfs/usr/bin/sos-appliance-preflight" || fail 'sOS ABI9 preflight'
pass 'sOS installed-appliance boot/install guards'

# Cross-platform shell syntax for scripts we can parse in this Linux release environment.
while IFS= read -r f; do bash -n "$f" || fail "shell syntax $f"; done < <(find "$ROOT" -type f \( -name '*.sh' -o -name '*.command' \) -not -path '*/APPLIANCE_ISO/source/rootfs/opt/groovebox/*' | sort)
pass 'Linux/macOS shell syntax'

# The staged ISO payload must be byte-identical for the critical pair.
for rel in \
  scode_optimizer_bridge.py author_number_codec.py author_numeric_font.py groovebox.py graph_script_context.py dj_effects.py groovebox_paths.py groovebox_media_tools.py layered_signal_lab.py performance.py performance_box.py media_output_router.py media_layer_engine.py media_cutup_engine.py parametric_file_remix.py radio_station.py videogame_engine.py standalone_import_audit.py bin/README.txt run_groovebox.py test_project_media_contract.py test_algorithm_automation_parity.py launch_desktop.sh launch_mobile.sh run_hybrid.sh scripts/provision_first_launch.py HELP_TEXT.md \
  sCode/apps/groovebox/groovebox_optimizer.sC sCode/apps/groovebox/pool_catalog.sC \
  sCode/apps/groovebox/pool_request_probe.sC sCode/scode/libs/runtime/pool.sC \
  sCode/scode/libs/runtime/completion.sC sCode/scode/libs/groovebox/symbols.sC \
  sCode/scode/libs/groovebox/symbol_plan.sC sCode/scripts/test.sh; do
  cmp "$ROOT/$rel" "$STAGE/$rel" || fail "staged mismatch: $rel"
done
cmp "$ROOT/sCode/scode/libs/runtime/pool.sC" "$ISO/source/sCode/scode/libs/runtime/pool.sC" || fail 'standalone staged sCode pool mismatch'
cmp "$ROOT/sCode/scode/libs/runtime/completion.sC" "$ISO/source/sCode/scode/libs/runtime/completion.sC" || fail 'standalone staged sCode completion mismatch'
pass 'staged /opt/groovebox and standalone sCode parity'

# Run sCode from the exact staged /opt/groovebox payload.
(cd "$STAGE/sCode" && bash scripts/test.sh >/tmp/groovebox-staged-scode.log)
grep -q 'PASS: sCode optimizer/runtime contract ABI 9' /tmp/groovebox-staged-scode.log || fail 'staged sCode ABI9 suite'
(cd "$STAGE" && python3 test_scode_pool_descriptor_parity.py >/tmp/groovebox-staged-pool.log)
grep -q 'PASS: host universal pool descriptor parity with sCode stage-0' /tmp/groovebox-staged-pool.log || fail 'staged pool parity'
pass 'staged ABI9 runtime + pool descriptor parity'

echo 'FINAL_RELEASE_ABI9|PASS'
