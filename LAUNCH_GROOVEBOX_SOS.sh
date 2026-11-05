#!/usr/bin/env bash
set -euo pipefail
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
PY="${GROOVEBOX_PYTHON:-}"
if [[ -n "$PY" ]] && ! command -v "$PY" >/dev/null 2>&1; then
  echo "Groovebox sOS launcher: requested GROOVEBOX_PYTHON is not usable: $PY" >&2
  exit 72
fi
[[ -n "$PY" ]] || PY=/opt/pyvenv/bin/python3
[[ -x "$PY" ]] || PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "Groovebox sOS launcher: no usable Python interpreter" >&2; exit 72; }
cd "$ROOT"
unset PYTHONHOME PYTHONPATH PYTHONPYCACHEPREFIX || true
exec "$PY" "$ROOT/run_groovebox.py" "$@"
