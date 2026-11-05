#!/bin/bash
# Builds MCC_GALLERY/index.html for the .MCC files in this folder (macOS).
cd "$(dirname "$0")" || exit 1
exec python3 PASTE_ME_NEAR_MCC.py "$(pwd)"
