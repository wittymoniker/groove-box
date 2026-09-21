from pathlib import Path
root=Path(__file__).resolve().parent
linux=(root/'install_deps_linux.sh').read_text()
run=(root/'run_hybrid.sh').read_text()
ensure=(root/'scripts/ensure_runtime_dependencies.py').read_text()
assert 'python3-pyqt6-webengine' in linux
assert 'python3-pyqt6-base' in linux
assert 'ffmpeg ffmpeg-libs' not in linux.replace('RPM Fusion `ffmpeg` / `ffmpeg-libs`','')
assert 'optional player/game packages skipped' in linux
assert '--allowerasing' in run and 'APP_ARGS' in run
assert 'stdout=sys.stderr, stderr=sys.stderr' in ensure
assert 'QT_PIP_PACKAGES' in ensure and '_remove_local_qt_wheels' in ensure
assert 'capture_output=True' in ensure
print('PASS: v35.22d Fedora/WebEngine runtime repair contract')

# v35.22e: Fedora user-site/PYTHONPATH Qt ABI isolation
assert 'PYTHONNOUSERSITE=1' in run
assert 'unset PYTHONPATH' in run
assert 'PYTHONNOUSERSITE' in ensure and '_runtime_env' in ensure
assert 'include-system-site-packages = true' in ensure
launch=(root/'launch_groovebox.py').read_text()
assert 'GROOVEBOX_FEDORA_QT_ISOLATED' in launch and "'-s'" in launch
print('PASS: v35.22e Fedora Qt ABI isolation contract')
