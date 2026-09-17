# Mathematician's Groovebox + sCode Unified Compatibility Release

This release packages Groovebox together with the unified native sCode ABI-9 stage-0/runtime source for the primary 64-bit desktop targets:

- Linux x86-64
- Linux ARM64 / AArch64
- Windows x86-64
- Windows ARM64
- macOS Intel x86-64
- macOS Apple Silicon ARM64

## Groovebox

The `groovebox/` directory contains the complete Groovebox application. Its bundled `groovebox/sCode/` tree is the same unified sCode distribution shipped alongside it.

Windows: run `groovebox/LAUNCH_GROOVEBOX_WINDOWS.bat`.
macOS: run `groovebox/LAUNCH_GROOVEBOX_MACOS.command`.
Linux: run `groovebox/launch_desktop.sh`.

The launch path provisions and verifies the host-native sCode stage-0 before Groovebox starts. A valid stage-0 probe reports `scode_stage0_native=1` and `scode_optimizer_abi=9`.

## Standalone sCode

The top-level `sCode/` directory is the same unified sCode distribution for direct use. Run `sCode/run-scode --probe` on Linux/macOS or `sCode\\run-scode.cmd --probe` on Windows.

## Architecture note

The source package is cross-platform. Native binaries are host-specific: a PE executable cannot run on macOS/Linux and a Mach-O/ELF binary cannot run on Windows. For targets without a bundled prebuilt stage-0, the included build/provision script compiles the portable C stage-0 on that target and execution-probes it before use.

## Appliance ISO

The companion ISO is an x86-64 PC bootable sOS/Groovebox appliance image. It contains this updated Groovebox tree and unified sCode source/runtime payload in its initramfs. The ISO itself is not a universal firmware image for ARM Macs or Windows-on-ARM devices; those platforms use the source package above. This distinction prevents falsely claiming one x86 boot image can directly boot every CPU/firmware family.
