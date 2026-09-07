#!/usr/bin/env bash
set -Eeuo pipefail
ISO=${1:?Usage: sudo ./BURN_GROOVEBOX_APPLIANCE_USB.sh path.iso /dev/sdX}
DEV=${2:?Usage: sudo ./BURN_GROOVEBOX_APPLIANCE_USB.sh path.iso /dev/sdX}
[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo/root.' >&2; exit 3; }
[ -f "$ISO" ] || { echo "ISO not found: $ISO" >&2; exit 4; }
case "$DEV" in /dev/sd? | /dev/nvme?n? | /dev/mmcblk?) ;; *) echo "Refusing unexpected device path: $DEV" >&2; exit 5;; esac
echo "THIS WILL OVERWRITE $DEV with $ISO"
read -r -p 'Type BURN to continue: ' ans
[ "$ans" = BURN ] || exit 1
sync
dd if="$ISO" of="$DEV" bs=4M status=progress conv=fsync
sync
echo 'Burn complete.'
