#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[Groovebox] macOS launcher - automatic first-run provisioning"

needs_provision=0
command -v python3 >/dev/null 2>&1 || needs_provision=1
[ -x "bin/ffmpeg" ] || needs_provision=1
[ -x "bin/ffprobe" ] || needs_provision=1
[ -f ".groovebox_provisioned_macos" ] || needs_provision=1

if [ "$needs_provision" -eq 1 ]; then
  echo "[Groovebox] Provisioning macOS dependencies automatically..."
  chmod +x ./install_deps_macos.sh
  ./install_deps_macos.sh
  "${PYTHON:-python3}" ./scripts/provision_first_launch.py
  : > .groovebox_provisioned_macos
fi

exec "${PYTHON:-python3}" launch_groovebox.py "$@"
