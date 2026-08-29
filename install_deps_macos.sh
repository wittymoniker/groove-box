#!/usr/bin/env bash
# =============================================================================
# Groovebox dependency installer - macOS
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency (Homebrew + pip) and the
# ffmpeg codec suite, then symlinks ffmpeg/ffprobe into the codec lookup paths
# VideoSynthEngine checks (/bin when writable, else /usr/local/bin).
# =============================================================================
set -u

if [ "$(id -u)" -eq 0 ]; then
  echo "Do not run this installer as root; macOS python/brew are user-managed." >&2
  exit 4
fi

echo "==> Groovebox installer: macOS"
if ! command -v brew >/dev/null 2>&1; then
  echo "==> Homebrew missing — installing the official one-liner..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "==> brew python + ffmpeg (full codec suite)..."
brew install python ffmpeg || brew upgrade python ffmpeg

echo "==> pip dependencies (shared: host app + exported games)..."
PIP_DEPS="numpy scipy PyQt6 sounddevice Pillow"
python3 -m pip install --upgrade pip wheel
python3 -m pip install $PIP_DEPS

echo "==> Codec binaries into the resolver's lookup path ..."
FF=$(command -v ffmpeg || true)
FP=$(command -v ffprobe || true)
for pair in "ffmpeg|$FF" "ffprobe|$FP"; do
  name="${pair%%|*}"; path="${pair#*|}"
  if [ -n "$path" ]; then
    ln -sf "$path" "/bin/$name" 2>/dev/null || ln -sf "$path" "/usr/local/bin/$name" 2>/dev/null || true
  fi
done

echo "==> Verify:"
python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
command -v ffmpeg; command -v ffprobe
ffmpeg -hide_banner -encoders >/dev/null 2>&1 && echo "ffmpeg OK"
echo "==> Done."
echo "    Run the app:   python3 groovebox.py"
