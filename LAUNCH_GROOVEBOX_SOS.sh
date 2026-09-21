#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export GROOVEBOX_PROFILE=sos
# Appliance images already contain the complete runtime. launch_groovebox.py
# verifies the shared manifest but will not reinstall anything when it is intact.
exec "${PYTHON:-python3}" "$ROOT/launch_groovebox.py" "$@"
