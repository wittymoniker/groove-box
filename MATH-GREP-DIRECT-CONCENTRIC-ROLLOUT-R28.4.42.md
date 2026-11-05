# Math-grep + Direct-Concentric Cross-Media Rollout — R28.4.42

## What is implemented

- `math_grep.py`: Python AST-based discovery of numeric literals, arithmetic expressions, common math functions, comparisons, and scale/bound operations.
- Findings retain file, line/column, source SHA-256, category, expression, conservative exact rational form where safely evaluable, and explicit evidence needed.
- Exact arithmetic is labeled `exact-syntax-only`; this is intentionally not called semantic proof. Unknown meaning, units, domain, and model-to-reality correspondence remain unresolved until separately specified and checked.
- `universal_field.py`: shared canonical field and deterministic concentric samples, plus audio/video/game adapters, correspondence manifests, and reconstruction/invariance reports.
- The same `direct-concentric-v1` shaping identity is carried through each medium adapter. Adapter-specific channels remain distinct; this is correspondence of provenance/structure, not proof that every rendered artifact is an exact fractal.
- Added regression tests for rational arithmetic classification, source lineage, syntax-error reporting, concentric nesting, deterministic cross-medium identity, and projection reconstruction.

## Evidence produced

The focused rollout suite ran 17 tests successfully: math-grep evidence tests, direct-concentric correspondence tests, video visual contract tests, linear EQ contract tests, instrument translation determinism, and performance/thread lifecycle contracts.

## Evidence limits / release gates

- Static AST discovery is not full symbolic execution, type inference, unit inference, or a proof of physical semantics.
- Cross-medium manifests prove shared source identity and deterministic adapter derivation, not that every audio/video/game execution path consumes the adapter. Integration coverage must be expanded as each live path is connected.
- The full OS ISO was not built or boot-tested in this environment. ISO mastering utilities (`xorriso`, `genisoimage`, `mkisofs`) and a container build runtime were not present in PATH during this rollout check. This release is source/build inputs, not a bootable ISO.
- The previously known installer CRC32C/initramfs issue remains a blocking hardware-install verification item. Do not mark Install-to-SSD passed until CRC32C is included in the target initramfs and the Dell path is re-tested.

## Reproduction

```sh
python math_grep.py universal_field.py groovebox.py video_clip_studio.py videogame_engine.py --json math-grep-report.json
python -m pytest -q BUILD_ISO/release-tests-r28.4.42/test_math_grep_evidence.py BUILD_ISO/release-tests-r28.4.41/test_direct_concentric_rollout_r28_4_42.py test_video_fractal_visual_contract.py test_eq_linear_frequency_contract_r28_4_39.py test_instrument_translation_determinism.py test_performance_thread_lifecycle_contract.py
```

## Safety invariants

- No stochastic/probabilistic behavior is introduced by math-grep.
- The scanner does not rewrite source code.
- Exact simplification is conservative and only evaluates integer rational arithmetic in a restricted subset.
- No changes were made to the real-time audio callback or hardware routing in this rollout.
