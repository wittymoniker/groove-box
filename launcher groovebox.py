#!/usr/bin/env python3
"""
Groovebox V3[final] — Main Launcher with Dependency Checking

This launcher:
  1. Checks and installs all Python dependencies
  2. Verifies ffmpeg availability (installs locally if needed)
  3. Builds C++ acceleration library if needed
  4. Checks Julia backend availability
  5. Launches the application
"""
from __future__ import annotations

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}[OK]{Colors.NC} {msg}")

def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def log_error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")


def check_python_version() -> bool:
    """Check Python version is 3.9+."""
    log_info("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        log_success(f"Python {version.major}.{version.minor}.{version.micro} found")
        return True
    else:
        log_error(f"Python 3.9+ required, found {version.major}.{version.minor}")
        return False


def check_python_deps() -> bool:
    """Check and install required Python packages."""
    log_info("Checking Python dependencies...")
    
    required_packages = {
        'numpy': 'numpy',
        'scipy': 'scipy',
        'PyQt6': 'PyQt6',
        'sounddevice': 'sounddevice',
        'Pillow': 'Pillow'
    }
    
    missing_packages = []
    
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            log_success(f"{package_name} OK")
        except ImportError:
            log_warning(f"{package_name} missing")
            missing_packages.append(package_name)
    
    if missing_packages:
        log_info(f"Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip', 'wheel'
            ])
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_packages)
            log_success("Packages installed")
            return True
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to install packages: {e}")
            return False
    
    return True


def setup_ffmpeg() -> bool:
    """Check and setup ffmpeg for video/audio export."""
    log_info("Checking ffmpeg...")
    
    root = Path(__file__).parent.absolute()
    bin_dir = root / 'bin'
    bin_dir.mkdir(exist_ok=True)
    
    # Check local bin first
    local_ffmpeg = bin_dir / 'ffmpeg'
    if local_ffmpeg.exists():
        log_success("Local ffmpeg found in bin/")
        os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
        return True
    
    # Check system ffmpeg
    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        log_success(f"System ffmpeg found: {system_ffmpeg}")
        
        # Copy to local bin for export readiness
        try:
            shutil.copy2(system_ffmpeg, bin_dir / 'ffmpeg')
            system_ffprobe = shutil.which('ffprobe')
            if system_ffprobe:
                shutil.copy2(system_ffprobe, bin_dir / 'ffprobe')
            log_success("ffmpeg copied to local bin/")
        except Exception as e:
            log_warning(f"Could not copy ffmpeg: {e}")
        
        os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
        return True
    
    # Try to install ffmpeg locally
    log_warning("ffmpeg not found. Attempting local installation...")
    
    system = platform.system()
    
    if system == 'Linux':
        # Try apt
        if shutil.which('apt-get'):
            try:
                subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], check=True)
                system_ffmpeg = shutil.which('ffmpeg')
                if system_ffmpeg:
                    shutil.copy2(system_ffmpeg, bin_dir / 'ffmpeg')
                    system_ffprobe = shutil.which('ffprobe')
                    if system_ffprobe:
                        shutil.copy2(system_ffprobe, bin_dir / 'ffprobe')
                    log_success("ffmpeg installed via apt")
                    os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
                    return True
            except Exception as e:
                log_warning(f"apt install failed: {e}")
        
        # Try dnf
        if shutil.which('dnf'):
            try:
                subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True)
                system_ffmpeg = shutil.which('ffmpeg')
                if system_ffmpeg:
                    shutil.copy2(system_ffmpeg, bin_dir / 'ffmpeg')
                    log_success("ffmpeg installed via dnf")
                    os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
                    return True
            except Exception as e:
                log_warning(f"dnf install failed: {e}")
    
    elif system == 'Darwin':
        # macOS with Homebrew
        if shutil.which('brew'):
            try:
                subprocess.run(['brew', 'install', 'ffmpeg'], check=True)
                system_ffmpeg = shutil.which('ffmpeg')
                if system_ffmpeg:
                    shutil.copy2(system_ffmpeg, bin_dir / 'ffmpeg')
                    log_success("ffmpeg installed via brew")
                    os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
                    return True
            except Exception as e:
                log_warning(f"brew install failed: {e}")
    
    log_error("Could not install ffmpeg. Video export may not work.")
    return False


def build_cpp_accel() -> bool:
    """Build C++ acceleration library if needed."""
    log_info("Checking C++ acceleration library...")
    
    root = Path(__file__).parent.absolute()
    cpp_dir = root / 'cpp'
    cpp_dir.mkdir(exist_ok=True)
    
    system = platform.system()
    if system == 'Linux':
        lib_name = 'libgroovebox_accel.so'
    elif system == 'Darwin':
        lib_name = 'libgroovebox_accel.dylib'
    else:
        lib_name = 'groovebox_accel.dll'
    
    lib_path = cpp_dir / lib_name
    source_path = cpp_dir / 'groovebox_accel.cpp'
    
    if lib_path.exists():
        log_success("C++ library already built")
        return True
    
    if not source_path.exists():
        log_warning("C++ source not found. Skipping build.")
        return False
    
    log_info("Building C++ acceleration library...")
    
    gpp = shutil.which('g++') or shutil.which('c++')
    if not gpp:
        log_warning("g++ not found. Using Python fallback.")
        return False
    
    try:
        # Try with OpenMP first
        subprocess.run([
            gpp, '-std=c++17', '-O3', '-shared', '-fPIC',
            '-o', str(lib_path),
            str(source_path),
            '-lm', '-fopenmp'
        ], check=True, capture_output=True)
        log_success("C++ library built with OpenMP")
        return True
    except subprocess.CalledProcessError:
        try:
            # Try without OpenMP
            subprocess.run([
                gpp, '-std=c++17', '-O3', '-shared', '-fPIC',
                '-o', str(lib_path),
                str(source_path),
                '-lm'
            ], check=True, capture_output=True)
            log_success("C++ library built (no OpenMP)")
            return True
        except subprocess.CalledProcessError as e:
            log_warning(f"C++ build failed: {e}")
            log_warning("Using Python fallback.")
            return False


def check_julia() -> bool:
    """Check Julia backend availability."""
    log_info("Checking Julia backend...")
    
    if os.environ.get('GROOVEBOX_JULIA', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        log_info("Julia disabled by environment variable")
        return True
    
    julia_exe = shutil.which('julia')
    if julia_exe:
        log_success(f"Julia found: {julia_exe}")
        
        # Check if juliacall is available
        try:
            __import__('juliacall')
            log_success("juliacall Python package available")
            return True
        except ImportError:
            log_warning("juliacall not installed. Julia backend unavailable.")
            log_info("Install with: pip install juliacall")
            return True
    else:
        log_info("Julia not found. Using Python-only mode.")
        return True


def set_environment() -> None:
    """Set environment variables for the application."""
    log_info("Setting environment variables...")
    
    root = Path(__file__).parent.absolute()
    bin_dir = root / 'bin'
    
    # Add local bin to PATH
    os.environ['PATH'] = str(bin_dir) + os.pathsep + os.environ.get('PATH', '')
    
    # Set profile based on platform/args
    if '--mobile' in sys.argv:
        os.environ['GROOVEBOX_PROFILE'] = 'mobile'
        os.environ['GROOVEBOX_SAMPLE_RATE'] = '48000'
        log_success("Environment configured for mobile (48kHz)")
    else:
        os.environ['GROOVEBOX_PROFILE'] = 'desktop'
        os.environ['GROOVEBOX_SAMPLE_RATE'] = '96000'
        log_success("Environment configured for desktop (96kHz)")


def launch_app() -> int:
    """Launch the main Groovebox application."""
    log_info("Launching Groovebox V3[final]...")
    print()
    print("=" * 50)
    print("  EQR GROOVEBOX — MATHEMATICIAN'S")
    print("         SCIENTIST'S GROOVEBOX")
    print("   Hybrid C++/Python/Julia Engine")
    print("=" * 50)
    print()
    
    # Add script directory to path
    root = Path(__file__).parent.absolute()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    
    os.chdir(root)
    
    try:
        from PyQt6.QtWidgets import QApplication
        import groovebox
        
        app = QApplication(sys.argv)
        win = groovebox.MathematiciansGrooveboxApp()
        win.show()
        return int(app.exec())
    except ImportError as e:
        log_error(f"Failed to import application: {e}")
        log_error("Please check your Python dependencies.")
        return 1
    except Exception as e:
        log_error(f"Application error: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    print()
    print("Groovebox V3[final] — Pre-launch checks")
    print("=" * 45)
    print()
    
    # Run all checks
    checks = [
        ("Python version", check_python_version),
        ("Python dependencies", check_python_deps),
        ("ffmpeg", setup_ffmpeg),
        ("C++ acceleration", build_cpp_accel),
        ("Julia backend", check_julia),
    ]
    
    all_passed = True
    for name, check_fn in checks:
        try:
            if not check_fn():
                all_passed = False
        except Exception as e:
            log_error(f"{name} check failed: {e}")
            all_passed = False
    
    # Set environment
    set_environment()
    
    if not all_passed:
        log_warning("Some checks failed. Application may have limited functionality.")
    
    print()
    print("Checks complete. Starting application...")
    print()
    
    return launch_app()


if __name__ == "__main__":
    raise SystemExit(main())
