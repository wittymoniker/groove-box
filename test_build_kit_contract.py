from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent


def test_windows_exe_builder_gates_complete_qt_runtime_and_collects_qt_payload():
    source = (ROOT / 'BUILD_KIT' / 'build.py').read_text()
    assert 'PyQt6.QtMultimedia import QMediaDevices, QMediaPlayer, QAudioOutput' in source
    assert 'PyQt6.QtMultimediaWidgets import QVideoWidget' in source
    assert 'cmd.extend(["--collect-all", "PyQt6"])' in source
    assert 'cmd.extend(["--collect-all", "sounddevice"])' in source
    assert 'cmd.extend(["--collect-all", "scipy"])' in source
    assert 'cmd.extend(["--collect-all", "PIL"])' in source
    assert "missing sounddevice's PortAudio DLL" in source
    assert 'CArchiveReader' in source and 'one-file archive is missing required runtime resources' in source
    assert 'Qt6MultimediaWidgets.dll' in source and 'QtWebEngineProcess.exe' in source
    assert 'FAIL: required bundled runtime resources missing' in source
    assert 'def verify_scode_stage0()' in source and 'host_scode_relative_path()' in source
    assert 'def verify_python_runtime(' in source and 'check_pyinstaller=True' in source
    assert 'PASS: host-native sCode stage-0 ABI 9' in source
    assert 'FAIL: onedir executable missing or empty' in source
    assert 'Required executable-build imports unavailable' in source
    assert 'Required project-local codecs unavailable' in source
    assert 'PyInstaller' in source


def test_rust_acceleration_is_optional_for_executable_packaging():
    source = (ROOT / 'BUILD_KIT' / 'build.py').read_text()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compile_rust')
    body = ast.get_source_segment(source, fn)
    assert 'except (subprocess.CalledProcessError, OSError)' in body
    assert 'optional Rust accelerator unavailable' in body
    assert 'Do not emit a MinGW DLL' in source


def test_windows_builder_provisions_local_codecs_and_checks_native_exit_codes():
    source = (ROOT / 'BUILD_KIT' / 'install_dependencies_windows.ps1').read_text()
    for token in ('Invoke-Checked', 'provision_first_launch.py', 'QtMultimedia', 'QtMultimediaWidgets', 'libportaudio64bit.dll', 'build.py'):
        assert token in source
    assert 'Rust toolchain unavailable' in source


def test_fedora_pyqt6_package_names_match_fedora_44_repository_layout():
    source = (ROOT / 'install_deps_linux.sh').read_text()
    fedora = source.split('else\n  export DEBIAN_FRONTEND', 1)[0]
    assert 'python3-pyqt6 ' in fedora
    assert 'python3-pyqt6-webengine' in fedora
    assert 'python3-pyqt6-multimedia' not in fedora


def test_linux_build_installer_is_fail_fast_and_fedora44_ffmpeg_safe():
    installer = (ROOT / 'BUILD_KIT' / 'install_dependencies_linux.sh').read_text()
    assert 'ffmpeg-free' in installer
    assert 'ffmpeg-libs' not in installer and 'python3-pyqt6-multimedia' not in installer
    required_transaction = installer.split("echo '[BUILD_KIT] Installing optional media/game packages", 1)[0]
    assert 'dnf install -y' in required_transaction
    assert '|| true' not in required_transaction
    assert 'apt-get install -y' in installer
    assert 'Rust toolchain unavailable' in installer
    assert 'build.py' in installer and '--doctor' in installer


def test_linux_installers_delegate_to_the_correct_canonical_prerequisite_gates():
    root_installer = (ROOT / 'install_dependencies_linux.sh').read_text()
    assert 'BUILD_KIT/install_dependencies_linux.sh' in root_installer
    iso_installer = (ROOT / 'BUILD_ISO/install_dependencies_linux.sh').read_text()
    assert 'ensure_host_build_deps_v35_22zt.sh' in iso_installer
    all_build = (ROOT / 'BUILD_ALL_V3.sh').read_text()
    assert './BUILD_KIT/install_dependencies_linux.sh || true' not in all_build
    assert './BUILD_KIT/build_linux.sh ||' not in all_build


def test_macos_builder_does_not_silently_ignore_required_brew_transaction():
    text = (ROOT / 'BUILD_KIT' / 'install_dependencies_macos.sh').read_text()
    assert 'brew install python ffmpeg portaudio glm' in text
    assert 'brew install python ffmpeg portaudio glm || true' not in text
    assert 'Rust toolchain unavailable' in text
