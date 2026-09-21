#!/usr/bin/env bash
# Groovebox complete macOS desktop runtime installer (v35.22b).
set -euo pipefail
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not run this installer as root; Homebrew/Python are user-managed." >&2
  exit 4
fi
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/bin"
echo "==> Groovebox installer: macOS"
if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
brew install python ffmpeg portaudio || brew upgrade python ffmpeg portaudio || true
SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py" --force-install)"
"$SELECTED" "$ROOT/scripts/provision_first_launch.py"
echo "==> Verify complete runtime:"
"$SELECTED" -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtWebEngineWidgets; print('Groovebox Python/browser runtime OK')"
"$SELECTED" "$ROOT/scripts/ensure_native_scode_stage0.py"
echo "==> Done. Launch with LAUNCH_GROOVEBOX_MACOS.command"
