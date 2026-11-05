#!/bin/sh
# Builds MCC_GALLERY/index.html for the .MCC files in this folder (Linux).
cd "$(dirname "$0")" || exit 1
exec python3 PASTE_ME_NEAR_MCC.py "$(pwd)"
