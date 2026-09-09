Groovebox platform-native launcher
==================================
Use the launcher matching the host shell:
  Windows: LAUNCH_GROOVEBOX_WINDOWS.bat
  macOS:   LAUNCH_GROOVEBOX_MACOS.command
  Linux:   LAUNCH_GROOVEBOX_LINUX.sh
  sOS:     LAUNCH_GROOVEBOX_SOS.sh

All wrappers call launch_groovebox.py. It autodetects OS/CPU, chooses only the matching
accelerator (.dll/.dylib/.so), optionally builds it from cpp/groovebox_accel.cpp, and
selects only the matching sCode stage-0 bootstrap.

Verified sCode bootstrap layout:
  sCode/bootstrap/windows-x86_64/scode0.exe
  sCode/bootstrap/macos-x86_64/scode0
  sCode/bootstrap/macos-arm64/scode0
  sCode/bootstrap/linux-x86_64/scode0

IMPORTANT: the current source archive contains the verified Linux x86_64 stage-0 only.
The launcher therefore refuses to substitute that ELF executable on Windows or macOS.
Add verified Windows/macOS stage-0 builds at the paths above and the same launcher will
autodetect them without code changes.
