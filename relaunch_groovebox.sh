#!/usr/bin/env bash
# Relaunch Groovebox after any crash. A clean exit (0) stops the loop.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
MAX=8
n=0
ORIGINAL_ARGS=("$@")
while [[ "$n" -lt "$MAX" ]]; do
  n=$((n + 1))
  echo "[relaunch] start $n"
  if [[ -s "$ROOT/run_hybrid.sh" ]]; then
    bash "$ROOT/run_hybrid.sh" "$@"
  elif [[ -s "$ROOT/scripts/launch_entry.sh" ]]; then
    bash "$ROOT/scripts/launch_entry.sh" "$@"
  else
    echo "[relaunch] no usable run_hybrid.sh or scripts/launch_entry.sh" >&2
    exit 70
  fi
  code=$?
  if [[ "$code" -eq 0 || "$code" -eq 130 || "$code" -eq 143 ]]; then
    echo "[relaunch] clean exit"
    exit "$code"
  fi
  if [[ "$code" -lt 128 ]]; then
    echo "[relaunch] startup/application error $code; not retrying a broken setup" >&2
    exit "$code"
  fi
  echo "[relaunch] exit $code — bringing windows back"
  sleep 1
  set -- "${ORIGINAL_ARGS[@]}" --skip-startup-launcher --restore-windows
done
echo "[relaunch] stopped after $MAX crashes"
exit 1
