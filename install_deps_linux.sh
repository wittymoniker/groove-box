#!/usr/bin/env bash
# =============================================================================
# Groovebox dependency installer - Linux
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency onto this machine and puts
# the ffmpeg codec binaries into /bin (the directory VideoSynthEngine's codec
# resolver checks first), so audio+video export work with real encoders.
#
# Usage:
#   ./install_deps_linux.sh            auto-detect Fedora vs Ubuntu-family
#   ./install_deps_linux.sh --fedora   force the DNF/Fedora path
#   ./install_deps_linux.sh --ubuntu   force the apt/Ubuntu-family path
#   ./install_deps_linux.sh --distro=<name>  force any supported family
# =============================================================================
set -u

DISTRO="auto"
for arg in "$@"; do
  case "$arg" in
    --fedora)  DISTRO="fedora";;
    --ubuntu)  DISTRO="ubuntu";;
    --distro=*) DISTRO="${arg#--distro=}";;
    -h|--help)
      sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
      exit 0;;
    *) echo "Unknown argument: $arg"; exit 2;;
  esac
done

if [ "$DISTRO" = "auto" ]; then
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *fedora*|*centos*|*rhel*) DISTRO="fedora";;
      *ubuntu*|*debian*)        DISTRO="ubuntu";;
    esac
  fi
fi

case "$DISTRO" in
  fedora|ubuntu) : ;;
  *)
    echo "Unsupported or undetectable distribution '$DISTRO'."
    echo "Use the toggle:  $0 --fedora   |   $0 --ubuntu"
    exit 3;;
esac

echo "==> Groovebox installer: Linux/$DISTRO"

# This script needs root for system packages and the /bin codec drop.
if [ "$(id -u)" -ne 0 ]; then
  echo "Re-running with sudo..."
  exec sudo "$0" "$@"
fi

set -e

PIP_DEPS="numpy scipy PyQt6 sounddevice Pillow"

if [ "$DISTRO" = "fedora" ]; then
  echo "==> Enabling RPM Fusion (free + nonfree) for full ffmpeg codecs..."
  dnf install -y \
    "https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
    "https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
  dnf install -y \
    python3 python3-pip python3-devel gcc gcc-c++ \
    ffmpeg ffmpeg-libs alsa-lib-devel portaudio-devel openssl-devel libffi-devel
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y \
    python3 python3-pip python3-venv python3-dev build-essential \
    ffmpeg libasound2-dev portaudio19-dev libssl-dev libffi-dev
  # Broad codec pack (mp3 / mp4 / aac / av1 / h264 …). Best effort: this is a
  # multiverse package; if it fails, core ffmpeg above already covers WAV/PNG
  # frame muxing and the common containers.
  apt-get install -y ubuntu-restricted-extras || true
fi

echo "==> Installing Python packages: $PIP_DEPS"
python3 -m pip install --upgrade pip wheel
python3 -m pip install $PIP_DEPS

echo "==> Placing codec binaries into /bin ..."
FF=$(command -v ffmpeg || true)
FP=$(command -v ffprobe || true)
if [ -n "$FF" ]; then cp -f "$FF" /bin/ffmpeg || ln -sf "$FF" /bin/ffmpeg; fi
if [ -n "$FP" ]; then cp -f "$FP" /bin/ffprobe || ln -sf "$FP" /bin/ffprobe; fi

echo "==> Verify:"
python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
command -v ffmpeg; command -v ffprobe
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "libx264|aac|libvpx|libvorbis" | sed 's/^/  encoder: /' | head -6
echo "==> Done."
echo "    Run the app:   python3 groovebox.py"
