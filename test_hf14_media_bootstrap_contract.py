from pathlib import Path
ROOT=Path(__file__).resolve().parent

def test_media_bootstrap_is_delayed_bounded_and_diagnostic():
    s=(ROOT/"scripts/media_runtime_bootstrap.py").read_text()
    assert "QTimer.singleShot(1200, run_probe)" in s
    assert "state[\"attempt\"] < 4" in s
    assert "QMediaDevices.audioOutputs()" in s
    assert "sd.query_devices()" in s  # documented equivalent in bootstrap diagnostics
    assert "audio_device_diagnostics(force=True)" in s
    assert "enumeration_error" in s
    assert "media-bootstrap.log" in s

def test_bootstrap_is_scheduled_after_qapplication():
    s=(ROOT/"run_groovebox.py").read_text()
    assert s.index("app = QApplication(sys.argv)") < s.index("_schedule_media_bootstrap(app)")

def test_runtime_requires_qt_multimedia_contract():
    s=(ROOT/"scripts/runtime_dependencies.py").read_text()
    assert '("PyQt6.QtMultimedia", "PyQt6")' in s
    assert '("PyQt6.QtMultimediaWidgets", "PyQt6")' in s
    assert 'OPTIONAL = (' in s
    assert '(*REQUIRED, *OPTIONAL)' in s

def test_installer_requests_distro_multimedia_packages():
    s=(ROOT/"install_deps_linux.sh").read_text()
    assert "python3-pyqt6" in s
    assert "python3-pyqt6-multimedia" not in s
    assert "python3-pyqt6.qtmultimedia" in s
