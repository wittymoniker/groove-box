#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
export GROOVEBOX_PROFILE="${GROOVEBOX_PROFILE:-desktop}"
exec bash "$ROOT/scripts/launch_entry.sh" "$@"
