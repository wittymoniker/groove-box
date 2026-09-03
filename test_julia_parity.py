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
    src = open("julia/src/GrooveboxMeumOT.jl", encoding="utf-8").read()
    for token in (":saw", ":sawtooth", ":square", ":pulse", ":triangle", ":tri",
                  ":ics", ":cos", ":cosine", ":arcisn", ":arcics", ":isn_inv"):
        assert token in src


def test_julia_source_has_explicit_operator_theory_contract():
    src = open("julia/src/GrooveboxMeumOT.jl", encoding="utf-8").read()
    assert "set_operator_theory!" in src
    assert "operator_theory_enabled" in src


def test_bridge_has_parity_report():
    assert callable(julia_bridge.parity_report)
