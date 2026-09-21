from __future__ import annotations
import importlib.util
import os
from pathlib import Path

root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ensure_runtime_dependencies', root/'scripts'/'ensure_runtime_dependencies.py')
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

env=mod._runtime_env(True)
assert env.get('PYTHONNOUSERSITE') == '1'
assert 'PYTHONPATH' not in env

env2=mod._runtime_env(False)
# Non-Fedora/non-system-Qt mode must not invent isolation variables.
if 'PYTHONNOUSERSITE' not in os.environ:
    assert 'PYTHONNOUSERSITE' not in env2

run=(root/'run_hybrid.sh').read_text()
linux=(root/'install_deps_linux.sh').read_text()
launch=(root/'launch_groovebox.py').read_text()
ensure=(root/'scripts'/'ensure_runtime_dependencies.py').read_text()
assert 'export PYTHONNOUSERSITE=1' in run and 'unset PYTHONPATH' in run
assert 'export PYTHONNOUSERSITE=1' in linux and 'unset PYTHONPATH' in linux
assert 'GROOVEBOX_FEDORA_QT_ISOLATED' in launch and "'-s'" in launch
assert 'include-system-site-packages = true' in ensure
print('PASS: v35.22e Fedora Qt ABI isolation behavior')
