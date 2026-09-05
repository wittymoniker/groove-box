#!/usr/bin/env bash
set -euo pipefail
# Groovebox Performance appliance helper for Raspberry Pi OS / Debian / Ubuntu.
# Run from the unpacked Groovebox directory. It installs OS playback/render
# dependencies, creates a local venv, and leaves the source tree user-owned.
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip ffmpeg mpv libportaudio2 libsndfile1
fi
"$PYTHON" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip wheel
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
cat > "$ROOT/run_performance_box.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
exec "$ROOT/.venv/bin/python" "$ROOT/run_groovebox.py" "$@"
EOF
chmod +x "$ROOT/run_performance_box.sh"
echo "Installed. Launch with: $ROOT/run_performance_box.sh"
