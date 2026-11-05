#!/usr/bin/env bash
# Preflight. Finds the project root if you run it from BUILD_ISO/.
set -euo pipefail
find_root() {
  local d="$1"
  while [[ "$d" != "/" ]]; do
    if [[ -d "$d/BUILD_ISO" && -f "$d/groovebox.py" ]]; then
      echo "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}
ROOT="$(find_root "$(pwd)")" || ROOT="$(find_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")" || {
  echo "Could not find project root." >&2
  exit 1
}
cd "$ROOT"
echo "Preflight in $ROOT"
fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }
