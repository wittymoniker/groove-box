from pathlib import Path
ROOT=Path(__file__).resolve().parent

def test_diagnostic_enumerates_qt_audio_and_camera_devices():
    s=(ROOT/'scripts/diagnose_platform.py').read_text()
    for token in ('QMediaDevices.audioOutputs()', 'QMediaDevices.audioInputs()', 'QMediaDevices.videoInputs()', 'sd.query_devices()', 'diagnostic-only'):
        assert token in s

def test_windows_installer_requires_complete_multimedia_runtime():
    s=(ROOT/'install_deps_windows.ps1').read_text()
    assert 'PyQt6.QtMultimedia, PyQt6.QtMultimediaWidgets' in s
    assert 'complete Python/Qt runtime verification failed' in s

def test_help_explains_media_and_all_output_boundary():
    for name in ('README.md','HELP_TEXT.md','PLATFORM_RUNTIME_README.txt'):
        s=(ROOT/name).read_text(errors='replace')
        assert 'diagnose_platform.py' in s
    s=(ROOT/'HELP_TEXT.md').read_text()
    assert 'fan-out implementation' in s

def test_iso_stamps_current_diagnostic_and_help():
    s=(ROOT/'BUILD_ISO/stamp_final_initramfs_v35_22zz.sh').read_text()
    assert 'diagnose_platform.py' in s and 'HELP_TEXT.md' in s


def test_audio_backend_exposes_portaudio_enumeration_failure():
    s=(ROOT/'audio_os_backend.py').read_text()
    assert 'def audio_device_diagnostics(force=True):' in s
    assert 'query_hostapis()' in s
    assert 'PortAudio returned zero devices' in s
    assert 'enumeration_error' in s

def test_hybrid_installer_installs_os_audio_and_qt_multimedia_stack():
    s=(ROOT/'scripts/install_hybrid_linux.sh').read_text()
    canonical=(ROOT/'install_deps_linux.sh').read_text()
    assert 'bash ./install_deps_linux.sh' in s
    for token in ('wireplumber','pipewire-alsa','portaudio','python3-pyqt6','qt6-qtmultimedia'):
        assert token in canonical
