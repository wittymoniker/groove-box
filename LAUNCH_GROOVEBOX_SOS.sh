#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export GROOVEBOX_PROFILE=sos
exec "${PYTHON:-python3}" launch_groovebox.py "$@"
