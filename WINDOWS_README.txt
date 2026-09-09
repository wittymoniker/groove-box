MATHEMATICIAN'S GROOVEBOX ? WINDOWS README
===========================================

This package is cross-platform. On Windows, use the Windows launcher/build
scripts and let the auto-detection layer select Windows-native components.

QUICK START
-----------

1. Extract the ZIP to a normal writable folder, for example:

   C:\Users\YourName\Desktop\groovebox

2. Open PowerShell in the extracted Groovebox folder.

3. Install/provision Windows dependencies:

   powershell -ExecutionPolicy Bypass -File .\install_deps_windows.ps1

   If the package uses the BUILD_KIT dependency installer instead, run:

   powershell -ExecutionPolicy Bypass -File .\BUILD_KIT\install_dependencies_windows.ps1

4. Build the Windows-native accelerator:

   .\BUILD_KIT\build_windows.bat

   or:

   powershell -ExecutionPolicy Bypass -File .\BUILD_KIT\build_windows.ps1

5. Launch Groovebox:

   .\LAUNCH_GROOVEBOX_WINDOWS.bat


AUTO-DETECTION
--------------

The launcher auto-detects the current operating system and chooses only
compatible native artifacts.

Windows uses:
    groovebox_accel.dll
    Windows executables ending in .exe

macOS uses:
    libgroovebox_accel.dylib

Linux / sOS use:
    libgroovebox_accel.so

A Linux .so file is NOT a Windows DLL and should never be loaded by Windows.
The launcher is designed to ignore incompatible native artifacts instead of
attempting to load them.


WINDOWS C++ BUILD REQUIREMENTS
------------------------------

The Windows native accelerator needs a working C/C++ compiler.

Recommended:
    Microsoft Visual Studio Build Tools
    "Desktop development with C++"

Alternative:
    MinGW-w64

If the build script reports that no compiler is available, install one of the
above toolchains and rerun:

    .\BUILD_KIT\build_windows.bat

After a successful build, the launcher should detect the Windows-native
accelerator automatically.


PYTHON
------

If "py" works on your system:

    py groovebox.py

If not, try:

    python groovebox.py

Normally you should use the supplied Windows launcher instead:

    .\LAUNCH_GROOVEBOX_WINDOWS.bat


FFMPEG
------

Groovebox expects FFmpeg/FFprobe to be provisioned by the included Windows
dependency/setup scripts or available in the package-local bin directory.

Typical Windows files:

    bin\ffmpeg.exe
    bin\ffprobe.exe

If video/audio export reports FFmpeg missing, rerun:

    powershell -ExecutionPolicy Bypass -File .\install_deps_windows.ps1

Then confirm that ffmpeg.exe and ffprobe.exe are present in the expected local
bin folder or discoverable on PATH.


sCODE ON WINDOWS
----------------

The launcher distinguishes the portable sCode/Python layer from the native
sCode stage-0/bootstrap runtime.

A Linux sCode executable cannot be used as a Windows executable.

If this package does not yet contain a verified Windows-native stage-0 binary,
the launcher will report that clearly rather than trying to execute the Linux
bootstrap.

Expected Windows-native form is similar to:

    scode0.exe
    or
    scode-native-windows-x86_64.exe

When a genuine Windows stage-0 binary is present in the expected runtime path,
the auto-detection launcher will select it automatically.

Groovebox may still use its supported Python/native-accelerator fallback path
for functionality that does not strictly require stage-0 sCode.


COMMON WINDOWS ERRORS
---------------------

ERROR: libgroovebox.so cannot be loaded
    libgroovebox.so is a Linux shared object. Windows needs a .dll build.
    Use the Windows launcher and rebuild with the Windows build script.

ERROR: groovebox_accel.dll missing
    Run:
        .\BUILD_KIT\build_windows.bat

ERROR: no C++ compiler found
    Install Visual Studio Build Tools with Desktop development with C++,
    or install MinGW-w64, then rebuild.

ERROR: Python not found
    Install Python 3 and make sure either "py" or "python" works from
    PowerShell.

ERROR: FFmpeg not found
    Run the included Windows dependency provisioning script and verify that
    bin\ffmpeg.exe and bin\ffprobe.exe exist.

ERROR: Windows sCode stage-0 missing
    This means a genuine Windows-native sCode bootstrap executable is not
    currently bundled. Do not rename a Linux binary to .exe. A real Windows
    build is required.


RECOMMENDED WINDOWS COMMAND SEQUENCE
------------------------------------

From the extracted Groovebox directory:

    powershell -ExecutionPolicy Bypass -File .\install_deps_windows.ps1

    .\BUILD_KIT\build_windows.bat

    .\LAUNCH_GROOVEBOX_WINDOWS.bat


IMPORTANT
---------

Do not run Linux .so files or Linux sCode binaries directly on Windows.

Do not fix a platform mismatch by merely renaming:
    .so  -> .dll
or:
    Linux binary -> .exe

They must be genuinely compiled for Windows.

The supplied auto-detection launcher exists specifically to prevent this class
of platform mismatch and select the appropriate runtime/build path.


WINDOWS POWERSHELL COMPATIBILITY
--------------------------------
The included Windows PowerShell scripts are ASCII-safe so they work correctly
with Windows PowerShell 5.1 as well as newer PowerShell versions. This avoids
UTF-8 punctuation being misread as quotation marks and causing parser errors.
