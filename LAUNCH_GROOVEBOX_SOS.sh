#!/usr/bin/env bash
set -euo pipefail
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# sOS already ships its dependency/runtime image. Do not invoke the desktop
# first-launch installer (launch_groovebox.py) from this appliance wrapper.
[[ -s "$ROOT/run_groovebox.py" && -s "$ROOT/groovebox.py" ]] || {
  echo "Groovebox sOS launcher: run_groovebox.py or groovebox.py is missing under $ROOT" >&2
  exit 71
}
export GROOVEBOX_PROFILE=sos
export GROOVEBOX_APPLIANCE=1
export GROOVEBOX_DATA_DIR="${GROOVEBOX_DATA_DIR:-/var/lib/groovebox}"
if [[ -d /opt/sos/rust/bin ]]; then export PATH="/opt/sos/rust/bin:$PATH"; fi
export CARGO_HOME="${CARGO_HOME:-/opt/sos/rust/cargo-home}"
cd "$ROOT"
unset PYTHONHOME PYTHONPATH PYTHONPYCACHEPREFIX || true

# Probe the complete required import set before choosing an interpreter. This
# makes /opt/pyvenv the preferred runtime, not a single point of failure: a
# repaired system CPython can be used when the venv is missing or damaged.
_probe='from runtime_contract import REQUIRED, interpreter_error; import importlib, sys; e=interpreter_error(); e and sys.exit(e); [importlib.import_module(m) for m, _ in REQUIRED]'
PY="${GROOVEBOX_PYTHON:-}"
if [[ -n "$PY" ]]; then
  if ! command -v "$PY" >/dev/null 2>&1; then
    echo "Groovebox sOS launcher: requested GROOVEBOX_PYTHON is not usable: $PY" >&2
    exit 72
  fi
  if ! "$PY" -c "$_probe" >/dev/null 2>&1; then
    echo "Groovebox sOS launcher: requested Python lacks required Groovebox imports: $PY" >&2
    exit 72
  fi
else
  for candidate in /opt/pyvenv/bin/python3 /usr/bin/python3 "${PYTHON:-python3}" python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$_probe" >/dev/null 2>&1; then
      PY="$candidate"
      break
    fi
  done
fi
[[ -n "$PY" ]] || { echo "Groovebox sOS launcher: no CPython runtime with the required PyQt6/scientific/audio imports was found." >&2; exit 72; }
exec "$PY" "$ROOT/run_groovebox.py" "$@"
