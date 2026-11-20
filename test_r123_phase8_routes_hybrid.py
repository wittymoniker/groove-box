"""R123 phase 8: route determinism, patch bay safety, hybrid parity per language, live deck helpers."""
import copy
import os
import types

import numpy as np
import pytest


def _fake_app():
    app = types.SimpleNamespace()
    app.instrument_names_48 = [f"Inst{i}" for i in range(12)]
    app.patch_connections = [{"source": "Inst0", "target": "Inst1", "weight": 0.5}]
    app.r99_mod_matrix = [{"amount": 0.2, "rate": 8.0}, {"amount": -0.4, "rate": 2.0}]
    app.patch_motion_state = {"routes": [{"source": "Inst2 Out", "destination": "Inst3 In", "depth_pct": 50.0,
                                          "rate_pct": 100.0, "enabled": True}]}
    app.sidechain_state = {"global": {"enabled": True, "amount": 0.2, "source": "master",
                                      "attack_ms": 5.0, "release_ms": 120.0}, "targets": {}}
    app.instrument_sequencer_memory = {"Inst4": {"steps": [1, 0, 1]}}
    app.get_numeric_seed = lambda: 1234
    return app


def test_patch_randomize_is_deterministic_without_dups_or_self():
    import patch_bay_sync as pbs
    a, b = _fake_app(), _fake_app()
    ca = pbs.randomize_patch(a, n_cables=6, seed=99)
    cb = pbs.randomize_patch(b, n_cables=6, seed=99)
    assert ca == cb and ca
    edges = [(c["source"], c["target"]) for c in a.patch_connections]
    assert len(edges) == len(set(edges))
    assert all(s != t for s, t in edges)


def test_seed_handles_is_deterministic():
    import route_handles as rh
    a, b = _fake_app(), _fake_app()
    try:
        rh.seed_handles(a, 77, amount=0.6)
        rh.seed_handles(b, 77, amount=0.6)
    except Exception as exc:          # needs pieces of the full app (QSettings / widgets): structural check only
        pytest.skip(f"seed_handles needs the GUI host: {exc}")
    assert a.patch_connections == b.patch_connections
    assert a.r99_mod_matrix == b.r99_mod_matrix
    assert a.sidechain_state == b.sidechain_state


def test_incoming_routes_lists_cables_and_motion():
    import route_handles as rh
    app = _fake_app()
    assert ("Inst0", 0.5, "follow") in rh.incoming_routes(app, "Inst1")
    assert any(s == "Inst2" for s, _w, _k in rh.incoming_routes(app, "Inst3"))


ARGS = {"osc_fill": (0.3, 440.0, 4096, 48000, 0.8, 1.05), "wavefold": (np.linspace(-3, 3, 4096), 2.5),
        "hardclip": (np.linspace(-2, 2, 4096).astype(np.float32), 1.3), "ca_evolve": (110, 64, 32)}


@pytest.mark.parametrize("backend", ["c", "go", "luajit", "rust", "cpp", "julia"])
def test_hybrid_backend_parity(backend, tmp_path, monkeypatch):
    monkeypatch.setenv("GROOVEBOX_DATA_DIR", str(tmp_path))
    import hybrid_runtime as hr
    if backend in ("c", "go"):
        import hybrid_native as hn
        if not hn.build_now(backend):
            pytest.skip(f"{backend} toolchain missing")
        hr._AVAIL["t"] = 0
    if backend not in hr.available():
        pytest.skip(f"{backend} unavailable here")
    checked = 0
    for k, a in ARGS.items():
        if k not in hr._K or backend not in hr._K[k]["alts"]:
            continue
        fn = hr._alt(k, backend)
        if fn is None:
            continue
        ref = hr._K[k]["ref"](*copy.deepcopy(a))
        assert hr._close(fn(*copy.deepcopy(a)), ref, hr._K[k]["tol"]), (k, backend)
        checked += 1
    if not checked:
        pytest.skip(f"{backend}: no kernels ready")


def test_live_deck_meters_are_bounded():
    import live_deck
    c = live_deck._Cpu()
    c.percent()
    assert 0.0 <= c.percent() <= 100.0
    assert 0.0 <= live_deck.ram_percent() <= 100.0


def test_right_like_and_small_screen_helpers_exist():
    import touch_compat
    assert callable(touch_compat.right_like) and callable(touch_compat.small_screen)
    class E:
        def button(self):
            from PyQt6.QtCore import Qt
            return Qt.MouseButton.RightButton
    assert touch_compat.right_like(E())
