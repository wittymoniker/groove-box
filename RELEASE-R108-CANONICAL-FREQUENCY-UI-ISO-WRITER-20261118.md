# R108 — canonical frequency, field-console, and ISO writer hardening

## Fractal Seed frequency

- Adds a persistent absolute root frequency setting (20–20,000 Hz; recommended 432 Hz) to Performance → Canonical / Seed.
- The Fractal Seed event plan cache key includes both the configured root frequency and the current global reference frequency.
- Rasterized pitch ratios are normalized against the global base-frequency control, so the resulting canonical sequence actually sounds at the selected Fractal Seed root frequency rather than merely displaying it.
- Existing projects without the new field migrate to 432 Hz. Invalid/out-of-range values normalize safely.

## GOAVA amplitudes

- Performance → Canonical / Seed exposes independent linear amplitude controls for the three GOAVA sine voices.
- The selected amplitudes are carried into the event chord, GOAVA canonical playlist metadata, and `_goava_mix` audio rendering. They are project-persistent and update the canonical composition through the existing cooperative refresh path.
- GOAVA remains a non-instrument harmonic layer; it does not claim an instrument identity or overwrite instrument sequence ownership.

## RAND / LOCK coverage clarification

- RAND uses its captured per-engine RNG for the automation-lane generator as well as its playlist/sequence generation. The previous automation helper silently recreated an RNG from the project seed; that bypass is removed.
- RAND continues through the canonical playlist writer, generated synth context, domain/patch context, sequence-panel writer, and generated automation path. User-protected values and user-authored scripts remain protected.
- LOCK uses deterministic phase-lock sequence projection, wavefield phase-locking, canonical playlist painting, contour/step lanes, and velocity-link shaping. It is not intended to randomize every unrelated synth control; it preserves user-locked material and controls its relationship/timing/velocity fields.
- The `canonicals`, `panels`, and `runtime` console commands provide on-device state/coverage/runtime diagnostics.

## In-app console

- Console button remains in the main global canonical row.
- Ctrl+Shift+` is installed as a real shortcut; the Settings/Compatibility menu also exposes the console.
- Positional command arguments now reach command handlers (`mgr types`, `party on`, etc.). Added `canonicals`, `runtime`, and `windows` diagnostics.

## Language runtimes

- The active ISO overlay is synchronized from the authoritative root, including the Program Builder with no redundant per-language/manual Julia installer button.
- The image build provisions Go, Julia 1.11.7, JuliaCall/PythonCall, LuaJIT, C/C++, Python/Shell and a Rust compiler payload; the final rootfs checks execute GCC, G++, Go, the lazy Rust compiler wrapper, Julia, JuliaCall/PythonCall, and LuaJIT against the target filesystem. These are build contracts, not claims that a new ISO has already been built in this environment.

## Bytecode and launch integrity

- The final initramfs builder now syntax-checks Python sources in memory instead of invoking `py_compile` on deployed app/helper files.
- Stale `__pycache__` directories and `.pyc/.pyo` files are purged from the deployed application and SOS helper trees before the final source syntax sweep; the finalizer fails if any remain.
- Existing R107 no-bytecode launchers and Qt single-instance activation remain in place.

## Latitude UI sizing

- `fit_dialog_to_screen` now uses the dialog's own screen when available and clamps both minimum and maximum sizes to the screen's available work area. A small Latitude work area can no longer be forced to host a 480×520 dialog that extends behind the panel.
- This is a source-level geometry correction; actual Latitude compositing, button hit targets, and physical scrolling still require a GUI test on the laptop.

## Five-ISO / seven-partition writer

`BUILD_ISO/write_five_isos_7part.sh` and `BUILD_ISO/select_recent_isos.py` provide the new workflow:

1. Shared Limine EFI/config/kernel/initramfs/certificate payload.
2–6. The five newest complete ISO images (one dynamically sized exFAT volume each).
7. One independent exFAT data volume using the remaining capacity.

Run `sudo BUILD_ISO/write_five_isos_7part.sh /dev/sdX` to select the five newest images from `BUILD_ISO/dist` and `dist`. Set `GROOVEBOX_ISO_DIRS=/path/a:/path/b` to choose other search directories. Alternatively supply exactly five ISO paths after the device. The selected five must include a clearly named `*SIGNED*` or `*SECUREBOOT*` ISO to source the shared signed Limine boot payload. The script refuses non-removable targets, mounted or active-swap targets, a target containing the running root filesystem, source ISOs stored on the target, and anything short of two explicit confirmations.

## Validation boundary

- Focused source tests and shell syntax checks are run for this release.
- No ISO mastering, Qt GUI launch, Latitude physical boot, Secure Boot enrollment, or seven-partition physical USB write is claimed unless separately recorded in the validation report.
