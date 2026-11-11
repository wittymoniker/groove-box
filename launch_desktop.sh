#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
export GROOVEBOX_PROFILE=desktop
export GROOVEBOX_SAMPLE_RATE="${GROOVEBOX_SAMPLE_RATE:-96000}"
exec bash "$ROOT/scripts/launch_entry.sh" "$@"
