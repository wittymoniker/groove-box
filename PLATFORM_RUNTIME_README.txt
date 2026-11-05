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

## HF15 — Cross-platform support and deployment guide (2026-10-27)

### Supported launch paths

Use the launcher shipped with this source tree; do not run a Linux ELF bootstrap on another operating system.

| Environment | Preferred entry point | Notes |
|---|---|---|
| Windows 10/11 x64 | `LAUNCH_GROOVEBOX_WINDOWS.bat` | Uses the Windows dependency installer and Python launcher when available. Keep the project in a user-writable folder. |
| macOS Intel / Apple silicon | `LAUNCH_GROOVEBOX_MACOS.command` | Uses the host Python/runtime; native sCode bootstrap availability depends on the matching packaged build. |
| Fedora / other Linux desktop | `LAUNCH_GROOVEBOX_LINUX.sh` or `run_hybrid.sh` | Fedora RPM PyQt6 and PipeWire/WirePlumber can differ from pip-installed Qt; avoid mixing Qt stacks in one environment. |
| Groovebox appliance ISO / sOS | `BUILD_GROOVEBOX_APPLIANCE_ISO.sh` and the versioned `BUILD_ISO/` instructions | Build success, boot success, and media success are separate validation gates. |
| Android/mobile helpers | `launch_mobile.sh` | This is a helper path, not a claim of full desktop-feature parity on every phone/tablet. |

**Architecture boundary:** packaged bootstrap binaries and ISO artifacts are architecture-specific. A launcher existing in the source tree does not prove that every CPU architecture or OS release has a tested binary. Windows/macOS/Linux releases need native CI or physical-device testing before being described as fully certified.

### Audio and video startup

- Groovebox's real-time instrument playback uses the `sounddevice` / PortAudio path; media-player features use Qt Multimedia and the platform's media plugins/codecs. These are distinct runtime paths.
- At startup, device discovery can lag behind desktop login, especially with Fedora + PipeWire/WirePlumber. The HF14 bootstrap schedules a bounded, non-blocking probe and logs findings to `~/.local/state/groovebox/media-bootstrap.log` on Unix-like systems (Windows log paths depend on the user's environment and launcher).
- A detected device is not proof that it opened successfully or produced sound. Test playback at a safe volume and select an explicit endpoint if the OS default is not the intended device. Current routing should not be described as synchronized playback to every output unless a true fan-out implementation is present.
- Video playback requires `PyQt6.QtMultimedia`, a working Qt multimedia backend and supported codecs. `PyQt6.QtWebEngineWidgets` is optional and is not the video-player backend.
- For a diagnostic report, run `python scripts/diagnose_platform.py`; to save a report, run `python scripts/diagnose_platform.py --json groovebox-platform-report.json`. The script is read-only and does not install packages or change audio routing.

### Laptop portability checklist

Use this checklist for Dell Latitude, Acer Nitro, and other laptops; avoid hard-coding a specific sound-card number, GPU, camera path, or output name.

1. Confirm the laptop's OS, CPU architecture, desktop session, and Python executable.
2. Run the platform diagnostic and check that `PyQt6.QtMultimedia` and `sounddevice` import in the same interpreter used by the launcher.
3. On Linux, inspect PipeWire/WirePlumber (`wpctl status`), PulseAudio compatibility (`pactl list short sinks`), and ALSA (`aplay -l`) where those tools exist. Prefer the user's desktop default first; treat direct ALSA hardware endpoints as fallback diagnostics, not universal defaults.
4. Check built-in speakers, headphone jack, HDMI/USB audio, Bluetooth, internal microphone, USB microphone, camera, and external display separately when available. Devices may appear/disappear while docking or reconnecting.
5. Keep audio discovery off the real-time audio callback and off the GUI's blocking startup path. Re-scan only through a bounded asynchronous operation and surface errors instead of silently swallowing them.
6. Validate an ISO in stages: builder/verifier tests; ISO file integrity; boot in a VM; boot on physical hardware; then test audio/video after login. A successful build or VM boot does not establish physical audio/video compatibility.

### ISO builder preflight and release discipline

Before publishing an ISO, run the project's documented verifier(s) from `BUILD_ISO/`, confirm the root source and `app-overlay-v35.22zz/` copies of any overlay-managed runtime files match, then check the generated ISO's checksum. Test the ISO against the actual target boot mode (UEFI/Legacy as supported), graphics mode, network, storage, and media devices. Do not copy host-specific device names or runtime logs into the release.

### Reporting a cross-platform defect

Attach the diagnostic JSON plus the latest session log. Include OS/version, CPU architecture, exact launcher (`run_hybrid.sh`, Windows BAT, macOS command, or ISO), whether the main window appeared, whether the player window appeared, selected output, and whether export-to-WAV works when live playback does not. Remove personal paths or device names before sharing if desired.



## HF16 — media diagnostics
Run `python scripts/diagnose_platform.py --json groovebox-platform-report.json` with the same interpreter as the launcher. The report includes PortAudio outputs, Qt Multimedia audio/camera enumeration when Qt can initialize, and OS-specific service/tool checks. This is read-only and does not prove playback. Windows install now warns separately when Qt Multimedia imports fail. See README.md and HELP_TEXT.md for the release gate and platform-specific troubleshooting.

HF17 audio-device recovery (Linux): run ./run_hybrid.sh to invoke OS-level audio/media dependency provisioning, then run scripts/diagnose_platform.py with the same interpreter as the launcher. The report captures PortAudio host APIs, exact enumeration errors, and PipeWire/WirePlumber/Pulse status. Logs: ~/.local/state/groovebox/media-bootstrap.log. Empty devices cannot be solved by a Python-only package if the OS session or kernel exposes no endpoints; verify on physical hardware.
