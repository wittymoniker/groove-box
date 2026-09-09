#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" launch_groovebox.py "$@"
