#!/usr/bin/env bash
# Safe first-boot Wi-Fi hardware selection for Groovebox standalone appliances.
# Does not create/join a network or start a hotspot.
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export GROOVEBOX_PROFILE="${GROOVEBOX_PROFILE:-sos}"
exec "${PYTHON:-python3}" "$ROOT/appliance_wifi.py"
