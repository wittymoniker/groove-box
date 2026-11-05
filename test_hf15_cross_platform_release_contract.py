from pathlib import Path
ROOT = Path(__file__).resolve().parent

def test_all_primary_platform_launchers_are_present():
    for name in ('LAUNCH_GROOVEBOX_WINDOWS.bat','LAUNCH_GROOVEBOX_MACOS.command',
                 'LAUNCH_GROOVEBOX_LINUX.sh','LAUNCH_GROOVEBOX_SOS.sh','run_hybrid.sh'):
        assert (ROOT/name).is_file(), name

def test_readme_and_help_document_cross_platform_boundaries():
    for name in ('README.md','HELP_TEXT.md','PLATFORM_RUNTIME_README.txt'):
        text=(ROOT/name).read_text(errors='replace')
        assert 'HF15 — Cross-platform support and deployment guide' in text
        assert 'diagnose_platform.py' in text
        assert 'physical-hardware' in text or 'physical hardware' in text

def test_iso_stages_the_runtime_probe_imported_by_shared_launcher():
    s=(ROOT/'BUILD_ISO/stamp_final_initramfs_v35_22zz.sh').read_text()
    assert 'scripts/media_runtime_bootstrap.py' in s
    assert 'scripts/diagnose_platform.py' in s
    assert 'HELP_TEXT.md' in s

def test_diagnostic_is_read_only_and_reports_platform_and_audio():
    s=(ROOT/'scripts/diagnose_platform.py').read_text()
    assert 'platform.platform()' in s
    assert 'sd.query_devices()' in s
    assert 'Read-only' in s and 'never installs packages' in s
    assert 'wpctl' in s and 'pactl' in s
