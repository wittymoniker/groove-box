#!/usr/bin/env bash
# Desktop launch: 96 kHz design window
cd "$(dirname "$0")"
export GROOVEBOX_PROFILE=desktop
export GROOVEBOX_SAMPLE_RATE=96000
exec python3 groovebox.py
