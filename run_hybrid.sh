#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
mkdir -p "$ROOT/bin" "$ROOT/native"
unset PYTHONHOME PYTHONPATH PYTHONPYCACHEPREFIX || true

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

case "$(uname -s)" in
  Linux)
    INSTALLER="$ROOT/install_deps_linux.sh"
    NATIVE_LIBRARY="$ROOT/native/libgroovebox_accel.so"
    RUST_LIBRARY="$ROOT/native/libgroovebox_rust_accel.so"
    NATIVE_BUILDER="$ROOT/scripts/build_linux.sh"
    ;;
  Darwin)
    INSTALLER="$ROOT/install_deps_macos.sh"
    NATIVE_LIBRARY="$ROOT/native/libgroovebox_accel.dylib"
    RUST_LIBRARY="$ROOT/native/libgroovebox_rust_accel.dylib"
    NATIVE_BUILDER="$ROOT/scripts/build_macos.sh"
    ;;
  *) echo "[Groovebox] Use LAUNCH_GROOVEBOX_WINDOWS.bat on Windows." >&2; exit 2 ;;
esac

PYTHON_BOOT="${GROOVEBOX_PYTHON:-${PYTHON:-python3}}"
if [[ -z "${GROOVEBOX_PYTHON:-}${PYTHON:-}" && -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BOOT="$ROOT/.venv/bin/python"
fi
if ! command -v "$PYTHON_BOOT" >/dev/null 2>&1; then
  if [[ -n "${GROOVEBOX_PYTHON:-}${PYTHON:-}" ]]; then
    echo "[Groovebox] Requested Python is not usable: $PYTHON_BOOT" >&2
    exit 2
  fi
  echo "[Groovebox] Python missing; provisioning platform dependencies..." >&2
  bash "$INSTALLER" "${INSTALL_ARGS[@]}"
  PYTHON_BOOT="python3"
fi

if ! SELECTED="$("$PYTHON_BOOT" "$ROOT/scripts/ensure_runtime_dependencies.py")"; then
  echo "[Groovebox] Runtime import check needs platform dependency repair..." >&2
  bash "$INSTALLER" "${INSTALL_ARGS[@]}"
  SELECTED="$("$PYTHON_BOOT" "$ROOT/scripts/ensure_runtime_dependencies.py")"
fi
[[ -n "$SELECTED" && -x "$SELECTED" ]] || {
  echo "[Groovebox] Runtime checker did not return a usable Python path." >&2
  exit 2
}
PYTHON_BIN="$SELECTED"

"$PYTHON_BIN" "$ROOT/scripts/provision_first_launch.py"
"$PYTHON_BIN" "$ROOT/scripts/ensure_native_scode_stage0.py"
if [[ ! -s "$RUST_LIBRARY" || "${GROOVEBOX_REBUILD_NATIVE:-0}" == 1 ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/ensure_rust_toolchain.py" --install || echo "[Groovebox] WARNING: Rust setup failed; C++/NumPy fallback remains available." >&2
  "$PYTHON_BIN" "$ROOT/scripts/build_rust_accel.py" || echo "[Groovebox] WARNING: optional Rust build failed; continuing." >&2
fi
if [[ ! -s "$NATIVE_LIBRARY" || "${GROOVEBOX_REBUILD_NATIVE:-0}" == 1 ]]; then
  bash "$NATIVE_BUILDER" || echo "[Groovebox] WARNING: optional C++ build failed; Python fallback remains available." >&2
fi
export GROOVEBOX_RUNTIME_VERIFIED_PYTHON="$PYTHON_BIN"
exec "$PYTHON_BIN" "$ROOT/launch_groovebox.py" "${APP_ARGS[@]}"
