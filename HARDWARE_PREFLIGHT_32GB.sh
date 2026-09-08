#!/usr/bin/env bash
set -u

printf '=== Groovebox 32GB x86-64 Hardware Preflight ===\n'
printf 'Date: '; date 2>/dev/null || true
printf 'Kernel: '; uname -a 2>/dev/null || true
printf 'Architecture: '; uname -m 2>/dev/null || true
printf '\n--- Memory ---\n'
free -h 2>/dev/null || cat /proc/meminfo 2>/dev/null | head -20 || true
printf '\n--- CPU ---\n'
lscpu 2>/dev/null | sed -n '1,30p' || true
printf '\n--- PCI devices ---\n'
lspci -nnk 2>/dev/null || true
printf '\n--- USB devices ---\n'
lsusb 2>/dev/null || true
printf '\n--- Input/touch devices ---\n'
cat /proc/bus/input/devices 2>/dev/null || true
printf '\n--- Video/camera devices ---\n'
ls -l /dev/video* 2>/dev/null || printf 'No /dev/video* nodes found\n'
command -v v4l2-ctl >/dev/null 2>&1 && v4l2-ctl --list-devices 2>/dev/null || true
printf '\n--- Audio devices ---\n'
command -v wpctl >/dev/null 2>&1 && wpctl status 2>/dev/null || true
command -v pactl >/dev/null 2>&1 && pactl list short sinks 2>/dev/null || true
command -v pactl >/dev/null 2>&1 && pactl list short sources 2>/dev/null || true
arecord -l 2>/dev/null || true
aplay -l 2>/dev/null || true
printf '\n--- Network ---\n'
command -v nmcli >/dev/null 2>&1 && nmcli device status 2>/dev/null || true
command -v rfkill >/dev/null 2>&1 && rfkill list 2>/dev/null || true
printf '\n--- Displays ---\n'
command -v xrandr >/dev/null 2>&1 && xrandr --query 2>/dev/null || true
for f in /sys/class/drm/card*-*/status; do [ -e "$f" ] && printf '%s: %s\n' "$f" "$(cat "$f" 2>/dev/null)"; done
printf '\n--- Battery / power ---\n'
for b in /sys/class/power_supply/*; do
  [ -d "$b" ] || continue
  printf '%s\n' "$b"
  for f in type status capacity manufacturer model_name; do [ -r "$b/$f" ] && printf '  %s: %s\n' "$f" "$(cat "$b/$f")"; done
done
printf '\n--- Storage / boot ---\n'
lsblk -o NAME,TYPE,SIZE,FSTYPE,MODEL,TRAN,MOUNTPOINTS 2>/dev/null || true
if [ -d /sys/firmware/efi ]; then printf 'Boot mode: UEFI\n'; else printf 'Boot mode: legacy/unknown (UEFI preferred)\n'; fi
printf '\nPreflight is READ-ONLY. Review missing devices before installing to internal storage.\n'
