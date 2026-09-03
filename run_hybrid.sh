#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/bin" "$ROOT/native"
python3 "$ROOT/scripts/provision_first_launch.py" || true
if [[ ! -f "$ROOT/native/libgroovebox_accel.so" && ! -f "$ROOT/native/libgroovebox_accel.dylib" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then "$ROOT/scripts/build_macos.sh" || true; else "$ROOT/scripts/build_linux.sh" || true; fi
fi
exec python3 "$ROOT/groovebox.py" "$@"
