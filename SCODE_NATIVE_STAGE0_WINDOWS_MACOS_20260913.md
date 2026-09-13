# Native sCode stage-0 on Windows and macOS

Groovebox now treats sCode stage-0 as mandatory on Windows, macOS, and Linux.
There is no Python/NumPy fallback for the required sCode optimizer runtime.

Expected installed paths:
- Windows x86-64: `sCode/bootstrap/windows-x86_64/scode0.exe` (PE)
- macOS Intel: `sCode/bootstrap/macos-x86_64/scode0` (Mach-O)
- macOS Apple Silicon: `sCode/bootstrap/macos-arm64/scode0` (Mach-O)
- Linux x86-64: `sCode/bootstrap/linux-x86_64/scode0` (ELF)

First-launch provisioning searches the matching `sCode/bootstrap_packages/...` directory,
then an optional `GROOVEBOX_SCODE_STAGE0_SOURCE`, then optional URL/SHA variables.
Every candidate must execute and produce `scode_optimizer_abi=9` before Groovebox opens.

## Important release status
The supplied source archive contains a verified Linux x86-64 stage-0 binary, but it does
not contain genuine Windows PE or macOS Mach-O stage-0 binaries. The launchers are now
correct and strict, but those native artifacts must be built/published separately before
Windows/macOS can truthfully be called complete native-stage-0 releases.
