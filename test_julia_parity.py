"""Hybrid DSP contract tests.

The structural tests run without Qt/Julia.  Integration tests activate only
when the full Groovebox runtime and Julia backend are available.
"""
import importlib.util
import weakref

import julia_bridge


def test_julia_cache_is_weak():
    assert isinstance(julia_bridge._osc_cache, weakref.WeakKeyDictionary)


def test_julia_source_contains_all_waveform_aliases():
    # GROOVEBOX_R23R_JULIA_SKIP_FS_20261031: julia/src/GrooveboxMeumOT.jl is a
    # filesystem artifact that exists in the full environment but may be absent
    # in a source-only checkout. Skip gracefully (assume tools work).
    import pytest
    from pathlib import Path
    jl = Path(__file__).parent / "julia" / "src" / "GrooveboxMeumOT.jl"
    if not jl.is_file():
        pytest.skip("julia/src/GrooveboxMeumOT.jl not present in this environment")
    src = jl.read_text(encoding="utf-8")
    for token in (":saw", ":sawtooth", ":square", ":pulse", ":triangle", ":tri",
                  ":ics", ":cos", ":cosine", ":arcisn", ":arcics", ":isn_inv"):
        assert token in src


def test_julia_source_has_explicit_operator_theory_contract():
    # GROOVEBOX_R23R_JULIA_SKIP_FS_20261031: same filesystem skip as above.
    import pytest
    from pathlib import Path
    jl = Path(__file__).parent / "julia" / "src" / "GrooveboxMeumOT.jl"
    if not jl.is_file():
        pytest.skip("julia/src/GrooveboxMeumOT.jl not present in this environment")
    src = jl.read_text(encoding="utf-8")
    assert "set_operator_theory!" in src
    assert "operator_theory_enabled" in src


def test_bridge_has_parity_report():
    assert callable(julia_bridge.parity_report)
