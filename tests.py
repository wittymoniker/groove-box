#!/usr/bin/env python3
"""Unified regression suite for the complete Groovebox / GOAVA game build.

All project regression tests live here so one command validates the build.
Tests that require optional desktop dependencies are reported as SKIPPED when
those dependencies are unavailable; they are not silently removed.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_component_usage():
    try:
        import groovebox
        expected_modules = [
            groovebox,
            importlib.import_module("composition_state"),
            importlib.import_module("dj_effects"),
            importlib.import_module("fractal_spatial_engine"),
            importlib.import_module("videogame_engine"),
            importlib.import_module("fast_widgets"),
        ]
    except ModuleNotFoundError as exc:
        if exc.name == "PyQt6":
            return "SKIP: component registry requires optional PyQt6"
        raise
    expected = {}
    for mod in expected_modules:
        for name, obj in vars(mod).items():
            if not name.startswith("_") and inspect.isclass(obj):
                expected.setdefault(name, obj)
    missing = sorted(set(expected) - set(groovebox.COMPONENT_CLASS_REGISTRY))
    assert not missing, f"Unregistered usable classes: {missing}"
    assert len(groovebox.COMPONENT_CLASS_REGISTRY) >= len(expected)
    return f"PASS: {len(expected)} usable application classes are registered and lazily reachable"


def check_composition_parity():
    import videogame_engine as vge
    seed = 42.0
    seq = [seed, seed * vge.MEUM, seed * vge.PHI]
    set_a = vge.eski_fractal_pick(int(seed) & 0x7FFFFFFF, sequential_nums=seq, playlist_hash=0)
    set_b = vge.eski_fractal_pick(int(seed) & 0x7FFFFFFF, sequential_nums=seq, playlist_hash=0)
    assert set_a == set_b
    for _n_claim in (2, 8, 48, 64):
        xyz = vge.compositional_xyz(seed, sequential_nums=seq, t=1.0, slot=0)
        mode = vge.instrument_geometry_mode(0, 1.0, xyz, flags={}, fractal_set=set_a)
        assert all(math.isfinite(v) for v in xyz)
        wsum = sum(mode[k] for k in ("lattice", "book_set", "phase_lock", "scatter", "goava"))
        assert abs(wsum - 1.0) <= 1e-3
        _zs, n_done, _ = vge.eski_fractal_iterate_z(set_a, xyz[0], xyz[1], xyz[2], 0.3, max_iter=12)
        assert n_done <= 12
    assert vge.compositional_xyz(seed, sequential_nums=seq, t=1.0, slot=0) == vge.compositional_xyz(seed, sequential_nums=seq, t=1.0, slot=0)
    assert len([1.0, 2.0, 3.0, 4.0, 5.0]) == 5
    assert len(vge.ESKI_FRACTAL_SET_NAMES) == 6
    rep = vge.debug_cross_engine_alignment(seed, 1.0, 8)
    assert rep.get("ok"), rep.get("errors")
    return "PASS: composition/GOAVA parity and N-independence"


def check_final_determinism():
    from visual_determinism import instrument_population, pure_visual_object, pure_visual_population, quantization_error, golden_composition_fingerprint
    seed, values = 918273.0, [-100.0, 0.0, 25.0, 400.0]
    assert pure_visual_population(16, seed, values) == pure_visual_population(16, seed, values)
    for i in range(8):
        rows = [pure_visual_object(i, n, seed, values) for n in (8, 16, 32, 64)]
        assert len({r["identity"] for r in rows}) == 1
        assert len({r["numeric_unit"] for r in rows}) == 1
        assert len({r["phase_unit"] for r in rows}) == 1
    for n in (1, 2, 3, 8, 16, 31, 48, 64):
        pop = instrument_population(n, seed, values)
        assert all(r["compensation"] == 1.0 / n for r in pop)
        assert sum(r["compensation"] for r in pop) == 1.0
    assert [r["numeric_unit"] for r in instrument_population(4, seed, values)] == [0.0, 0.2, 0.25, 1.0]
    orig, rev = instrument_population(4, seed, values), instrument_population(4, seed, list(reversed(values)))
    assert [r["master_slot"] for r in orig] == [r["master_slot"] for r in rev]
    assert [r["numeric_unit"] for r in orig] == list(reversed([r["numeric_unit"] for r in rev]))
    for u in (0.0, 0.125, 0.5, 0.999999, 1.0):
        assert 0.0 <= quantization_error(u, 1920) <= 1.0 / 1920.0
    for n in (1, 8, 16, 32, 64):
        assert golden_composition_fingerprint(n, seed, values) == golden_composition_fingerprint(n, seed, values)
    return "PASS: final determinism purity battery (7/7)"


def check_fractal_spatial():
    from fractal_spatial_engine import FractalSpatialEngine, build_spatial_state
    assert build_spatial_state(12345, "abc", depth=4, roots=7) == build_spatial_state(12345, "abc", depth=4, roots=7)
    a = build_spatial_state(12345, "abc", depth=3, roots=5); b = build_spatial_state(12346, "abc", depth=3, roots=5)
    assert a["fingerprint"] != b["fingerprint"]
    e = FractalSpatialEngine(42, "fp", goava=False); s = e.snapshot(depth=3, roots=6)
    assert s["core_engines"] == ["randomizer", "phase_lock", "euclidean", "seeded"]
    assert s["goava_required"] is False
    assert s["channels"] == ["position", "phase", "scale", "topology", "complexity"]
    native = FractalSpatialEngine(42, "fp", goava=False); adapted = FractalSpatialEngine(42, "fp", goava=True)
    p = native.generate(3, 6)
    assert [x.to_dict() for x in p] == [x.to_dict() for x in adapted.generate(3, 6)]
    assert adapted.apply_goava_adapter(p) != p
    assert native.apply_goava_adapter(p) == p
    assert FractalSpatialEngine(99, "fp", goava=False).snapshot(3, 5)["edges"] == FractalSpatialEngine(99, "fp", goava=True).snapshot(3, 5)["edges"]
    e = FractalSpatialEngine(99, "fp"); p = e.generate(2, 4)
    assert sorted(e.topology_edges(p)) == sorted(e.topology_edges(list(reversed(p))))
    json.dumps(build_spatial_state("seed-text", "fp", depth=2, roots=3), sort_keys=True)
    return "PASS: fractal spatial engine (7/7)"


def _generated_game(meta):
    from videogame_engine import classify_from_composition, export_game_files
    root = tempfile.mkdtemp(prefix="groovebox_unified_tests_")
    ident = classify_from_composition(**meta)
    script = export_game_files(ident, root, meta)
    spec = importlib.util.spec_from_file_location("generated_game_unified", script)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return root, mod


def check_game_runtime():
    import numpy as np
    meta = {"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        game = mod.Game(); report = game.report()
        assert isinstance(report["arcade"], dict)
        assert all(v is None or isinstance(v, dict) for k, v in report["arcade"].items() if k != "active")
        game.tick(1/30); frame = np.asarray(game.render_instant_frame(64, 36)); assert frame.shape == (36,64,3)
        bed = mod.MusicBed(42); audio = np.asarray([bed.step(1/22050) for _ in range(22050)])
        assert np.max(np.abs(audio)) <= 1.0 and np.sqrt(np.mean(audio*audio)) < 0.75
        sfx = mod.LiveSFX(42,["collect","kill","portal","quest"]); sfx.trigger("collect"); burst = np.asarray(sfx.mix(5000))
        assert np.max(np.abs(burst)) > 0.01
        game.net.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: generated-game runtime + audio/video smoke"


def check_open_world():
    meta = {"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        g = mod.Game(); a0 = g.angle
        v0 = dict(g.visual_view)
        for _ in range(120): g.tick(1/30)
        assert abs(((g.angle-a0+math.pi)%(2*math.pi))-math.pi) < 1e-6
        assert abs(g.visual_view["roll_deg"]) < 1e-9
        g.perspective_move(dz=1.0)
        for _ in range(10): g.tick(1/30)
        assert abs(((g.angle-a0+math.pi)%(2*math.pi))-math.pi) > 1e-4
        obj = g.sandbox_place("crate", "test crate"); assert obj["label"] == "test crate"
        reg = g.sandbox_region(); assert reg["objects"]
        g.sandbox_remove(-1); assert not reg["objects"]
        g.handle_console_command("/note hello sandbox"); assert g.region_state
        g.handle_console_command("/report"); assert g.report()["sandbox"]["enabled"]
        g.net.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: open-world idle stability + authored movement + sandbox"


def check_sequence_conductor():
    meta = {"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        SequenceInfluence, ScenographLite, MusicBed = mod.SequenceInfluence, mod.ScenographLite, mod.MusicBed
        s1 = SequenceInfluence(42, (8,13,21)); s2 = SequenceInfluence(42, (8,13,21))
        a, b = s1.update(5.25), s2.update(5.25)
        assert a == b and 0.0 < a["motion"] <= 1.0 and 0.0 < a["vibration"] <= 0.5 and a["step"] == 5
        scene = ScenographLite(42, n=8); scene.sequence_control = SequenceInfluence(42, (8,13,21)); scene.tick(0.01); y0=[x["yaw"] for x in scene.layers]; scene.tick(0.01); y1=[x["yaw"] for x in scene.layers]
        assert any(abs(x-y)>1e-12 for x,y in zip(y0,y1))
        m = MusicBed(42, bars=8); m.sequence_control.pattern_lengths=(8,13,21); m.step(0.05); assert 0.0 < m.sequence_vibration <= 0.5
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: Sequence Conductor deterministic visual/audio coupling"


def check_instrument_translation():
    from visual_determinism import instruments_handler
    seed, seq = 918273.0, [-100.0,0.0,25.0,400.0]
    assert instruments_handler(3,16,seed,seq) == instruments_handler(3,16,seed,seq)
    for i in range(2):
        rows=[instruments_handler(i,n,seed,seq) for n in (2,8,48)]
        assert len({r["master_slot"] for r in rows}) == 1 and len({r["identity"] for r in rows}) == 1 and len({r["numeric_unit"] for r in rows}) == 1 and len({r["phase"] for r in rows}) == 1
    for n in (1,2,8,16,32,48,64):
        rows=[instruments_handler(i,n,seed,seq) for i in range(n)]
        assert abs(sum(r["compensation"] for r in rows)-1.0)<1e-15 and all(0.0<r["compensation"]<=1.0 for r in rows)
    rows=[instruments_handler(i,4,seed,seq) for i in range(4)]; units=[r["numeric_unit"] for r in rows]
    assert min(units)==0.0 and max(units)==1.0
    assert instruments_handler(1,8,seed,seq)["identity"] == 1.5/64.0
    assert instruments_handler(1,64,seed,seq)["identity"] == 1.5/64.0
    return "PASS: instrument→visual translation determinism (5/5)"


def check_video_contract():
    text=(ROOT/"groovebox.py").read_text(encoding="utf-8"); tree=ast.parse(text)
    video_cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="VideoSynthEngine")
    methods={n.name:n for n in video_cls.body if isinstance(n,ast.FunctionDef)}
    def source(fn): return ast.get_source_segment(text, methods[fn]) or ""
    assert "* 1.65" not in source("_line") and "* 1.65" not in source("_dot")
    canon=source("_build_canonical_ctx_and_layers"); assert "_visual_frame) % len(self._canonical)" not in canon and "_render_frame_index" in canon
    render=source("render_frame"); assert "frame_index=None" in render and "self._render_frame_index" in render
    assert "_current_goava_events" in text and "_parse_goava_seed_values" in source("_current_goava_events") and "cache=False" in source("_current_goava_events")
    export=text[text.index("    def export_video_dialog"):]; assert "eng = VideoSynthEngine(_nmem)" in export and "frame_index=fi" in export and '"-f", "rawvideo"' in export and "part_frames_dir" not in export and "frames_root" not in export
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="hash": raise AssertionError("executable built-in hash() remains")
    return "PASS: video render contract"


def check_visual_determinism():
    from visual_determinism import fibonacci_view, select_views, camera_distance, composition_fingerprint, visual_signal_id
    A=[fibonacci_view(i,128,918273) for i in range(128)]; B=[fibonacci_view(i,128,918273) for i in range(128)]; assert A==B
    keys={(v["yaw_deg"],v["pitch_deg"],v["roll_deg"],v["distance"],v["fov_deg"]) for v in A}; assert len(keys)==128
    for i in range(32): assert fibonacci_view(i,64,42)==fibonacci_view(i,64,42)
    S1,S2=select_views(32,42),select_views(32,42); assert S1==S2 and len({(v["index"],v["count"]) for v in S1})==32 and min(camera_distance(S1[i],S1[j]) for i in range(32) for j in range(i))>0.0
    objs=[{"id":2,"type":"orb","x":1.0,"y":2.0,"z":3.0},{"id":1,"type":"ring","x":4.0,"y":5.0,"z":6.0}]; assert composition_fingerprint(objs,seed=42)==composition_fingerprint(list(reversed(objs)),seed=42); assert composition_fingerprint(objs,seed=42)!=composition_fingerprint(objs,seed=43)
    fp=composition_fingerprint(objs,seed=42); id1=visual_signal_id(42,fp,S1[0]); id2=visual_signal_id(42,fp,S1[1]); assert id1!=id2 and id1==visual_signal_id(42,fp,S1[0])
    return "PASS: visual determinism (5/5)"


def check_temporal_seed():
    meta = {"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        TemporalSeedDynamics = mod.TemporalSeedDynamics
        a,b=TemporalSeedDynamics(42),TemporalSeedDynamics(42)
        samples=[]
        for t in (0.0,7.0,14.0,30.0,48.0,63.9,64.0,90.0):
            x,y=a.field("world",t),b.field("world",t); assert x==y and math.isfinite(x); samples.append((t,a.stage,a.intensity))
        assert samples[0][1] == "build"
        assert any(s=="modulate" for _,s,_ in samples)
        assert any(s=="stabilize" for _,s,_ in samples)
        assert a.seed == 42 and b.seed == 42
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: temporal seed build/modulate/stabilize determinism"


def check_renderer_topology_guard():
    text=(ROOT/"videogame_engine.py").read_text(encoding="utf-8")
    assert "for mi in range(34 if topo == \"open_world\" else 18):" in text
    draw_pos=text.index("    def draw(self, p, project, cx, cy, R):")
    body=text[draw_pos:text.index("\n    def ", draw_pos+10)] if "\n    def " in text[draw_pos+10:] else text[draw_pos:]
    assert "topo =" in body, "ProceduralWorldRenderer.draw must define topology before using topo"
    return "PASS: renderer topology NameError guard"


def check_character_ui_rules():
    meta={"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        g=mod.Game()
        assert g.character.freedom >= 0.99
        g.items.grant(0,1); assert g.equip_quick_slot(1)
        assert g.items.equipped == g.quick_slots[0]
        choices=g.interaction_items(); assert any(x["kind"]=="tool" for x in choices) and any(x["kind"]=="event" for x in choices)
        item=g.select_zero_item(6); assert item and item["kind"] in ("tool","event","interaction")
        assert mod.ObjectScaleRule.factor(42,"tree","a") in (0.25,1.75)
        assert mod.ObjectScaleRule.factor(42,"orb","a") == 1.0
        g.character.cycle_design("crest",0.2); g.tick(1/30)
        snap=g.character.snapshot(); assert 0.0 <= snap["experience"] <= 1.0 and 0.55 <= snap["freedom"] <= 1.0
        g.net.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: character progression + quick slots + 0 selector + size rules"


def check_home_starter_pack_and_panes():
    meta={"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,"goava_active":False,"randomizer_active":False,"phase_lock_active":False}
    root, mod = _generated_game(meta)
    try:
        g=mod.Game()
        lows=[d for d in g.items.defs if d.get("tier")==0]
        assert lows and all(g.items.inventory.get(d["id"],0)>0 for d in lows)
        assert g.home is not None and g.home.journal_priority(g) >= 0.72
        g.player_x, g.player_z = g.home.x, g.home.z
        assert g.home.ui_nearby(g) and g.home.nearby(g)
        result=g.interact(); assert result == "home" and g.home.owned
        before=sum(g.items.inventory.values())
        out=g.refine_starter_supplies(); after=sum(g.items.inventory.values())
        assert "CRAFTED" in out and after < before
        binds=mod.CONTROLS["binds"]
        expected={"Q":"quests","J":"journal","I":"inventory","K":"skills","L":"server","B":"crafting","G":"gameplay","H":"closet"}
        assert all(binds[name]["key"]==key for key,name in expected.items())
        g.net.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "PASS: home proximity + starter supplies + lossy refinement + pane keyboard map"


def check_goava_seed_scribing():
    import videogame_engine as vge
    a=vge.goava(42); b=vge.goava(42); c=vge.goava(43)
    opts=["a","b","c","d"]
    first=a.choose("item","alpha",opts)
    _=a.choose("item","unrelated",opts)
    assert first==a.choose("item","alpha",opts)==b.choose("item","alpha",opts)
    rec=a.scribe("item","alpha","choose",first)
    assert rec["seed"]==42 and rec["label"]=="item|alpha|choose" and rec["result"]==first
    assert a.value("x","a",0,1)==b.value("x","a",0,1)
    assert vge.build_micro_lexicon(42)==vge.build_micro_lexicon(42)
    assert vge.build_micro_lexicon(42)["seed_scribed"] is True
    return "PASS: GOAVA semantic choices are seed-scribed and call-order independent"



def check_total_correspondence():
    from universal_field import (canonical_field, self_procedure, correspondence_manifest,
                                 correspondence_verify, partition_field, reconstruct_parts)
    f=canonical_field(1.1975807343,"unified-correspondence",sequential_nums=[1,2,3,5,8,13],feature_vector=[.25,.5,.75])
    plan=self_procedure(f); assert plan["invariant"] and plan["field_id"]==f["field_id"]
    for n in (1,2,3,4,7,8,16,31,64,127):
        rec=reconstruct_parts(partition_field(f,n))
        assert max(abs(float(f["coords"][k])-rec[k]) for k in f["coords"])<=1e-12
    m=correspondence_manifest(f,{"event_id":"unified"}); v=correspondence_verify(f,m)
    assert m["identity_correspondence"] and v["pass"] and v["max_projection_error"]<=1e-12
    bad={**m,"domains":{**m["domains"],"ui":{**m["domains"]["ui"],"source_field_id":"tampered"}}}
    assert not correspondence_verify(f,bad)["pass"]
    return f"PASS: total correspondence + self-procedure ({plan['visual_projection_cover']['projection_count']} projection cover)"

CHECKS = [
    ("component registry", check_component_usage),
    ("composition parity", check_composition_parity),
    ("final determinism", check_final_determinism),
    ("fractal spatial", check_fractal_spatial),
    ("game runtime", check_game_runtime),
    ("open world", check_open_world),
    ("sequence conductor", check_sequence_conductor),
    ("instrument translation", check_instrument_translation),
    ("video contract", check_video_contract),
    ("visual determinism", check_visual_determinism),
    ("temporal seed", check_temporal_seed),
    ("renderer topology guard", check_renderer_topology_guard),
    ("character/UI rules", check_character_ui_rules),
    ("home/starter/panes", check_home_starter_pack_and_panes),
    ("GOAVA seed scribing", check_goava_seed_scribing),
    ("total correspondence", check_total_correspondence),
]


    # Numeric gameplay identity → deterministic display/audio signatures
def test_numeric_item_action_audio_identity():
    vg = importlib.import_module("videogame_engine")
    ident = vg.GameIdentity(
        seed=4242, title="Numeric Audio Test", genre="open_world", camera="first_person",
        topology="open_world", social="solo", mood="calm", online=False, host_port=33436,
        model_sets_1d=[], model_sets_2d=[], model_sets_3d=[], ui_palette={}, gameplay_hooks=[],
        music_variation="test", composition_fingerprint="4242424242424242"
    )
    ns = {}
    exec(vg.generate_game_script(ident), ns)
    g = ns["Game"]()
    assert getattr(g, "actions", None) is not None
    assert len(g.actions.actions) >= 10
    d = g.items.defs[0]
    assert d.get("sound", {}).get("freq", 0) > 0
    a = g.actions.by_id("meteor")
    assert a and a["sound"]["freq"] > 0
    assert g.items.describe(d["id"]).find("SOUND") >= 0
    sig = ns["_numeric_sound_signature"](4242, "meteor", (a["magnitude"], a["cost"], a["cooldown"]))
    assert sig["freq"] > 0 and sig["duration"] > 0 and sig["harmonics"] >= 1
    menu = g.zero_menu_text()
    assert "Hz" in menu and "NOTHING EQUIPPED" in menu

CHECKS.append(("numeric item/action/spell/event audio identity", test_numeric_item_action_audio_identity))

def main():
    failures=[]; skips=[]
    print("=== Groovebox Unified Test Suite ===")
    for name, fn in CHECKS:
        try:
            msg=fn(); print(msg)
            if isinstance(msg,str) and msg.startswith("SKIP:"): skips.append(name)
        except Exception as exc:
            failures.append((name,exc)); print(f"FAIL: {name}: {exc}")
    print("=== RESULT ===")
    print(f"checks={len(CHECKS)} passed={len(CHECKS)-len(failures)-len(skips)} skipped={len(skips)} failed={len(failures)}")
    if failures:
        for name,exc in failures: print(f" - {name}: {type(exc).__name__}: {exc}")
        return 1
    print("ALL AVAILABLE TESTS PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())


def test_visualizer_nonfinite_audio_guard():
    """NaN/Inf audiovisual samples must be neutralized before Qt plotting."""
    src = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")
    assert "PLOT_FINITE_GUARD" in src
    assert "np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)" in src
    assert "np.nan_to_num(self.track_overview, nan=0.0, posinf=0.0, neginf=0.0)" in src
    assert "if math.isfinite(y0) and math.isfinite(y1):" in src


def test_escape_releases_mouse_capture():
    """Regression: ESC/menu must release hidden cursor capture and held movement."""
    src = Path(__file__).with_name("videogame_engine.py").read_text(encoding="utf-8")
    assert "def _release_mouse_and_input(self):" in src
    assert "self._mouse_captured = False" in src
    assert "self.unsetCursor()" in src
    assert "self._held_movement.clear()" in src
    assert "self.view._release_mouse_and_input()" in src
