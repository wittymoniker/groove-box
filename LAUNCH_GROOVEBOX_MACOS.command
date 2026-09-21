#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "[Groovebox] macOS launcher - runtime verification/provisioning"
if ! command -v python3 >/dev/null 2>&1; then
  chmod +x "$ROOT/install_deps_macos.sh"
  "$ROOT/install_deps_macos.sh"
fi
if ! SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py")"; then
  chmod +x "$ROOT/install_deps_macos.sh"
  "$ROOT/install_deps_macos.sh"
  SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py")"
fi
PYTHON_BIN="$SELECTED"
"$PYTHON_BIN" "$ROOT/scripts/provision_first_launch.py"
"$PYTHON_BIN" "$ROOT/sCode/scripts/ensure-stage0.py" >/dev/null
"$PYTHON_BIN" "$ROOT/scripts/ensure_native_scode_stage0.py"
exec "$PYTHON_BIN" "$ROOT/launch_groovebox.py" "$@"
