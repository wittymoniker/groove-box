#!/usr/bin/env bash
# =============================================================================
# Groovebox V3[final] — Desktop Launcher with Dependency Checking
# =============================================================================
# This launcher:
#   1. Checks and installs all Python dependencies
#   2. Verifies ffmpeg availability (installs locally if needed)
#   3. Builds C++ acceleration library if needed
#   4. Checks Julia backend availability
#   5. Launches the application
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# 1. Check Python version
# =============================================================================
check_python() {
    log_info "Checking Python version..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        log_success "Python $PYTHON_VERSION found"
    else
        log_error "Python3 not found. Please install Python 3.9+"
        exit 1
    fi
}

# =============================================================================
# 2. Check and install Python dependencies
# =============================================================================
check_python_deps() {
    log_info "Checking Python dependencies..."
    
    REQUIRED_PACKAGES=("numpy" "PyQt6" "sounddevice" "Pillow")
    MISSING_PACKAGES=()
    
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            log_success "$package OK"
        else
            log_warning "$package missing"
            MISSING_PACKAGES+=("$package")
        fi
    done
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        log_info "Installing missing packages: ${MISSING_PACKAGES[*]}"
        python3 -m pip install --upgrade pip wheel
        python3 -m pip install "${MISSING_PACKAGES[@]}"
        log_success "Packages installed"
    fi
}

# =============================================================================
# 3. Check and setup ffmpeg
# =============================================================================
setup_ffmpeg() {
    log_info "Provisioning/validating project-local bin/ffmpeg + bin/ffprobe..."
    python3 "$SCRIPT_DIR/scripts/provision_first_launch.py"
    if [ ! -x "$SCRIPT_DIR/bin/ffmpeg" ] || [ ! -x "$SCRIPT_DIR/bin/ffprobe" ]; then
        log_error "Local FFmpeg pair is incomplete; launch aborted."
        exit 2
    fi
    export PATH="$SCRIPT_DIR/bin:$PATH"
    log_success "Local FFmpeg pair ready; runtime will not resolve system codecs"
}

# =============================================================================
# 4. Build C++ acceleration library
# =============================================================================
build_cpp_accel() {
    log_info "Checking C++ acceleration library..."
    
    LIB_NAME="groovebox_accel"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        LIB_FILE="lib${LIB_NAME}.so"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        LIB_FILE="lib${LIB_NAME}.dylib"
    else
        LIB_FILE="${LIB_NAME}.dll"
    fi
    
    if [ -f "$SCRIPT_DIR/cpp/$LIB_FILE" ]; then
        log_success "C++ library already built"
        return 0
    fi
    
    log_info "Building C++ acceleration library..."
    mkdir -p "$SCRIPT_DIR/cpp"
    
    if command -v g++ &> /dev/null; then
        g++ -std=c++17 -O3 -shared -fPIC \
            -o "$SCRIPT_DIR/cpp/$LIB_FILE" \
            "$SCRIPT_DIR/cpp/groovebox_accel.cpp" \
            -lm -fopenmp 2>/dev/null || \
        g++ -std=c++17 -O3 -shared -fPIC \
            -o "$SCRIPT_DIR/cpp/$LIB_FILE" \
            "$SCRIPT_DIR/cpp/groovebox_accel.cpp" \
            -lm
        
        if [ -f "$SCRIPT_DIR/cpp/$LIB_FILE" ]; then
            log_success "C++ library built successfully"
        else
            log_warning "C++ build failed. Using Python fallback."
        fi
    else
        log_warning "g++ not found. Using Python fallback."
    fi
}

# =============================================================================
# 5. Check Julia backend
# =============================================================================
check_julia() {
    log_info "Checking Julia backend..."
    
    if [ "${GROOVEBOX_JULIA:-1}" = "0" ]; then
        log_info "Julia disabled by environment variable"
        return 0
    fi
    
    if command -v julia &> /dev/null; then
        log_success "Julia found"
        
        # Check if juliacall is available
        if python3 -c "import juliacall" 2>/dev/null; then
            log_success "juliacall Python package available"
        else
            log_warning "juliacall not installed. Julia backend unavailable."
            log_info "Install with: pip install juliacall"
        fi
    else
        log_info "Julia not found. Julia is optional; required sCode + Python/native acceleration remains active."
    fi
}

# =============================================================================
# 6. Set environment variables
# =============================================================================
set_environment() {
    log_info "Setting environment variables..."
    
    export GROOVEBOX_PROFILE=desktop
    export GROOVEBOX_SAMPLE_RATE=96000
    
    # Add local bin to PATH for ffmpeg
    export PATH="$SCRIPT_DIR/bin:$PATH"
    
    log_success "Environment configured for desktop (96kHz)"
}

# =============================================================================
# 7. Launch application
# =============================================================================
launch_app() {
    log_info "Launching Groovebox V3[final]..."
    echo ""
    echo "=========================================="
    echo "  EQR GROOVEBOX — MATHEMATICIAN'S"
    echo "         SCIENTIST'S GROOVEBOX"
    echo "   Required sCode + C++/Python Engine"
    echo "=========================================="
    echo ""
    
    exec python3 run_groovebox.py "$@"
}

# =============================================================================
# Main execution
# =============================================================================
main() {
    echo ""
    echo "Groovebox V3[final] — Pre-launch checks"
    echo "========================================"
    echo ""
    
    check_python
    check_python_deps
    setup_ffmpeg
    build_cpp_accel
    check_julia
    set_environment
    
    echo ""
    echo "All checks passed. Starting application..."
    echo ""
    
    launch_app "$@"
}

# Run main function
main "$@"
