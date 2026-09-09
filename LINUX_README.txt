MATHEMATICIAN'S GROOVEBOX — LINUX README
=========================================

This package is cross-platform. On Linux, use the Linux launcher/build scripts
and let the auto-detection layer select Linux-native components.

QUICK START
-----------

1. Extract the ZIP to a normal writable folder.

2. Open a terminal in the extracted Groovebox folder.

3. Install/provision Linux dependencies.

   Fedora:
       ./install_deps_linux.sh --fedora

   Ubuntu/Debian:
       ./install_deps_linux.sh --ubuntu

4. Build the Linux-native accelerator:

       ./BUILD_KIT/build_linux.sh

   If needed:
       bash ./BUILD_KIT/build_linux.sh

5. Launch Groovebox:

       ./LAUNCH_GROOVEBOX_LINUX.sh

   or:
       bash ./LAUNCH_GROOVEBOX_LINUX.sh


AUTO-DETECTION
--------------

The launcher auto-detects the current operating system and chooses only
compatible native artifacts.

Linux / sOS use:
    libgroovebox_accel.so

macOS uses:
    libgroovebox_accel.dylib

Windows uses:
    groovebox_accel.dll

The launcher should not attempt to load Windows DLLs or macOS dylibs on Linux.


LINUX BUILD REQUIREMENTS
------------------------

Typical compiler/toolchain requirements:
    gcc / g++
    or
    clang / clang++

Fedora examples:
    sudo dnf install gcc gcc-c++ make

Ubuntu/Debian examples:
    sudo apt install build-essential

Then rerun:
    ./BUILD_KIT/build_linux.sh


PYTHON
------

Typical commands:

    python3 groovebox.py

Normally use the supplied launcher:

    ./LAUNCH_GROOVEBOX_LINUX.sh


FFMPEG
------

Use the included provisioning script:

Fedora:
    ./install_deps_linux.sh --fedora

Ubuntu/Debian:
    ./install_deps_linux.sh --ubuntu

Then verify:

    ffmpeg -version
    ffprobe -version

Groovebox may also use package-local FFmpeg binaries when provided.


sCODE ON LINUX
--------------

Linux is currently the most complete native sCode host in this package.

The launcher should select the verified Linux stage-0/native runtime when the
host architecture matches the bundled binary.

Typical Linux runtime names may include:
    scode0
    scode-native
    scode-native-linux-x86_64

A binary compiled for a different CPU architecture must not be used directly.
The auto-detection layer should reject incompatible architecture/runtime pairs.


sOS
---

sOS is Linux-based in the current project architecture.

When running inside sOS, the launcher should prefer the sOS-specific path when
detected and otherwise use the compatible Linux native runtime path.

The sOS compiler/planner can be hosted from Windows, macOS, or Linux, but the
current sOS target itself uses a Linux kernel/runtime.


COMMON LINUX ERRORS
-------------------

ERROR: libgroovebox_accel.so missing
    Install a compiler/toolchain and rerun:
        ./BUILD_KIT/build_linux.sh

ERROR: permission denied
    Run:
        chmod +x LAUNCH_GROOVEBOX_LINUX.sh
        chmod +x BUILD_KIT/*.sh
        chmod +x install_deps_linux.sh

ERROR: shared library cannot be opened
    Confirm the library was compiled for the same architecture and that the
    launcher is using the package-local native path.

ERROR: FFmpeg not found
    Rerun the appropriate Linux dependency provisioning command.

ERROR: wrong sCode architecture
    Use a Linux stage-0/runtime compiled for the current CPU architecture.


RECOMMENDED LINUX COMMAND SEQUENCE
----------------------------------

Fedora:
    ./install_deps_linux.sh --fedora
    ./BUILD_KIT/build_linux.sh
    ./LAUNCH_GROOVEBOX_LINUX.sh

Ubuntu/Debian:
    ./install_deps_linux.sh --ubuntu
    ./BUILD_KIT/build_linux.sh
    ./LAUNCH_GROOVEBOX_LINUX.sh


IMPORTANT
---------

Do not use Windows .dll or macOS .dylib native accelerator builds on Linux.

A native artifact must be genuinely compiled for the target OS and CPU.
