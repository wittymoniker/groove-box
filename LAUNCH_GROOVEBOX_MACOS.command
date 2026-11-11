#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
# Shared launcher selects Darwin provisioning when run_hybrid.sh is present;
# its source-runner fallback still performs the runtime preflight.
exec bash "$ROOT/scripts/launch_entry.sh" "$@"
