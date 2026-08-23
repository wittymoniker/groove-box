#!/usr/bin/env bash
# Cross-platform package launcher for Linux.
# Always launches the groovebox.py bundled beside this script.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TARGET_SCRIPT="${SCRIPT_DIR}/groovebox.py"

CYAN=$'\033[0;36m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
NC=$'\033[0m'

fail() {
    echo "${RED}[!] $*${NC}" >&2
    exit 1
}

printf '%s\n' "${CYAN}==============================================================${NC}"
printf '%s\n' "${CYAN}                 Groovebox Linux Launcher                    ${NC}"
printf '%s\n' "${CYAN}==============================================================${NC}"

# Resolve everything from the launcher location, not from $PWD or PATH.
[[ -f "$TARGET_SCRIPT" ]] || fail "Bundled groovebox.py not found: $TARGET_SCRIPT"

PYTHON_BIN=""
if [[ -n "${GROOVEBOX_PYTHON:-}" ]]; then
    PYTHON_BIN="${GROOVEBOX_PYTHON}"
elif [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    fail "Python 3 was not found. Install Python 3 or set GROOVEBOX_PYTHON."
fi

"$PYTHON_BIN" - <<'PY' || fail "PyQt6 is missing from the selected Python environment. Install it with: python -m pip install PyQt6"
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"Python 3.10+ required; found {sys.version.split()[0]}")
import PyQt6  # noqa: F401
PY

export PYTHONUNBUFFERED="1"
export EQR_CORE_FREQ="432.0"
export EQR_SURVIVAL_MODE="1"
export EQR_CREATIVE_MODE="0"
export EQR_SPATIAL_DIMENSIONS="x,y,z"
export EQR_MODULAR_BAY_ACTIVE="1"

cd -- "$SCRIPT_DIR"

printf '%s\n' "${GREEN}[+] Bundled Groovebox: $TARGET_SCRIPT${NC}"
printf '%s\n' "${GREEN}[+] Python: $PYTHON_BIN${NC}"
printf '%s\n' "${GREEN}[+] Working directory: $SCRIPT_DIR${NC}"

# exec replaces the shell with the exact bundled application process and
# passes every argument through unchanged.
exec "$PYTHON_BIN" "$TARGET_SCRIPT" "$@"
