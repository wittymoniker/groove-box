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


FULL-GRAPH SCRIPT COMPATIBILITY (2026-09-09)
---------------------------------------------
This build carries graph_script_context.py and the full_graph_v1 runtime contract.
Seed/Instrument/Algorithm/Domain programs can share the same t/x/y/z graph context,
and the resulting named channels are consumed by audio, video/scenograph, and
generated-game paths. RAND PARAM uses a pre-evaluated row cache in realtime.
Canonical and heuristic/random writers can author the richer scripts while preserving
user-authored Instrument Scripts. Keep graph_script_context.py beside groovebox.py
on every platform/appliance install. See HELP_TEXT.md for the public variable list.
