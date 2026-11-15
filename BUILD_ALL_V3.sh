#!/usr/bin/env bash
# Groovebox V3 — run the builds this tree supports.
# ISO supports Debian/Ubuntu or Fedora hosts (root required for the appliance stages). App executable uses BUILD_KIT.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# R64: every top-level BUILD invocation imports overlay-only sources and refreshes
# the active ISO runtime payload before any compilation or packaging stage.
if [[ "${GROOVEBOX_OVERLAY_SYNC_DONE:-0}" != 1 ]]; then
  bash "$ROOT/BUILD_ISO/RUN_ME_ZERO_STATE.sh" --prepare-overlay
  export GROOVEBOX_OVERLAY_SYNC_DONE=1
fi

echo "=== 1/3 syntax + fractal import ==="
python3 -m py_compile groovebox.py run_groovebox.py launch_groovebox.py groovebox_v3_runtime.py
PYTHONPATH="$ROOT/groovebox_fractal" python3 -c "import groovebox_fractal; print('fractal OK')"

echo "=== 2/3 application executable (Linux) ==="
if [[ -x BUILD_KIT/build_linux.sh ]]; then
  chmod +x BUILD_KIT/*.sh
  if [[ "${SKIP_APP_BUILD:-0}" != 1 ]]; then
    ./BUILD_KIT/install_dependencies_linux.sh
    ./BUILD_KIT/build_linux.sh --console
  fi
else
  echo "FAIL: BUILD_KIT/build_linux.sh is missing" >&2
  exit 1
fi

echo "=== 3/3 appliance ISO ==="
if [[ "${SKIP_ISO:-0}" == 1 ]]; then
  echo "SKIP_ISO=1 — not building ISO"
elif [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL: ISO build needs root. Re-run: sudo $0" >&2
  echo "Or: sudo ./BUILD_ISO/RUN_ME_ZERO_STATE.sh" >&2
  exit 2
else
  exec ./BUILD_ISO/RUN_ME_ZERO_STATE.sh
fi

echo "=== done ==="
