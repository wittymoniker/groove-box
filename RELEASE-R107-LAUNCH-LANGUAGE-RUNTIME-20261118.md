# R107 — launch integrity and language runtime completion

## Launch-path corrections

- `run_hybrid.sh`, the Linux/macOS shared launcher, Windows launcher, sOS launcher, `launch_groovebox.py`, and `run_groovebox.py` all establish no-bytecode behavior before project modules are imported.
- The ISO finalizer no longer uses `compileall` against the deployed application tree. It compiles source in memory, avoiding `.pyc`/`__pycache__` writes in the immutable image.
- The normal GUI runner claims a Qt local-server endpoint before constructing the main window. A second invocation sends `ACTIVATE`, raises the first window, and exits. Helper/game re-entry is dispatched before this guard and remains independent.
- The Apps & Scripts list excludes the product's own desktop launchers, including the Linux and Flatpak desktop IDs.

## Language runtime payload

The sOS runtime image now prepares:

- C and C++: Debian `build-essential`.
- Go: Debian `golang-go`.
- Julia 1.11.7: official x86_64 GNU/Linux archive selected from Julia's official versions manifest and verified against its published SHA-256.
- JuliaCall/PythonCall: installed and prewarmed during image construction; the sOS launcher sets the bundled Julia executable/project and offline package mode.
- LuaJIT: `lupa` with the LuaJIT backend, validated during image construction and final rootfs verification.
- Python and Shell: existing CPython/sCode runtime and `/bin/sh`.
- Rust: full host compiler/cargo/sysroot stored as a compressed ISO payload and extracted to writable user data on first use. The already-built native Rust accelerator remains immediately available.

The ISO build intentionally fails if the required language-runtime preflight or Julia source smoke test fails.

## Focused tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest -q \\
  test_r107_launch_hardening_20261118.py \\
  test_export_recovery_dependency_contract_20261118.py \\
  test_groovebox_intelligence_r105.py \\
  test_multidim_instrument_rename_20261118.py
```

## Validation boundary

Source-level tests and shell syntax checks do not constitute a completed ISO build, PyQt GUI launch, JuliaCall execution inside the finished rootfs, or physical hardware boot. Those require the documented full builder and a target machine. Do not mark those stages PASS until run.
