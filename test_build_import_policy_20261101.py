"""The EXE builder's standalone import policy must pass on the shipped tree.

BUILD_KIT/build.py refuses direct ``sounddevice``/SciPy imports outside
audio_os_backend; run the same function here so a violation fails in pytest
instead of half-way through an executable build.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent


def test_runtime_import_policy_passes():
    tree = ast.parse((ROOT / "BUILD_KIT" / "build.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "enforce_runtime_import_policy")
    from runtime_payload import runtime_sources
    ns = {"ROOT": ROOT, "runtime_sources": runtime_sources}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "build_policy", "exec"), ns)
    ns["enforce_runtime_import_policy"]()  # raises SystemExit on any violation
