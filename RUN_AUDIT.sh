#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT="${1:-.}"
python3 "$HERE/groovebox_mechanical_audit.py" "$PROJECT"
