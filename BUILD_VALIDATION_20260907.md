# Groovebox + sCode Full Acceleration validation — ABI 5 — 2026-09-07

Validated against both the outer source tree and the exact `/opt/groovebox` tree staged into the appliance ISO.

## Required runtime and symbol contract

- Required sCode optimizer ABI: **5** — PASS.
- Concrete sCode author-number contract — PASS:
  - base = 16
  - completed/full-cycle semantic cell = 16
  - in-cell squiggle fractional denominator = 2 (`2^-1`)
  - additional fractional subscale = 4 bits per slot (`16^-k = 2^-4k`)
  - precomputed semantic variants = 68 (`0..16 × squiggle/no-squiggle × spaced/unspaced`)
  - symbol pool key and symbol pool slot are concrete integers.
- Spacing semantics — PASS: at fractional slot 1, value 4 contributes 0.25 when spaced/full and 0.125 when unspaced/half-slot.
- Native sCode fractional extraction — PASS: decimal fraction 0.20 begins with base-16 subscale cells 3, 3.
- Pure Python/host codec round-trip and precision tests — PASS.
- Exact underlying control/project numbers are preserved; display spelling never overwrites them.

## Hot-path integration

- Per-field source dirty gate skips the codec for unchanged values — PASS (static/integration validation).
- Immutable number-spelling packets are memoized through the shared required sCode optimizer bridge — PASS.
- 68 semantic glyph variants are precomputed; individual Qt glyph faces and composed number pixmaps have bounded LRU caches — PASS.
- Explicit authored rewrites support per-slot spaced `1/1` and unspaced `1/2` semantics — PASS (API/static + pure-codec validation).
- Project save/load/provenance exposes `base16-squiggle-subscale-v4` author-number metadata — PASS.
- Numeric scripting exposes the same spelling/decoding/fraction helpers — PASS.
- Help/README symbol-language section documents the base-16/full-cycle, in-cell squiggle, `2^-4k` continuation, and spacing rules — PASS.

## Full sOS/sCode/native validation

The final staged source suite completed all 11 phases:

1. sCode runtime — PASS
2. static check of all sCode sources — PASS (**93 modules**)
3. hardware modality imports — PASS
4. logic/math duality and pooling — PASS
5. author-number symbol codec — PASS
6. finite-infinity compiled index — PASS
7. full native cross-media export — PASS
8. deterministic parity — PASS
9. rootfs shell syntax — PASS
10. source build helper — PASS
11. manifests and required handles — PASS

Python static compilation passed for Groovebox, required sCode bridge, author-number codec/font, Performance, layered Draw/Record, media layering and Parametric Remix modules. Shell syntax passed for 34 Linux/macOS `.sh`/`.command` entry points. `run_hybrid.sh` invokes its platform build helper via `bash`, avoiding the prior ZIP executable-bit `Permission denied` failure.

## Current microbenchmarks

These are isolated path measurements from this build container, **not whole-application multipliers**:

- sCode optimization plan: ~1.615 ms fresh vs ~0.00437 ms cached (~370× cached-plan speedup).
- unchanged layered-media reconstruction: ~3.385 ms raw vs ~0.01394 ms memoized (~243× path speedup).
- playlist row activation setup: ~6.119 ms old whole-song Boolean-mask path vs ~0.00205 ms indexed slice (~2,982× path speedup).
- symbol semantic codec: ~22.14 ms for 1000 cold spellings vs ~0.805 ms for 1000 cached spellings (~27.5× in-process cache speedup).
- sCode memoized symbol packet lookup: ~3.33 µs per cached lookup in the benchmark path.

## Environment limitation

PyQt6 is not installed in this packaging container, so the complete GUI could not be interactively exercised here. The Python sources compile, the Qt-free number codec tests execute, the required sCode runtime executes, and the appliance dependency/rootfs flow installs PyQt6 on the target system. Final ISO creation still requires the host/container Fedora DNF + GRUB/xorriso build environment.
