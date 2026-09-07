#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "$(uname -s 2>/dev/null || true)" in
  Linux) exec "$ROOT/appliance_tools/BUILD_AND_BURN_LINUX.sh" "$@" ;;
  Darwin) exec "$ROOT/appliance_tools/BUILD_AND_BURN_MACOS.command" "$@" ;;
  *) echo "Use appliance_tools/BUILD_AND_BURN_WINDOWS.ps1 on Windows." >&2; exit 2;;
esac
