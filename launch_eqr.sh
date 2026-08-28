#!/usr/bin/env bash
# Groovebox V1 — Linux/macOS launcher
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-}"
PYTHON="${PYTHON:-python3}"
if [[ ! -f "$ROOT/groovebox.py" ]]; then
  echo "groovebox.py not found next to launch_eqr.sh" >&2
  exit 1
fi
# Optional local venv
if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi
exec "$PYTHON" "$ROOT/launch_eqr.py" "$@"
