#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/launch_desktop.sh" ]]; then
  exec bash "$ROOT/launch_desktop.sh" "$@"
elif [[ -f "$ROOT/launch_groovebox.py" ]]; then
  exec python3 "$ROOT/launch_groovebox.py" "$@"
else
  exec python3 "$ROOT/run_groovebox.py" "$@"
fi
