#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
export GROOVEBOX_PROFILE=mobile
exec bash "$ROOT/scripts/launch_entry.sh" "$@"
