Groovebox BUILD_ISO v35.22v — recovery-verifier + final-stamp sync — 2026-09-22

Run from the extracted Groovebox root:
  sudo ./BUILD_ISO/RUN_ME_ZERO_STATE.sh

Expected final ISO:
  BUILD_ISO/dist/Groovebox-sOS-x86_64-YYYYMMDD-GAME-READY-v35.22v.iso

v35.22v keeps the strict v35.22u udev + seatd + Labwc + Qt Wayland runtime.
It fixes the stale v32w recovery-menu verifier that rejected the current root-owned
recovery menu, and makes the final initramfs stamper bind its own BUILD_ISO path.
The appliance/runtime family remains v35.22.
