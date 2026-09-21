#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GROOVEBOX_PROFILE=desktop
export GROOVEBOX_SAMPLE_RATE="${GROOVEBOX_SAMPLE_RATE:-96000}"
exec "$ROOT/run_hybrid.sh" "$@"
