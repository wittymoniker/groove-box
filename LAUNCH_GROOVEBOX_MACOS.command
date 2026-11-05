#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
# Share one handoff; run_hybrid selects Darwin's installer and library format.
exec bash "$ROOT/run_hybrid.sh" "$@"
