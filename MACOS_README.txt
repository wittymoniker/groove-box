MATHEMATICIAN'S GROOVEBOX — macOS README
=========================================

This package is cross-platform. On macOS, use the macOS launcher/build scripts
and let the auto-detection layer select macOS-native components.

QUICK START
-----------

1. Extract the ZIP to a normal writable folder.

2. Open Terminal in the extracted Groovebox folder.

3. Install/provision macOS dependencies:

   bash ./install_deps_macos.sh

4. Build the macOS-native accelerator:

   bash ./BUILD_KIT/build_macos.sh

   If a dedicated macOS build script is not present, use the generic build
   helper documented in BUILD_KIT/README_BUILD.txt.

5. Launch Groovebox:

   bash ./LAUNCH_GROOVEBOX_MACOS.command

   or double-click LAUNCH_GROOVEBOX_MACOS.command after making it executable.


AUTO-DETECTION
--------------

The launcher auto-detects the current operating system and chooses only
compatible native artifacts.

macOS uses:
    libgroovebox_accel.dylib

Windows uses:
    groovebox_accel.dll

Linux / sOS use:
    libgroovebox_accel.so

A Linux .so file is not a macOS dynamic library and should not be loaded on
macOS. The launcher is designed to ignore incompatible native artifacts.


MACOS BUILD REQUIREMENTS
------------------------

Recommended compiler/toolchain:
    Xcode Command Line Tools

Install with:

    xcode-select --install

Then rerun the macOS native build script.


PYTHON
------

Typical commands:

    python3 groovebox.py

Normally use the supplied launcher:

    bash ./LAUNCH_GROOVEBOX_MACOS.command


FFMPEG
------

Run the included macOS dependency installer:

    bash ./install_deps_macos.sh

Then verify that ffmpeg and ffprobe are available either in the package-local
bin folder or on PATH.

Typical checks:

    ffmpeg -version
    ffprobe -version


sCODE ON MACOS
--------------

The launcher distinguishes portable sCode/Python code from the native sCode
stage-0/bootstrap runtime.

A Linux sCode executable cannot be used as a macOS executable.

If this package does not contain a verified macOS-native stage-0 binary, the
launcher will report that clearly rather than attempting to run a Linux binary.

Expected native forms may include architecture-specific binaries such as:
    scode0-macos-x86_64
    scode0-macos-arm64

When a valid macOS stage-0 binary is present in the expected runtime path, the
auto-detection launcher will select it automatically.


COMMON MACOS ERRORS
-------------------

ERROR: libgroovebox_accel.dylib missing
    Install Xcode Command Line Tools and rebuild the native accelerator.

ERROR: permission denied when launching .command or .sh
    Run:
        chmod +x LAUNCH_GROOVEBOX_MACOS.command
        chmod +x BUILD_KIT/*.sh
        chmod +x install_deps_macos.sh

ERROR: "cannot be opened because the developer cannot be verified"
    macOS Gatekeeper may quarantine downloaded scripts/binaries. Review the
    file source and use the appropriate macOS security controls before running.

ERROR: FFmpeg not found
    Rerun:
        bash ./install_deps_macos.sh

ERROR: macOS sCode stage-0 missing
    A genuine macOS-native bootstrap is required. Do not rename a Linux binary.


RECOMMENDED MACOS COMMAND SEQUENCE
----------------------------------

    bash ./install_deps_macos.sh

    bash ./BUILD_KIT/build_macos.sh

    bash ./LAUNCH_GROOVEBOX_MACOS.command


IMPORTANT
---------

Do not attempt to use Linux .so files on macOS.

Do not fix a platform mismatch by renaming:
    .so -> .dylib

The native library must be genuinely compiled for macOS.
