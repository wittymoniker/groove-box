# Native sCode stage-0 — Windows + macOS

Groovebox requires sCode ABI-9 planning before the GUI starts.

- Windows x86-64 now ships a genuine native PE32+ `sCode/bootstrap/windows-x86_64/scode0.exe`. It is a CRT-free first-stage bootstrap, so it does not depend on Python or a compiler to execute.
- macOS Intel and Apple Silicon build a genuine native Mach-O `scode0` automatically on first launch from `sCode/bootstrap_source/scode0_groovebox.c` using the host Apple clang toolchain, then ad-hoc sign and ABI-probe it.
- If the Windows binary is removed/damaged, `scripts/build_scode_stage0_windows.ps1` can rebuild it with Visual C++ Build Tools, installing those through winget if necessary.
- No Linux ELF is copied or executed on Windows/macOS.
- No Python/NumPy fallback satisfies the stage-0 requirement.

The compact bootstrap implements exactly the sCode Groovebox optimizer surface required at stage 0. Its ABI-9 numeric output was parity-tested against the existing Linux stage-0 over 500 randomized planner states before packaging.
