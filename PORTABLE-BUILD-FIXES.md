# Portable ISO and Executable Builder Fixes

This source revision addresses the supplied Fedora traceback and related
host-configuration assumptions found by static inspection. It preserves the
working GUI and runtime audio policy. No tests, application run, or executable/
ISO build were performed for this revision.

## Failure trace

The R23f verifier runs the root audio fixture with `python3 -S`. Its analog
assertion expected fake device index 1 but received fake PipeWire index 0.
`CalledProcessError` reports that child assertion, not a separate Python
installation failure. The selector tries the aggregate route before direct
hardware; the old fixture did not isolate that route or its background worker.

The revised fixture isolates route state/preparation, subprocesses, device rows,
HDMI state, proven-speaker selection, and boot/volume state files. It asserts
analog fallback without an aggregate sink, then PipeWire/default selection with
an aggregate sink. Speaker unmute, Auto-Mute and UCM assertions remain active.
The duplicate BUILD_ISO fixture delegates to the root fixture. The enclosing
verifier still fails on errors and has a 30-second child timeout.

## Other portable source-check fixes

- **Personal cache:** remove `/home/eski/python_cache_...` from the zt verifier.
- **Writable source:** thirteen host verifiers and both active release runners
  use in-memory source compilation, not write-to-source bytecode checks. Syntax
  errors still fail. Guest-runtime bytecode generation is unchanged.
- **Working directory:** seven project-verifier defaults and three BUILD_ISO
  helper defaults derive their roots from `__file__`.
- **Current overlay:** the standalone rollout contract defaults to active zz,
  not frozen zt.
- **Module lookup:** standalone shared-context and spatial-synth checks add
  the project root before importing application modules.
- **HDMI false negative:** the standalone R23s check now inspects the digital
  mixer branch structurally instead of rejecting spaces in an equivalent tuple.

These additional items are concrete conditional/standalone hazards, not proof
that each would fail on this particular Fedora machine. Literal/AST tracing
did not execute the verifier suite or establish that every later stage passes.

## Executable builder

BUILD_KIT now clears inherited Python home/path/cache overrides for child
commands and uses `build_executable/cache/` for pip and PyInstaller caches.
It diagnoses non-writable outputs and stale/incomplete venvs without changing
ownership or deleting a venv. Doctor checks use the actual project build venv.

Source policy and compilation use the ISO's shared runtime inventory, and
invalid source fails immediately rather than being silently skipped. Required
host stage-0 repair precedes its strict ABI gate, separately from optional
Rust/C++ accelerators. Packaging uses the exact codec pair that was validated.
One-file archive inspection no longer embeds a fragile nested newline escape.
PowerShell prefers the build venv and returns the native process's exit code.

No runtime modules changed in this revision, so the ISO overlay and executable
inventory remain the same source payload. This does not verify dependency
compatibility on every distribution, Windows host, or macOS host.

## Example commands

Stop the old builder before replacing files. Extract the full revised archive
into a new user-owned folder; do not mix an old fixture with a new runner.
Run normally rather than through sudo; package installers request elevation.

Fedora/Linux executable:

```bash
bash BUILD_KIT/install_dependencies_linux.sh
bash BUILD_KIT/build_linux.sh --console
```

Windows EXE, from PowerShell on Windows:

```powershell
.\BUILD_KIT\install_dependencies_windows.ps1
.\BUILD_KIT\build_windows.ps1 -Console
```

Add `-OneFile` to the last command for a single-file EXE. Normal output is
`dist/MathematiciansGroovebox/MathematiciansGroovebox.exe`; single-file output
is `dist/MathematiciansGroovebox.exe`. Fedora builds a Linux executable, not a
Windows EXE; no cross-compilation support is introduced here.

ISO on Linux:

```bash
bash RUN_ME_ZERO_STATE.sh
```

Keep the newest `BUILD_ISO/logs/iso-build-*.log` if another stage fails. Completed
EXE/ISO builds, boot behavior, and laptop installation remain unverified.
