#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/Groovebox"
exec python3 run_groovebox.py "$@"
