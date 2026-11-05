"""One root-module inventory for ISO and executable builds."""
from pathlib import Path

REFERENCE_MODULES = frozenset({"groovebox_newold", "groovebox_reference", "groovebox_seqfix"})


def runtime_sources(root):
    return sorted(
        path for path in Path(root).glob("*.py")
        if path.stem.isidentifier()
        and not path.stem.startswith(("test", "benchmark_"))
        and not path.stem.endswith("_tests")
        and path.stem not in REFERENCE_MODULES
    )


def runtime_module_names(root, *, exclude=()):
    """Canonical module names for source checks and PyInstaller hidden imports."""
    excluded = frozenset(exclude)
    return [path.stem for path in runtime_sources(root) if path.stem not in excluded]
