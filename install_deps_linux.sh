#!/usr/bin/env bash
# Groovebox complete Linux desktop runtime installer (v35.22e).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DISTRO="auto"
# Accepted so a command copied from dnf's suggestion does not get forwarded to
# Groovebox itself. The required transaction deliberately does NOT use
# --allowerasing: Groovebox should never replace the host multimedia stack.
REQUEST_SKIP_BROKEN=0
for arg in "$@"; do
  case "$arg" in
    --fedora) DISTRO="fedora" ;;
    --ubuntu) DISTRO="ubuntu" ;;
    --distro=*) DISTRO="${arg#--distro=}" ;;
    --skip-broken) REQUEST_SKIP_BROKEN=1 ;;
    --allowerasing)
      echo "[runtime] NOTE: --allowerasing accepted but intentionally not used; Groovebox will not erase/replace Fedora multimedia packages." >&2
      ;;
    -h|--help)
      echo "Usage: $0 [--fedora|--ubuntu|--distro=NAME] [--skip-broken] [--allowerasing]"
      exit 0
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if [[ "$DISTRO" == auto && -f /etc/os-release ]]; then
  . /etc/os-release
  case "${ID:-} ${ID_LIKE:-}" in
    *fedora*|*centos*|*rhel*) DISTRO="fedora" ;;
    *ubuntu*|*debian*) DISTRO="ubuntu" ;;
  esac
fi
case "$DISTRO" in fedora|ubuntu) ;; *) echo "Unsupported Linux distribution '$DISTRO'." >&2; exit 3;; esac
if [[ "$DISTRO" == fedora ]]; then
  export PYTHONNOUSERSITE=1
  unset PYTHONPATH || true
fi
SUDO=""; [[ "$(id -u)" -eq 0 ]] || SUDO="sudo"

echo "==> Groovebox installer: Linux/$DISTRO"
if [[ "$DISTRO" == fedora ]]; then
  echo "==> Installing required Fedora runtime (no RPM Fusion multimedia replacement)"
  # Fedora 44 ships a synchronized Python 3.14 / PyQt6 / QtWebEngine stack.
  # Prefer it over mixing pip Qt wheels with distro Qt shared libraries.
  $SUDO dnf install -y \
    python3 python3-pip python3-devel gcc gcc-c++ \
    python3-pyqt6-base python3-pyqt6-webengine \
    qt6-qtbase qt6-qtbase-gui qt6-qtdeclarative qt6-qtwebchannel qt6-qtwebengine qt6-qtwayland \
    alsa-lib alsa-lib-devel portaudio portaudio-devel openssl-devel libffi-devel \
    pipewire wireplumber pipewire-alsa pipewire-pulseaudio \
    mesa-dri-drivers mesa-vulkan-drivers mesa-libgbm libdrm \
    nss nspr fontconfig freetype dbus-libs \
    libXcomposite libXcursor libXdamage libXext libXi libXrandr libXrender libXtst \
    libxcb libxkbcommon libxkbcommon-x11 xcb-util-cursor

  # Fedora's ffmpeg-free already provides ffmpeg, ffprobe AND ffplay. Do not
  # install RPM Fusion ffmpeg/ffmpeg-libs here; that is what caused the user's
  # ffmpeg-free/libswscale transaction conflict. Optional players must never
  # block the required browser/runtime repair.
  OPTIONAL_FLAGS=(--skip-broken)
  [[ "$REQUEST_SKIP_BROKEN" -eq 1 ]] && OPTIONAL_FLAGS+=(--setopt=skip_if_unavailable=True)
  $SUDO dnf install -y "${OPTIONAL_FLAGS[@]}" gamescope mpv SDL2 SDL2_mixer openal-soft || \
    echo "[runtime] optional player/game packages skipped; ffplay fallback remains available when provided by ffmpeg-free." >&2
else
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -y
  $SUDO apt-get install -y \
    python3 python3-pip python3-venv python3-dev build-essential \
    ffmpeg pipewire wireplumber libasound2-dev portaudio19-dev libssl-dev libffi-dev \
    libnss3 libxkbcommon-x11-0 libgbm1 libxcomposite1 libxdamage1 libxrandr2 \
    libsdl2-2.0-0 libsdl2-mixer-2.0-0 libopenal1
  $SUDO apt-get install -y mpv || true
  $SUDO apt-get install -y ubuntu-restricted-extras || true
fi

if [[ "$DISTRO" == fedora ]]; then
  SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py" --force-install --prefer-system-qt)"
else
  SELECTED="$(python3 "$ROOT/scripts/ensure_runtime_dependencies.py" --force-install)"
fi
"$SELECTED" "$ROOT/scripts/provision_first_launch.py"

echo "==> Verify complete runtime:"
"$SELECTED" -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtWebEngineWidgets; print('Groovebox Python/browser runtime OK')"
"$ROOT/bin/ffmpeg" -hide_banner -version | head -1
"$ROOT/bin/ffprobe" -hide_banner -version | head -1

echo "==> Verifying bundled required sCode optimizer..."
"$SELECTED" "$ROOT/scripts/ensure_native_scode_stage0.py"
echo "==> Done. Launch with ./run_hybrid.sh"
