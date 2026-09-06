#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/reverse_decode_groovebox.py --resolution 8
python3 - <<'PY' "$@"
import sys
from pathlib import Path
from scode.runtime import run_program
raise SystemExit(run_program(Path('generated/groovebox_finished_stab.sC'), ['groovebox'] + sys.argv[1:]))
PY
