#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GROOVEBOX_PROFILE=mobile
exec "$ROOT/run_hybrid.sh" "$@"
