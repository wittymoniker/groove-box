"""HF28 regression test for QTimer lexical scope in the main-window constructor."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "groovebox.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def _constructor_node(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MathematiciansGrooveboxApp":
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__":
                    return child
    raise AssertionError("MathematiciansGrooveboxApp.__init__ not found")


def test_main_window_constructor_does_not_shadow_module_qtimer():
    tree = ast.parse(SOURCE, filename=str(SOURCE_PATH))
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore"]
    assert any(any(alias.name == "QTimer" and alias.asname is None for alias in node.names) for node in imports),         "QTimer must be available from the module-level PyQt6.QtCore import"

    ctor = _constructor_node(tree)
    # Only walk the constructor's own lexical scope; an import inside a nested
    # function would not bind the constructor's local namespace.
    stack = list(ctor.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Import):
            assert not any(alias.name == "QTimer" or alias.asname == "QTimer" for alias in node.names),                 f"constructor shadows QTimer at line {node.lineno}"
        if isinstance(node, ast.ImportFrom):
            assert not any(alias.name == "QTimer" or alias.asname == "QTimer" for alias in node.names),                 f"constructor shadows QTimer at line {node.lineno}"
        stack.extend(ast.iter_child_nodes(node))

    assert "QTimer.singleShot(0, self._main_window_relaunch_filter.ensure_window_strip)" in SOURCE
    assert 'QTimer.singleShot(120, lambda: self._ensure_hardware_use("app-startup-early"))' in SOURCE


def test_iso_overlay_is_byte_synchronized_with_root_source():
    overlay = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py"
    assert overlay.read_bytes() == SOURCE_PATH.read_bytes()
