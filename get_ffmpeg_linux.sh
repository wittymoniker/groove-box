#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$ROOT/bin"
TMP="/tmp/groovebox-ffmpeg"

mkdir -p "$BIN"
rm -rf "$TMP"
mkdir -p "$TMP"

echo "Downloading FFmpeg..."
curl -fL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
  -o "$TMP/ffmpeg.tar.xz"

echo "Extracting..."
tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP"

DIR="$(find "$TMP" -maxdepth 1 -type d -name 'ffmpeg-*' | head -n 1)"

cp "$DIR/ffmpeg" "$BIN/ffmpeg"
cp "$DIR/ffprobe" "$BIN/ffprobe"

chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"

echo
echo "Installed:"
"$BIN/ffmpeg" -version | head -n 1
"$BIN/ffprobe" -version | head -n 1
echo
echo "FFmpeg binaries are in: $BIN"
