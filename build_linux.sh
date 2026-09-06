#!/usr/bin/env bash
set -Eeuo pipefail
KIT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$KIT/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$KIT/build.py" "$@"
