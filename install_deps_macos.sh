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
if ! xcrun --find clang >/dev/null 2>&1; then
  echo "==> Installing Apple Command Line Tools for C++/Rust linker support"
  xcode-select --install || true
fi
brew install python ffmpeg portaudio glm || brew upgrade python ffmpeg portaudio glm || true
SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py" --force-install)"
"$SELECTED" "$ROOT/scripts/provision_first_launch.py"
echo "==> Verify complete runtime:"
"$SELECTED" -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtMultimedia, PyQt6.QtMultimediaWidgets; print('Groovebox required Python/Qt runtime OK')"
"$SELECTED" - <<'PY'
import subprocess, sys
try:
    subprocess.run([sys.executable, "-c", "import PyQt6.QtWebEngineWidgets"],
                   check=True, timeout=30)
except (OSError, subprocess.SubprocessError) as exc:
    print(f"[runtime] WARNING: optional browser probe failed: {exc}", file=sys.stderr)
PY
"$SELECTED" "$ROOT/scripts/ensure_native_scode_stage0.py"
"$SELECTED" "$ROOT/scripts/ensure_rust_toolchain.py" --install || echo "[runtime] WARNING: optional Rust toolchain unavailable." >&2
"$SELECTED" "$ROOT/scripts/build_rust_accel.py" || echo "[runtime] WARNING: optional Rust build failed; fallback remains available." >&2
echo "==> Done. Launch with LAUNCH_GROOVEBOX_MACOS.command"
