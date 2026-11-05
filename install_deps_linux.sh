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
  # GROOVEBOX_DNF_MISSING_ONLY_20261031: install only packages that are not
  # already installed. "dnf install" on an installed package with a newer build
  # upgrades it; upgrading qt6-qtbase drags every Qt/KDE package on the host
  # into one large transaction (seen failing on Fedora 44 with the
  # kmime -> kf6-kmime file conflict). Groovebox never upgrades the host stack.
  FEDORA_REQUIRED=(python3 python3-pip python3-devel gcc gcc-c++ glm-devel curl python3-pyqt6 python3-pyqt6-webengine qt6-qtbase qt6-qtbase-gui qt6-qtdeclarative qt6-qtwebchannel qt6-qtwebengine qt6-qtwayland qt6-qtmultimedia alsa-lib alsa-lib-devel portaudio portaudio-devel openssl-devel libffi-devel pipewire wireplumber pipewire-alsa pipewire-pulseaudio mesa-dri-drivers mesa-vulkan-drivers mesa-libgbm libdrm nss nspr fontconfig freetype dbus-libs libXcomposite libXcursor libXdamage libXext libXi libXrandr libXrender libXtst libxcb libxkbcommon libxkbcommon-x11 xcb-util-cursor)
  MISSING=()
  for pkg in "${FEDORA_REQUIRED[@]}"; do
    rpm -q --whatprovides "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
  done
  if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "==> Installing missing Fedora packages: ${MISSING[*]}"
    # GROOVEBOX_DNF_CONFLICT_RETRY_20261031: Fedora sometimes ships packages with
    # undeclared file conflicts (e.g. kf6-kmime vs kmime on Fedora 44). Groovebox
    # never needs those packages, so retry once excluding whatever conflicted.
    DNF_LOG="$(mktemp)"
    set +e
    $SUDO dnf install -y "${MISSING[@]}" 2>&1 | tee "$DNF_LOG"
    DNF_RC=${PIPESTATUS[0]}
    set -e
    if [[ $DNF_RC -ne 0 ]]; then
      mapfile -t CONFLICTS < <(grep -oE 'from install of [^ ]+' "$DNF_LOG" | awk '{print $4}' | sed -E 's/-[^-]+-[^-]+$//' | sort -u)
      if [[ ${#CONFLICTS[@]} -gt 0 ]]; then
        EXCL=(); for c in "${CONFLICTS[@]}"; do EXCL+=("--exclude=$c"); done
        echo "==> Fedora package conflict in: ${CONFLICTS[*]} (not needed by Groovebox); retrying without them" >&2
        $SUDO dnf install -y "${EXCL[@]}" "${MISSING[@]}" || {
          echo "FAIL: dnf could not install: ${MISSING[*]}" >&2
          echo "Fedora repository file conflict. Either wait for the Fedora fix or run:" >&2
          echo "  sudo dnf upgrade --refresh ${EXCL[*]}" >&2
          rm -f "$DNF_LOG"; exit 1; }
      else
        rm -f "$DNF_LOG"; exit 1
      fi
    fi
    rm -f "$DNF_LOG"
  else
    echo "==> All required Fedora packages are already installed; no dnf transaction needed"
  fi

  # Fedora's ffmpeg-free already provides ffmpeg, ffprobe AND ffplay. Do not
  # install RPM Fusion ffmpeg/ffmpeg-libs here; that is what caused the user's
  # ffmpeg-free/libswscale transaction conflict. Optional players must never
  # block the required browser/runtime repair.
  OPTIONAL_FLAGS=(--skip-broken)
  [[ "$REQUEST_SKIP_BROKEN" -eq 1 ]] && OPTIONAL_FLAGS+=(--setopt=skip_if_unavailable=True)
  OPT_MISSING=()
  for pkg in gamescope mpv SDL2 SDL2_mixer openal-soft; do rpm -q --whatprovides "$pkg" >/dev/null 2>&1 || OPT_MISSING+=("$pkg"); done
  [[ ${#OPT_MISSING[@]} -eq 0 ]] || $SUDO dnf install -y "${OPTIONAL_FLAGS[@]}" "${OPT_MISSING[@]}" || \
    echo "[runtime] optional player/game packages skipped; ffplay fallback remains available when provided by ffmpeg-free." >&2
else
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -y
  $SUDO apt-get install -y \
    python3 python3-pip python3-venv python3-dev python3-pyqt6.qtmultimedia build-essential libglm-dev curl \
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
"$SELECTED" -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtMultimedia, PyQt6.QtMultimediaWidgets; print('Groovebox required Python/Qt multimedia runtime OK')"
# WebEngine is optional and can block in Chromium initialization. Its bounded
# installer-only probe must not prevent the main editor/audio runtime starting.
"$SELECTED" - <<'PY'
import subprocess, sys
try:
    subprocess.run([sys.executable, "-c", "import PyQt6.QtWebEngineWidgets"],
                   check=True, timeout=30)
except (OSError, subprocess.SubprocessError) as exc:
    print(f"[runtime] WARNING: optional browser probe failed: {exc}", file=sys.stderr)
PY
"$ROOT/bin/ffmpeg" -hide_banner -version | sed -n '1p'
"$ROOT/bin/ffprobe" -hide_banner -version | sed -n '1p'

echo "==> Verifying bundled required sCode optimizer..."
"$SELECTED" "$ROOT/scripts/ensure_native_scode_stage0.py"
# Rust acceleration is optional; a missing network/toolchain must not prevent
# the supported C++/NumPy/Python fallback from launching.
if ! "$SELECTED" "$ROOT/scripts/ensure_rust_toolchain.py" --install; then
  echo "[runtime] WARNING: Rust toolchain unavailable; continuing with fallback acceleration." >&2
elif ! "$SELECTED" "$ROOT/scripts/build_rust_accel.py"; then
  echo "[runtime] WARNING: Rust accelerator build failed; continuing with fallback acceleration." >&2
fi
echo "==> Done. Launch with ./run_hybrid.sh"
