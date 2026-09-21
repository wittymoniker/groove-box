Groovebox BUILD_ISO v35.22d — Debian Qt WebEngine native runtime fix — 2026-09-21
Run from the extracted Groovebox root:
  sudo ./BUILD_ISO/RUN_ME_ZERO_STATE.sh
Expected final ISO:
  BUILD_ISO/dist/Groovebox-sOS-x86_64-YYYYMMDD-GAME-READY-v35.22.iso

Builder v35.22d adds the Debian 13 native runtime libraries required by the
PyQt6-WebEngine wheel (including NSPR/NSS) and audits QtWebEngineProcess/
libQt6WebEngine shared-library dependencies with ldd before packing.
The appliance/runtime release remains v35.22.
