#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "$ROOT/BUILD_KIT/install_dependencies_linux.sh" "$@"
