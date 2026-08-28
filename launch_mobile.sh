#!/usr/bin/env bash
# Mobile-oriented launch: 48 kHz, lower default ensemble pressure
cd "$(dirname "$0")"
export GROOVEBOX_PROFILE=mobile
export GROOVEBOX_SAMPLE_RATE=48000
python3 -c "
import os
os.environ.setdefault('GROOVEBOX_PROFILE', 'mobile')
# Patch preferred rate before import side-effects where possible
import groovebox as gb
if hasattr(gb, 'TARGET_SAMPLE_RATE'):
    gb.TARGET_SAMPLE_RATE = 48000
" 2>/dev/null || true
exec python3 groovebox.py
