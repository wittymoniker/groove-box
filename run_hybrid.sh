#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/bin" "$ROOT/native"

# V35.22e_FEDORA_QT_ABI_ISOLATION: Fedora's RPM PyQt6/WebEngine must not
# be shadowed by old pip wheels under ~/.local or an arbitrary PYTHONPATH.
if [[ -f /etc/os-release ]] && grep -Eqi '^ID=("?fedora"?)$|^ID_LIKE=.*fedora' /etc/os-release; then
  export PYTHONNOUSERSITE=1
  unset PYTHONPATH || true
fi

# V35.22d_RUNTIME_REPAIR: every launch verifies one complete desktop runtime.
# dnf recovery flags are consumed by the installer and never forwarded into the
# Groovebox application argument parser.
INSTALL_ARGS=()
APP_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --allowerasing|--skip-broken) INSTALL_ARGS+=("$arg") ;;
    *) APP_ARGS+=("$arg") ;;
  esac
done

PYTHON_BOOT="${PYTHON:-python3}"
if ! command -v "$PYTHON_BOOT" >/dev/null 2>&1; then
  echo "[Groovebox] Python missing; provisioning Linux dependencies..." >&2
  bash "$ROOT/install_deps_linux.sh" "${INSTALL_ARGS[@]}"
  PYTHON_BOOT="python3"
fi

if ! SELECTED="$($PYTHON_BOOT "$ROOT/scripts/ensure_runtime_dependencies.py")"; then
  echo "[Groovebox] Runtime import check needs native/system repair; running Linux installer..." >&2
  bash "$ROOT/install_deps_linux.sh" "${INSTALL_ARGS[@]}"
  SELECTED="$($PYTHON_BOOT "$ROOT/scripts/ensure_runtime_dependencies.py")"
fi
PYTHON_BIN="$SELECTED"

"$PYTHON_BIN" "$ROOT/scripts/provision_first_launch.py"
"$PYTHON_BIN" "$ROOT/scripts/ensure_native_scode_stage0.py"
if [[ ! -f "$ROOT/native/libgroovebox_accel.so" && ! -f "$ROOT/native/libgroovebox_accel.dylib" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then bash "$ROOT/scripts/build_macos.sh" || true; else bash "$ROOT/scripts/build_linux.sh" || true; fi
fi
exec "$PYTHON_BIN" "$ROOT/run_groovebox.py" "${APP_ARGS[@]}"
