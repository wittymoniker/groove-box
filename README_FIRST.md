# Mathematician's Groovebox + sCode + sOS Universal Redistributable 0.4

This bundle contains:

- `Groovebox/` — latest working Groovebox migration/reference tree, including the
  author-number-symbol UI patch and Mechanical Phase 0.3 reverse-decode outputs.
- `sCode/` — sCode parser/compiler, sIR/sBIN translators, libraries, native C++
  runtime source, sAssistant workbench, and the existing Linux native runtime.
- `BUILD_COMPILER/` — native C++ runtime/compiler build scripts for:
  - Linux: GCC/g++
  - macOS: Apple clang++
  - Windows: MSVC or MinGW-w64
- `sOS/` — sOS 0.3 Linux appliance source.
- `sOS_COMPILER/` — cross-platform sOS source compiler/validator/planner.
- top-level run/compile launchers for Windows, macOS, and Linux.

## sCode compiler

The Python parser/compiler layer is portable to Windows/macOS/Linux with Python 3.

The native C++ runtime source is `sCode/native/scode_native.cpp`.

Build it:

Linux:
```bash
./BUILD_COMPILER/build_linux.sh
```

macOS:
```bash
./BUILD_COMPILER/build_macos.sh
```

Windows PowerShell:
```powershell
.\BUILD_COMPILER\build_windows.ps1
```

Then compile an sCode file with the top-level `COMPILE_SCODE_*` launcher.

## Groovebox

Current redistributable Groovebox is still migration/reference-capable rather
than a certified pure-sCode release. The launcher therefore uses the existing
bridge/reference path today while the sCode compiler/runtime is included beside it.

## sOS compiler

The sOS **host compiler** works on Windows, macOS, and Linux:

Linux:
```bash
./COMPILE_SOS_LINUX.sh
```

macOS:
```bash
./COMPILE_SOS_MAC.command
```

Windows:
```bat
COMPILE_SOS_WINDOWS.bat
```

It validates `sOS/scode/system.sC`, hashes the sOS source tree, and emits:

```text
build_sos/sos.sir.json
build_sos/SHA256SUMS.json
build_sos/sOS-source-payload.zip
```

The current sOS target is Linux. Building the actual Linux root filesystem or
ISO therefore requires a Linux host:

```bash
./COMPILE_SOS_LINUX.sh --build-rootfs
./COMPILE_SOS_LINUX.sh --build-iso
```

## Important status

- Linux native sCode runtime: included from the existing tested ecosystem.
- Linux native runtime rebuild path: tested syntactically in this packaging environment.
- Python sCode compiler/parser: included and compile-checked.
- sOS compiler/validator: executed successfully in this packaging environment.
- Windows/macOS native runtime build scripts: provided from the same C++ source,
  but cannot be truthfully called tested on Windows/macOS from this Linux session.
- sOS is a Linux target; Windows/macOS compatibility here means they can host the
  sCode compiler and sOS planner/compiler, not boot sOS natively.
- Groovebox is not yet certified as 100% pure sCode; Python remains in the
  redistributable as the mature reference/bridge during migration.
