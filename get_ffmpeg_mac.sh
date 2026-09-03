#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$ROOT/bin"
TMP="/tmp/groovebox-ffmpeg"

mkdir -p "$BIN"
rm -rf "$TMP"
mkdir -p "$TMP"

echo "Downloading FFmpeg for macOS..."

curl -fL https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip \
  -o "$TMP/ffmpeg.zip"

curl -fL https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip \
  -o "$TMP/ffprobe.zip"

unzip -o "$TMP/ffmpeg.zip" -d "$TMP"
unzip -o "$TMP/ffprobe.zip" -d "$TMP"

cp "$TMP/ffmpeg" "$BIN/ffmpeg"
cp "$TMP/ffprobe" "$BIN/ffprobe"

chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"

echo
echo "Installed:"
"$BIN/ffmpeg" -version | head -n 1
"$BIN/ffprobe" -version | head -n 1
echo
echo "FFmpeg binaries are in: $BIN"
