# ABI-9 final release validation — 2026-09-07

Status: **FINAL_RELEASE_ABI9|PASS** for the source/staged appliance contract.

## Passed

- Python static compilation: `groovebox.py`, launch bridge, sCode optimizer bridge, Performance, layered media, parametric remix, author-number codec/font, and release tests.
- Bundled stage-0 strict sCode test suite: optimizer ABI 9, pool ABI 3, pool-format ABI 1, 18 formats, scheduler ABI 2, completion ABI 1, five completion policies, symbol ABI 4.
- All exported `pool_format_*` and `pool_request_*` methods are exercised by the strict sCode suite.
- Host universal request descriptor parity against stage-0 sCode across generic, audio, visual/image, video-frame, symbol, project side-effect, sequence/canonical, world and media-stream requests.
- Completion bridge: PURE reuse/coalescing, GENERATION/FRAME stale rejection, STREAM publication, SIDE_EFFECT non-cache/non-coalesce, dedicated `scode-complete` thread.
- Author-number codec: 5,188 semantic states, four ordered cross-bars on every glyph, absent=0/dotted=0.5/solid=1, full-cycle 16 has 12/12 solid main strokes and solid subdivider mask 1111; alternate 16 cross-bar faces are rejected.
- Heuristic writer split: STEP and AUTOMATION have independent field-level revert memories, share GLOBAL/LOCAL scope, and pass both activation-order regressions.
- Groovebox final determinism: 7/7 purity groups.
- Composition parity: PASS.
- Native Groovebox parity is included in the strict sCode suite.
- sOS package profile contains kernel, modules, EFI/BIOS GRUB, dracut, filesystem and partitioning tools required for installed-appliance boot.
- `sos-install-appliance` syntax and safety guards: preflight before erase, whole-disk checks, mounted-target refusal, explicit erase phrase, at least one GRUB firmware path required.
- Installed normal and Safe/Recovery GRUB entries explicitly locate the root filesystem by UUID.
- Linux/macOS shell syntax pass for packaged shell/build scripts.
- Critical root files byte-match staged `/opt/groovebox`; runtime pool/completion libraries also byte-match standalone staged `APPLIANCE_ISO/source/sCode`.
- The strict sCode suite and host/stage-0 pool descriptor parity both pass again from the exact staged `/opt/groovebox` payload.

## Validation boundary

The packaging environment does not provide a full PyQt6/audio/display hardware session and does not build the final Fedora package-fed ISO with network/root privileges. Therefore interactive GUI/device operation and physical/VM boot of the generated ISO remain deployment-machine tests. The builder, installed-root staging, preflight and disk-install scripts are included and statically/runtime-contract validated without executing destructive disk installation.

## ABI-9 corrections in this release

- Semantic cell `16` is invariant: **12/12 main strokes solid + 4/4 subdividers solid**; dotted/missing `16` variants are rejected by the codec and sCode symbol ABI.
- Valid semantic face count is **5,188**, because values 0..15 retain all four ternary cross-bar states while cell 16 has one fixed cross-bar state.
- Heuristic composition is split into **HEURISTIC WRITE STEP** and **HEURISTIC WRITE AUTOMATION**. Each has independent field-level revert memory and both obey the shared GLOBAL/LOCAL scope selector.
- Headless activation-order tests prove either writer can be reverted without erasing the other.
- Final validation was completed as segmented gates because the packaging harness limits one long combined shell run; every constituent gate passed independently, including staged sCode, 7/7 determinism, composition parity, rootfs hashes, and source/stage byte parity.

## Two-writer cleanup validation

- PASS: exactly one `HEURISTIC WRITE STEP` control.
- PASS: exactly one `HEURISTIC WRITE AUTOMATION` control.
- PASS: legacy `btn_nt_apply`, `_on_nt_lattice_apply`, `chk_edit_algorithm_per_sequence`, and `_sync_nt_lattice_button_state` are absent from active Groovebox source.
- PASS: STEP and AUTOMATION independent revert regression in both activation orders.
- PASS: Algorithm XMod activation now follows the authoritative STEP writer.
- PASS: deterministic visual/composition tests remain unchanged.
- PASS: sCode optimizer ABI 9 / pool ABI 3 / symbol ABI 4 unchanged.
- NOTE: PyQt6 is not installed in the packaging container, so the full interactive GUI import/launch test remains a target-machine acceptance step.
