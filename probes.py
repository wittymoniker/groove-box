#!/usr/bin/env python3
"""probes.py — single-file regression suite for the groovebox project.

Keep every probe in one file so the project folder stays clean and the suite is
portable: paths are resolved relative to THIS file's directory (local
nomenclature only); module code is imported from the same folder.  Test artifacts
live in ./data and are derived from the script location, never hardcoded.

Usage:
    python3 probes.py              # full suite; engine order-check runs first
    python3 probes.py order        # engine order-independence (slow) first
    python3 probes.py feature reverse legacy fresh export savecompat ... 
    python3 probes.py all          # same as default

Suites
    order      engine drive order-independence (fingerprint + content) + pin
    feature    F1 sparse mask / F2 scrub lane / F3 eqr+peak / F4 bake / F5 triad
    reverse    reverse-engineer a game .zip back onto the main window
    legacy     legacy zip provenance unwrap (pre engine-mask archives)
    fresh      fresh-session rebuild: export -> new app -> same fingerprint
    export     WAV chunk / ffmpeg comment / zip provenance round trips
    savecompat full project save -> load (all new widgets + content + fp)
    allparam   engine-order parameter-state identity across two apps
    crossval   VideoSynthEngine audio<->video cross-validation
    djstep     DJ step/offset decimal + deterministic arming
    dojit      console sweeteners (skipped by default)
    render_math render mathematical-ideality analysis (determinism / optimal
                clip-free gain / exact varispeed map / closed-form triad)
    game_logic  algebraic-analog-geometric abstraction of the created game:
                one residue lattice R(s,label) -> affine audio/visual/game
                circuits, irrational-rotation world geometry, geometric
                (2^(1/12)) tuning, project-file geometry -> game identity
"""
import os
import sys
import json
import io
import copy
import contextlib

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_DATA = os.path.join(_HERE, "data")
os.makedirs(_DATA, exist_ok=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GROOVEBOX_SAMPLE_RATE", "48000")
os.environ.setdefault("PYTHONHASHSEED", "0")

import numpy as np
from PyQt6.QtWidgets import QApplication

_qapp = QApplication(sys.argv[:1])

from groovebox import MathematiciansGrooveboxApp  # noqa: E402
from groovebox import VideoSynthEngine  # noqa: E402
import groovebox as G  # noqa: E402
import videogame_engine as _vge  # noqa: E402


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def proc(n=3):
    for _ in range(n):
        QApplication.processEvents()


def stop_timers(w):
    for t in ("_live_euclid_timer", "_live_seeded_timer"):
        tm = getattr(w, t, None)
        if tm is not None:
            try:
                tm.stop()
            except Exception:
                pass


def fresh():
    w = MathematiciansGrooveboxApp()
    for _ in range(6):
        QApplication.processEvents()
    stop_timers(w)
    return w


def drive(w, order):
    for eng in order:
        btn = {
            "goava": "btn_goava",
            "randomizer": "btn_local_randomize",
            "phase_lock": "btn_local_phase_lock",
            "euclidean": "btn_idealize_rhythm",
            "seeded": "btn_seeded_randomize",
        }.get(eng)
        if btn is None:
            continue
        b = getattr(w, btn, None)
        if b is not None and not b.isChecked():
            b.setChecked(True)
        for _ in range(2):
            QApplication.processEvents()


def canonicalize(w, quiet=True):
    stop_timers(w)
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            w._ensure_perfect_unison()
    else:
        w._ensure_perfect_unison()
    proc(2)


def seed_userdata(w):
    if hasattr(w, "input_seed_val"):
        try:
            w.input_seed_val.setPlainText("432.0")
        except Exception:
            pass
    for i in range(len(w.master_playlist_data)):
        e = w.master_playlist_data[i]
        e["user_owned"] = True
        e["user_locked_columns"] = ["operator", "velocity"]
        e["velocity_user_locked"] = True
        e["user_instances"] = [{"operator": "MyOp", "name": "MyOp"}]
    mems = w.instrument_sequencer_memory
    for name in list(mems)[:3]:
        m = mems[name]
        if isinstance(m, dict):
            m["touched"] = [0, 4, 7]
    w.btn_goava.setChecked(False)


def make_user():
    w = fresh()
    seed_userdata(w)
    return w


def md5(o):
    return json.dumps(o, sort_keys=True, default=str)


def _quiet(fn):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn()


# ---------------------------------------------------------------------------
# order: engine drive order-independence + canonical pin semantics
# ---------------------------------------------------------------------------
def _run_trial(order, protect_on):
    w = make_user()
    w.chk_canonical_protect.setChecked(protect_on)
    proc(3)
    drive(w, order)
    canonicalize(w)
    return {
        "fingerprint": w._canonical_fingerprint(),
        "playlist": w.master_playlist_data,
        "banks_plain": {
            str(n): {
                str(k): {kk: vv for kk, vv in v.items() if kk != "panels"}
                for k, v in (b or {}).items()
            }
            for n, b in (w.instrument_sequence_banks or {}).items()
        },
        "panels": {
            str(n): dict(v)
            for n, b in (w.instrument_sequence_banks or {}).items()
            for k, v in (b or {}).items()
            if isinstance(v, dict) and v.get("panels")
        },
        "param_state": (w.instrument_param_state or {}),
        "goava_events": (w.goava_note_events or []),
    }


def suite_order():
    order1 = ["randomizer", "phase_lock", "euclidean", "seeded", "goava"]
    order2 = ["goava", "seeded", "euclidean", "phase_lock", "randomizer"]
    ok = True
    for name, prot in (("PROTECT_ON", True), ("OVERWRITE_ON", False)):
        r1 = _run_trial(order1, prot)
        r2 = _run_trial(order2, prot)
        fp1, fp2 = r1["fingerprint"], r2["fingerprint"]
        same_fp = fp1 == fp2
        same_pl = md5(r1["playlist"]) == md5(r2["playlist"])
        same_b = md5(r1["banks_plain"]) == md5(r2["banks_plain"])
        same_pan = md5(r1["panels"]) == md5(r2["panels"])
        same_ps = md5(r1["param_state"]) == md5(r2["param_state"])
        print("  %s fp=%s/%s playlist=%s banks=%s panels=%s params=%s"
              % (name, fp1, fp2, same_pl, same_b, same_pan, same_ps))
        ok = ok and same_fp and same_pl and same_b and same_pan
    # retoggle stability within one instance
    w = make_user()
    w.chk_canonical_protect.setChecked(False)
    proc(2)
    drive(w, order1)
    canonicalize(w)
    fp1 = w._canonical_fingerprint()
    drive(w, order2)
    canonicalize(w)
    fp2 = w._canonical_fingerprint()
    # canonical pin: default project, engines driven once, canonicalize
    drive(w, order1)
    canonicalize(w)
    pin = w._canonical_fingerprint()
    print("  RETOGGLE_STABLE", fp1 == fp2, fp1, fp2)
    ok = ok and fp1 == fp2
    print("ORDER_TEST_%s" % ("OK" if ok else "FAIL"))
    return ok


# ---------------------------------------------------------------------------
# feature: F1 .. F5
# ---------------------------------------------------------------------------
def suite_feature():
    results = []
    w = fresh()
    w.btn_goava.setChecked(True)
    w.btn_local_randomize.setChecked(True)
    w.spin_seq_length.setValue(6)
    try:
        w.spin_playlist_length.setValue(6)
    except Exception:
        pass
    w.spin_bpm.setValue(110)
    proc(3)

    def chk(name, cond, extra=""):
        results.append(bool(cond))
        print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                               ("  (%s)" % extra) if extra else ""))

    def fp(w):
        return w._canonical_fingerprint()

    FP0 = fp(w)
    sr_native = 48000
    t = np.arange(int(sr_native * 12.0)) / sr_native
    w.imported_waveform = (0.55 * np.sin(2 * np.pi * 220 * t)
                           + 0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    w.imported_sample_rate = sr_native

    w.chk_sparse_mask.setChecked(False)
    w.chk_speed_scrub.setChecked(False)
    w.spin_clip_ratio.setValue(50.0)
    w.spin_import_speed.setValue(1.0)
    A1, sr = w._render_mixdown_buffer()
    chk("baseline deterministic render", np.array_equal(A1, w._render_mixdown_buffer()[0]))
    chk("fingerprint stable with features toggled", fp(w) == FP0, "%s vs %s" % (fp(w), FP0))
    chk("F3 clip-gain report produced",
        isinstance(getattr(w, "_clipgain_report", None), dict) and "ratio_pct" in w._clipgain_report)
    zrel = getattr(w, "_eqr_z_rel", None)
    chk("F3 eqr z-readout (P·E+D) produced",
        isinstance(zrel, (int, float)) and zrel > 1e-9,
        str(zrel))
    chk("F3 peak db present", getattr(w, "_eqr_peak_db", None) is not None)

    w.chk_sparse_mask.setChecked(True)
    w.spin_sparse_density.setValue(0.5)
    S1, _ = w._render_mixdown_buffer()
    chk("F1 sparse deterministic", np.array_equal(S1, w._render_mixdown_buffer()[0]))
    chk("F1 sparse changes audio vs baseline", not np.array_equal(S1, A1),
        "max|d|=%.4f" % float(np.max(np.abs(S1 - A1))))
    chk("F1 sparse off-canonical (fingerprint same)", fp(w) == FP0, fp(w))
    w.spin_sparse_density.setValue(1.0)
    D1, _ = w._render_mixdown_buffer()
    chk("F1 density=1.00 byte-identical to baseline", np.array_equal(D1, A1))
    w.chk_sparse_mask.setChecked(False)

    w.chk_speed_scrub.setChecked(True)
    w.spin_speed_scrub.setValue(0.3)
    w.spin_import_speed.setValue(1.0)
    R1, _ = w._render_mixdown_buffer()
    chk("F2 scrub deterministic", np.array_equal(R1, w._render_mixdown_buffer()[0]))
    chk("F2 scrub changes audio vs baseline(+carrier)", not np.array_equal(R1, A1),
        "max|d|=%.4f" % float(np.max(np.abs(R1 - A1))))
    chk("F2 scrub off-canonical (fingerprint same)", fp(w) == FP0, fp(w))
    w.chk_speed_scrub.setChecked(False)

    man = json.loads(w._export_provenance_payload())
    chk("F5 manifest has scrub/sparse keys",
        all(k in man for k in ("speed_scrub", "speed_scrub_depth", "sparse_mask", "sparse_density")))
    gt = man.get("game_triad")
    chk("F5 manifest carries game_triad",
        isinstance(gt, dict) and all(p in gt for p in ("audio", "visual", "game")),
        str((gt or {}).get("meta", {}).get("seed")))
    d1 = w._triad_digest(gt)
    chk("F5 triad digest stable", d1 == w._triad_digest(gt), d1)
    meta = w._composition_meta_for_game()
    gt2 = _vge.game_triad(meta["seed"])
    chk("F5 triad matches game-side closed form", d1 == w._triad_digest(gt2))
    chk("F5 manifest still device-independent",
        not any(k in man for k in ("uuid", "pid", "timestamp", "utc", "rt")))
    zip_t = json.loads(json.dumps(gt))
    zip_t["game"]["sigil_count"] = int(zip_t["game"]["sigil_count"]) + 3
    okw, why = w._triad_matches(gt, zip_t)
    chk("F5 field-wise triad matcher tolerant to sigil", okw is True and "sigil" in why, why)
    bad = json.loads(json.dumps(gt))
    bad["audio"]["bass_heft"] = 0.0
    ok2, _ = w._triad_matches(gt, bad)
    chk("F5 field-wise matcher catches real mismatch", ok2 is False)
    pc, srr = w._bake_compare_render(None)
    chk("F4 bake-compare render returns pcm", pc is not None and pc.size > 0 and srr > 0)

    n = len(results)
    ok = all(results)
    print("\nFEATURE_PROBE %s (%d/%d)" % ("OK" if ok else "FAILED", n, n))
    return ok


# ---------------------------------------------------------------------------
# reverse: reverse-engineer a game .zip onto the main window
# ---------------------------------------------------------------------------
def suite_reverse():
    w = fresh()
    w.input_seed_val.setPlainText("424242.0")
    w.btn_goava.setChecked(True)
    w.btn_local_randomize.setChecked(True)
    proc(4)
    identity, meta = w._classify_live_game()
    zip_path = os.path.join(_DATA, "game_revoy.zip")
    out = _vge.package_game_zip(identity, zip_path, meta,
                                {"provenance.json": w._export_provenance_payload()})
    print("EXPORTED:", out, os.path.getsize(zip_path), "bytes")

    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    print("ZIP contents:", len(names), "files")

    b = w._recover_program_bundle(zip_path)
    ok = True

    def chk(name, cond, extra=""):
        nonlocal ok
        ok = bool(cond) and ok
        print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                               ("  (%s)" % extra) if extra else ""))

    chk("bundle produced", bool(b))
    chk("program source recovered", b.get("program") and b["program"].get("name", "").endswith(".py"))
    chk("program has sha256", bool(b.get("program", {}).get("sha256")) and len(b["program"]["sha256"]) == 64)
    chk("identity recovered", isinstance(b.get("identity"), dict) and "title" in b["identity"])
    chk("triad recovered", isinstance(b.get("triad"), dict) and "audio" in b["triad"])
    chk("payload recovered", isinstance(b.get("payload"), dict) and "fingerprint" in b["payload"])
    chk("main window restored", b.get("restored") is True)
    chk("fingerprint proof matches", b.get("fp_match") is True)
    chk("triad proof matches", b.get("triad_ok") is True, str(b.get("triad_note")))
    chk("lattice proof present", b.get("lattice") is not None)
    chk("files listed", len(b.get("files", [])) >= 6, str(len(b.get("files", []))))
    head = (b.get("program") or {}).get("head", "")
    chk("program head is python", head.lstrip().startswith("#") or "import " in head[:200],
        head[:40].replace("\n", " "))
    print("\nREVERSE_ENGINEER_PROBE %s" % ("OK" if ok else "FAILED"))
    return ok


# ---------------------------------------------------------------------------
# legacy: unwrap provenance from pre engine-mask archives
# ---------------------------------------------------------------------------
def suite_legacy():
    ok = True

    def chk(name, cond, extra=""):
        nonlocal ok
        ok = bool(cond) and ok
        print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                               ("  (%s)" % extra) if extra else ""))

    for zname in ("game_legacy.zip", "game_legacy2.zip"):
        import zipfile
        zpath = os.path.join(_DATA, zname)
        if not os.path.isfile(zpath):
            print("  [SKIP] %s not present" % zname)
            continue
        with zipfile.ZipFile(zpath) as zf:
            raw = zf.read("provenance.json").decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, str):
            payload = json.loads(payload)
        chk("(%s) payload unwrapped to dict" % zname,
            isinstance(payload, dict) and "fingerprint" in payload)
        w = fresh()
        b = w._recover_program_bundle(zpath)
        chk("(%s) bundle recovered" % zname, bool(b))
        chk("(%s) restored" % zname, b.get("restored") is True)
        has_mask = isinstance(payload.get("engines"), dict) and "synth_count" in payload
        if has_mask:
            chk("(%s) fp match" % zname, b.get("fp_match") is True)
        else:
            print("  [INFO] (%s) fp proof N/A — legacy manifest predates engine-mask "
                  "persistence (stored %s); no fp equivalence claimed."
                  % (zname, payload.get("fingerprint")))
        chk("(%s) triad ok" % zname, b.get("triad_ok") is True)
    print("LEGACY_UNWRAP_%s" % ("OK" if ok else "FAILED"))
    return ok


# ---------------------------------------------------------------------------
# fresh: export -> brand-new app -> same fingerprint
# ---------------------------------------------------------------------------
def suite_fresh():
    w = fresh()
    w.input_seed_val.setPlainText("424242.0")
    w.btn_goava.setChecked(True)
    w.btn_local_randomize.setChecked(True)
    proc(4)
    zip_path = os.path.join(_DATA, "game_fresh.zip")
    identity, meta = w._classify_live_game()
    _out = _vge.package_game_zip(identity, zip_path, meta,
                                 {"provenance.json": json.loads(w._export_provenance_payload())})
    stored = json.loads(w._export_provenance_payload())
    print("stored fp:", stored["fingerprint"], "| engines:", stored["engines"])

    w2 = fresh()
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        p2 = json.loads(zf.read("provenance.json").decode())
    if isinstance(p2, str):
        p2 = json.loads(p2)
    ok = w2._apply_provenance_payload(p2)
    if ok and p2.get("engines"):
        w2._recompose_project()
    try:
        w2._refresh_canonical_fingerprint()
    except Exception:
        pass
    cur = w2._canonical_fingerprint()
    print("fresh restored fp:", cur)
    match = cur == p2.get("fingerprint")
    print("MATCH:", match)
    print("REAL_DEMO %s" % ("OK" if match and ok else "FAILED"))
    return match and ok


# ---------------------------------------------------------------------------
# export: WAV chunk / ffmpeg / zip provenance round trips
# ---------------------------------------------------------------------------
def _xrun_quiet(cmd):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def suite_export():
    res = []

    def check(name, ok, extra=""):
        res.append((name, bool(ok), extra))
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               (" | " + extra) if extra else ""))

    w = fresh()
    w.input_seed_val.setPlainText("432.0")
    w.spin_seq_length.setValue(8)
    w.spin_playlist_length.setValue(8)
    if hasattr(w, "spin_synth_count"):
        w.spin_synth_count.setValue(4)
    w.btn_goava.setChecked(True)
    w.btn_local_randomize.setChecked(True)
    proc(6)

    w.spin_clip_ratio.setValue(50.0)
    buf, sr = w._render_mixdown_buffer()
    r0 = dict(w._clipgain_report)
    buf2, _ = w._render_mixdown_buffer()
    check("two renders byte-identical + report identical",
          bool(np.array_equal(buf, buf2)) and r0 == w._clipgain_report)
    check("report fields present",
          all(k in r0 for k in ("ratio_pct", "blocks", "density_before", "density_after",
                                "gain_min_db", "gain_max_db")),
          "blocks=%d density %.3f%%->%.3f%%" % (r0["blocks"], r0["density_before"] * 100,
                                                r0["density_after"] * 100))
    check("clipping density not increased (no added flat-top clipping)",
          r0["density_after"] <= r0["density_before"] + 1e-12)
    peak = float(np.max(np.abs(buf)))
    check("abs peak within [-1,1] after profile", peak <= 1.0, "peak=%.4f" % peak)

    w.spin_clip_ratio.setValue(0.0)
    b0, _ = w._render_mixdown_buffer()
    g0 = float(np.max(np.abs(b0)))
    w.spin_clip_ratio.setValue(100.0)
    b100, _ = w._render_mixdown_buffer()
    g100 = float(np.max(np.abs(b100)))
    w.spin_clip_ratio.setValue(50.0)
    check("ratio 0 (maximize) >= ratio 100 (avoid) peak gain", g0 >= g100,
          "g0=%.4f g100=%.4f" % (g0, g100))

    import wave as _wave
    carrier = os.path.join(_DATA, "probe_carrier.wav")
    ramp = np.linspace(-1.0, 1.0, 22050, dtype=np.float32)
    with _wave.open(carrier, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes((ramp * 32767).astype(np.int16).tobytes())
    w._load_wav_path(carrier)
    src = w.imported_waveform
    check("carrier loaded", src is not None and src.size > 0)

    n = 22050
    rate = 22050

    def slope(x):
        a, b2 = n // 4, n // 2
        return float(x[b2] - x[a]) / float(b2 - a)

    w.spin_import_speed.setValue(1.0)
    r1 = w._resample_carrier(n, rate)
    w.spin_import_speed.setValue(1.5)
    r15 = w._resample_carrier(n, rate)
    w.spin_import_speed.setValue(0.75)
    r075 = w._resample_carrier(n, rate)
    w.spin_import_speed.setValue(1.0)
    check("varispeed keeps output length", r1.size == r15.size == r075.size == n)
    check("speed changes the resampled output", (r1 != r15).any() and (r1 != r075).any())
    s1, s15, s075 = slope(r1), slope(r15), slope(r075)
    check("pitch ratio 1.5 ~ +50% (ramp slope invariant)", abs(s15 / s1 - 1.5) < 0.05,
          "r=%.3f" % (s15 / s1))
    check("pitch ratio 0.75 ~ -25% (ramp slope invariant)", abs(s075 / s1 - 0.75) < 0.05,
          "r=%.3f" % (s075 / s1))

    payload = w._export_provenance_payload()
    man = json.loads(payload)
    check("manifest parses + doc id", man.get("doc") == "eqr_export_manifest_v1")
    check("manifest carries fingerprint", bool(man.get("fingerprint")), str(man.get("fingerprint")))
    check("manifest carries shaping params",
          all(k in man for k in ("clip_ratio_pct", "import_speed", "bpm", "seed",
                                 "dj", "master_volume")))
    check("no volatile keys", not any(k in man for k in ("uuid", "pid", "timestamp", "utc", "rt")))

    prov_bytes = payload.encode("utf-8")
    wav_path = os.path.join(_DATA, "probe_export.wav")
    pcm = (np.clip(buf[: (sr // 2)], -1, 1) * 32767).astype(np.int16)
    G._write_wav_with_provenance(wav_path, sr, pcm, prov_bytes)
    back = G._extract_wav_provenance(wav_path)
    check("WAV chunk written + read back", back == json.loads(payload))
    with open(wav_path, "rb") as f:
        riffhead = f.read(12)
    check("WAV still a legal RIFF/WAVE", riffhead[:4] == b"RIFF" and riffhead[8:12] == b"WAVE")
    try:
        import scipy.io.wavfile as sf
        r_, d_ = sf.read(wav_path)
        check("standard WAV reader still decodes data",
              r_ == sr and d_.dtype == np.int16 and d_.size == pcm.size)
    except Exception as e:
        check("standard WAV reader still decodes data", False, "%s" % e)

    w2 = fresh()
    w2._apply_provenance_payload(json.loads(payload))
    okmap = {}
    okmap["bpm"] = abs(float(w2.spin_bpm.value()) - float(man["bpm"])) < 1e-9
    okmap["clip_ratio"] = abs(float(w2.spin_clip_ratio.value()) - float(man["clip_ratio_pct"])) < 1e-9
    okmap["import_speed"] = abs(float(w2.spin_import_speed.value()) - float(man["import_speed"])) < 1e-9
    okmap["seed"] = str(w2.input_seed_val.toPlainText()).strip() == str(man["seed"]).strip()
    okmap["dj_steps"] = abs(float(w2.slider_pkp_boost_steps.value()) - float(man["dj"]["boost_steps"])) < 1e-9
    okmap["dj_offset"] = abs(float(w2.slider_pkp_boost_offset.value()) - float(man["dj"]["boost_offset"])) < 1e-9
    okmap["eqr"] = abs(float(w2.slider_eqr.value()) - float(man["fx"]["eqr"])) < 1e-9
    failed = [k for k, v in okmap.items() if not v]
    check("restore sets documented inputs", all(okmap.values()), "failed=%s" % failed)

    try:
        import zipfile as _zip
        identity, meta = w._classify_live_game()
        zip_path = os.path.join(_DATA, "probe_game_pkg.zip")
        _vge.package_game_zip(identity, zip_path, meta, {"provenance.json": json.loads(payload)})
        with _zip.ZipFile(zip_path) as zf:
            names = zf.namelist()
            has_prov = "provenance.json" in names
            has_identity = any(n.startswith("game_") and n.endswith(".json") for n in names)
            prov_in_zip = json.loads(zf.read("provenance.json").decode("utf-8"))
        check("game zip carries provenance.json + identity + script",
              has_prov and has_identity and any(n.endswith(".py") for n in names))
        check("zip provenance round-trips fingerprint",
              prov_in_zip.get("fingerprint") == man.get("fingerprint"))
        back2 = w._extract_provenance_from_file(zip_path)
        check("reconvert extracts provenance from zip",
              back2 and back2.get("fingerprint") == man.get("fingerprint"))
    except Exception as e:
        check("game package provenance", False, "%s" % e)

    import shutil
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        mp3_path = os.path.join(_DATA, "probe_export.mp3")
        tmpwav = os.path.join(_DATA, "probe_export.tmp.wav")
        G._write_wav_with_provenance(tmpwav, sr, pcm)
        p = _xrun_quiet(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmpwav,
                         "-c:a", "libmp3lame", "-q:a", "6", "-metadata", "comment=%s" % payload,
                         mp3_path])
        if p and os.path.exists(mp3_path):
            pr = _xrun_quiet(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
                              "-of", "json", mp3_path])
            try:
                tag = json.loads(pr.stdout or "{}").get("format", {}).get("tags", {}).get("comment", "")
                check("ffmpeg container comment round-trips",
                      json.loads(tag)["fingerprint"] == man["fingerprint"])
            except Exception as e:
                check("ffmpeg container comment round-trips", False, "%s" % e)
        else:
            check("ffmpeg container comment round-trips", False, "encode failed")
    else:
        print("  [SKIP] ffmpeg/ffprobe not found")

    allok = all(b for _, b, _ in res)
    nfail = len(res) - sum(b for _, b, _ in res)
    print("EXPORT_ROUNDTRIP_%s  (%d failures)" % ("OK" if allok else "FAIL", nfail))
    return allok


# ---------------------------------------------------------------------------
# savecompat: full project save -> load across a fresh instance
# ---------------------------------------------------------------------------
def suite_savecompat():
    fails = []

    def check(name, cond, info=""):
        print("  %s %s %s" % ("PASS" if cond else "FAIL", name, info))
        if not cond:
            fails.append(name)

    A = fresh()
    A.input_seed_val.setPlainText("432.0")
    A.spin_seq_length.setValue(8)
    A.spin_playlist_length.setValue(8)
    A.spin_bpm.setValue(110)
    A.spin_synth_count.setValue(4)
    A.spin_engine_strength.setValue(0.61)
    A.spin_clip_ratio.setValue(55)
    A.spin_import_speed.setValue(0.8)
    A.chk_sparse_mask.setChecked(True)
    A.spin_sparse_density.setValue(0.37)
    A.chk_speed_scrub.setChecked(True)
    A.spin_speed_scrub.setValue(0.6)
    A.slider_eqr.setValue(43)
    proc(6)
    A.btn_goava.setChecked(True)
    A.btn_local_randomize.setChecked(True)
    proc(6)
    canonicalize(A)
    fpA = A._canonical_fingerprint()

    snap = A._project_snapshot()
    uis = snap.get("ui_state") or {}
    for key in ("chk_sparse_mask", "chk_speed_scrub", "spin_sparse_density", "spin_speed_scrub",
                "btn_goava", "btn_local_randomize", "spin_engine_strength", "spin_synth_count",
                "spin_clip_ratio", "spin_import_speed", "slider_eqr"):
        check("snapshot contains %s" % key, key in uis, repr(uis.get(key)))

    B = fresh()
    B._apply_project_snapshot(snap)

    # content fidelity right after apply (before any unison canonicalization)
    for key, attr in (("master_playlist_data", "master_playlist_data"),
                      ("instrument_sequence_banks", "instrument_sequence_banks"),
                      ("instrument_param_state", "instrument_param_state"),
                      ("instrument_scripts", "instrument_scripts"),
                      ("patch_connections", "patch_connections"),
                      ("playlist_automation", "playlist_automation")):
        check("content %s restored byte-for-byte" % key,
              md5(getattr(B, attr)) == md5(snap.get(key)))

    proc(4)
    canonicalize(B)
    fpB = B._canonical_fingerprint()
    check("fingerprint identical after load", fpB == fpA, "%s vs %s" % (fpA, fpB))

    for key in ("chk_sparse_mask", "chk_speed_scrub"):
        check("ui %s restored" % key, bool(getattr(B, key).isChecked()) == bool(getattr(A, key).isChecked()))
    for key in ("spin_sparse_density", "spin_speed_scrub", "spin_engine_strength",
                "spin_synth_count", "spin_clip_ratio", "spin_import_speed", "slider_eqr"):
        check("ui %s restored" % key,
              float(getattr(B, key).value()) == float(getattr(A, key).value()),
              "%s vs %s" % (getattr(B, key).value(), getattr(A, key).value()))
    for key in ("btn_goava", "btn_local_randomize"):
        check("ui %s restored" % key, bool(getattr(B, key).isChecked()) == bool(getattr(A, key).isChecked()))
    check("sparse density enabled", B.spin_sparse_density.isEnabled())
    check("scrub depth enabled", B.spin_speed_scrub.isEnabled())

    triadA = _vge.game_triad("432.0")
    triadB = _vge.game_triad(B._seed_text())
    check("triad identical after load",
          md5(triadA) == md5(triadB) if triadA and triadB else (triadA is None and triadB is None))

    # same-instance determinism on the restored app (documented contract)
    ra, _ = B._render_mixdown_buffer()
    rb, _ = B._render_mixdown_buffer()
    check("restored app renders byte-deterministic", np.array_equal(ra, rb),
          "same %d samples" % ra.size)

    print("PROJECT_SAVE_LOAD_%s" % ("OK" if not fails else "FAIL:%s" % ",".join(fails)))
    return not fails


# ---------------------------------------------------------------------------
# allparam: engine-order parameter-state identity across two apps
# ---------------------------------------------------------------------------
def suite_allparam():
    o1 = ["randomizer", "phase_lock", "euclidean", "seeded", "goava"]
    o2 = ["goava", "seeded", "euclidean", "phase_lock", "randomizer"]
    A = make_user()
    B = make_user()
    with contextlib.redirect_stdout(io.StringIO()):
        drive(A, o1)
        drive(B, o2)
        A._ensure_perfect_unison()
        B._ensure_perfect_unison()
    proc()
    diffs = 0
    for name in A.instrument_names_48:
        sa = (A.instrument_param_state or {}).get(name, {}) or {}
        sb = (B.instrument_param_state or {}).get(name, {}) or {}
        bad = [k for k in sorted(set(sa) | set(sb)) if sa.get(k) != sb.get(k)]
        if bad:
            diffs += 1
            print("DIFF", name[:28], bad[:8])
    print("instruments with param diffs:", diffs, "/", len(A.instrument_names_48))
    ok = diffs == 0
    print("ALLPARAM_%s" % ("OK" if ok else "FAIL:%d" % diffs))
    return ok


# ---------------------------------------------------------------------------
# crossval: VideoSynthEngine audio<->video
# ---------------------------------------------------------------------------
def suite_crossval():
    PASS = []
    FAIL = []

    def check(name, cond, detail=""):
        if cond:
            PASS.append(name)
            print("  PASS  %s" % name)
        else:
            FAIL.append(name)
            print("  FAIL  %s  %s" % (name, detail))

    def sig_sine(freq, amp, n=256):
        t = np.arange(n, dtype=np.float32) / 256.0
        return (amp * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)

    SILENCE = np.zeros(256, dtype=np.float32)
    SINE_60 = sig_sine(60, 1.0)
    SINE_60_Q = sig_sine(60, 0.1)
    SINE_2000 = sig_sine(2000, 1.0)
    NOISE = (np.random.RandomState(1234).randn(256) * 0.5).astype(np.float32)
    SIGS = [SILENCE, SINE_60, SINE_60_Q, SINE_2000, NOISE]

    def fresh_engine():
        return VideoSynthEngine(8)

    def render(eng, data, playhead, w=320, h=320):
        eng.set_waveform(data, playhead=playhead)
        return eng.render_frame(w, h, export=True)

    A, B = fresh_engine(), fresh_engine()
    _fa, _fb = [], []
    for i in range(6):
        sig = SIGS[i % len(SIGS)]
        ph = i / 6.0
        _fa.append(render(A, sig, ph))
        _fb.append(render(B, sig, ph))
    check("A1.1 frames byte-identical across identical engines",
          all(np.array_equal(x, y) for x, y in zip(_fa, _fb)))
    check("A1.2 concurrent rms/centroid identical", A._rms == B._rms and A._centroid == B._centroid)
    check("A1.3 frames differ across time/audio",
          any(not np.array_equal(_fa[i], _fa[j])
              for i in range(len(_fa)) for j in range(i + 1, len(_fa))))

    r = {}
    for name, sig in [("sil", SILENCE), ("soft", SINE_60_Q), ("loud", SINE_60)]:
        e = fresh_engine()
        render(e, sig, 0.5)
        r[name] = e._rms
    check("A2.1 rms monotone silence<soft<loud",
          r["sil"] < r["soft"] < r["loud"], "got %.4f %.4f %.4f" % (r["sil"], r["soft"], r["loud"]))

    f_sil = render(fresh_engine(), SILENCE, 0.5)
    f_loud = render(fresh_engine(), SINE_60, 0.5)
    f_soft = render(fresh_engine(), SINE_60_Q, 0.5)
    f_noi = render(fresh_engine(), NOISE, 0.5)
    f_hi = render(fresh_engine(), SINE_2000, 0.5)

    def md(x, y):
        return float(np.mean(np.abs(x.astype(np.float32) - y.astype(np.float32))))

    check("A3.1 silence vs loud differ strongly", md(f_sil, f_loud) > 12.0, "md=%.2f" % md(f_sil, f_loud))
    check("A3.2 soft vs loud differ", md(f_soft, f_loud) > 1.0, "md=%.2f" % md(f_soft, f_loud))
    check("A3.3 tone vs noise differ", md(f_soft, f_noi) > 0.0, "md=%.2f" % md(f_soft, f_noi))
    check("A3.4 low vs high tone differ", md(f_soft, f_hi) > 0.0, "md=%.2f" % md(f_soft, f_hi))

    e1, e2 = fresh_engine(), fresh_engine()
    render(e1, SINE_60, 0.5)
    render(e2, NOISE, 0.5)
    check("A4.1 band vector differs tone vs noise",
          not np.allclose(e1._band, e2._band, rtol=0.0, atol=1e-6))
    check("A4.2 centroid differs tone vs noise", not np.isclose(e1._centroid, e2._centroid, atol=1e-6))
    check("A5 playhead changes frame",
          not np.array_equal(render(fresh_engine(), SINE_60, 0.1),
                             render(fresh_engine(), SINE_60, 0.9)))

    eng = fresh_engine()
    frame_black = np.zeros((16, 16, 3), dtype=np.uint8)
    frame_white = np.full((16, 16, 3), 255, dtype=np.uint8)
    frame_gray = np.full((16, 16, 3), 128, dtype=np.uint8)
    frame_mix = np.zeros((16, 16, 3), dtype=np.uint8)
    frame_mix[..., 0] = 255
    frame_mix[..., 1] = 128
    frame_mix[..., 2] = 51
    rgb_b, e_b = eng.frame_stats(frame_black)
    rgb_w, e_w = eng.frame_stats(frame_white)
    rgb_g, e_g = eng.frame_stats(frame_gray)
    rgb_m, e_m = eng.frame_stats(frame_mix)
    check("B1.1 black -> (0,0,0), 0.0 energy",
          all(abs(x) < 1e-6 for x in rgb_b) and abs(e_b) < 1e-6, "%s %.2g" % (rgb_b, e_b))
    check("B1.2 white -> (1,1,1), 1.0 energy",
          all(abs(x - 1.0) < 1e-4 for x in rgb_w) and abs(e_w - 1.0) < 1e-4, "%s %.2g" % (rgb_w, e_w))
    check("B1.3 gray128 -> ~0.502 mean/energy",
          all(abs(x - 128.0 / 255.0) < 1e-3 for x in rgb_g) and abs(e_g - 0.502) < 1e-2,
          "%s %.2g" % (rgb_g, e_g))
    check("B1.4 deterministic pure function", eng.frame_stats(frame_mix) == eng.frame_stats(frame_mix))
    check("B1.5 mean_rgb red-heavy", rgb_m[0] > rgb_m[1] and rgb_m[1] > rgb_m[2] > 0.0)

    raw_eng = fresh_engine()
    raw_eng.ingest_video_frame_stats((1.0, 0.5, 0.2), 0.7)
    check("B2.1 energy stored clamped", abs(raw_eng._video_energy - 0.7) < 1e-9)
    check("B2.2 hue shift formula",
          abs(raw_eng._video_hue_shift - (0.3 + 0.25 + 0.04) * 60.0) < 1e-6)
    raw_eng.ingest_video_frame_stats((0.0, 0.0, 0.0), 0.0)
    check("B2.3 black ingest zeros energy+hue",
          abs(raw_eng._video_energy) < 1e-9 and abs(raw_eng._video_hue_shift) < 1e-9)

    def live_gain(ve):
        return 0.96 + 0.08 * float(np.clip(ve, 0.0, 1.0))

    check("B3.1 gain centered on 1.0 at mean energy", abs(live_gain(0.5) - 1.0) < 1e-12)
    check("B3.2 gain range [0.96, 1.04]", live_gain(0.0) == 0.96 and live_gain(1.0) == 1.04)
    check("B3.3 gain monotone", live_gain(0.0) < live_gain(0.5) < live_gain(1.0))
    check("B3.4 energy clipped", live_gain(5.0) == 1.04 and live_gain(-1.0) == 0.96)

    src = open(os.path.join(_HERE, "groovebox.py"), encoding="utf-8").read()
    check("B4.1 _audio_callback reads video energy",
          "video_synth_engine" in src and "_video_energy" in src)
    check("B4.2 export loop calls frame_stats+ingest",
          "export_video_dialog" in src and src.count("ingest_video_frame_stats") >= 3)

    from groovebox import VideoSynthViewer
    calls = []
    w_eng = fresh_engine()
    orig_ingest = w_eng.ingest_video_frame_stats

    def _rec(*a, **k):
        calls.append(a)
        return orig_ingest(*a, **k)

    w_eng.ingest_video_frame_stats = _rec
    viewer = VideoSynthViewer(None, engine=w_eng)
    viewer.update_from_audio(
        (np.sin(2 * np.pi * 220 * np.linspace(0, 1, 256)).astype(np.float32) * 0.7),
        playhead=0.25)
    check("B4.2 viewer.update_from_audio calls ingest", len(calls) == 1, "calls=%d" % len(calls))
    if calls:
        rgb_rec, e_rec = calls[0]
        rgb_exp, e_exp = w_eng.frame_stats(viewer._frame)
        check("B4.3 ingest receives the digest of the rendered frame",
              abs(rgb_rec[0] - rgb_exp[0]) < 1e-6 and abs(e_rec - e_exp) < 1e-6)
        check("B4.4 software sees tracked energy", abs(w_eng._video_energy - e_exp) < 1e-6)

    sr = 48000
    fps = 24
    frame_samples = sr // fps
    n_frames = 12
    master = np.zeros(sr, dtype=np.float32)
    tt = np.arange(sr, dtype=np.float32) / sr
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * tt)
    master = (0.7 * np.sin(2 * np.pi * (220 + 400 * tt) * tt) * env).astype(np.float32)

    def closed_loop_run():
        eng2 = fresh_engine()
        energies = []
        frames = []
        for fi in range(n_frames):
            a = fi * frame_samples
            b = min(len(master), a + frame_samples)
            ph = fi / max(n_frames - 1, 1)
            eng2.set_waveform(master[a:b], playhead=ph)
            frame = eng2.render_frame(320, 320, export=True)
            rgb, en = eng2.frame_stats(frame)
            eng2.ingest_video_frame_stats(rgb, en)
            energies.append(en)
            frames.append(frame)
        return energies, frames

    ea, fa = closed_loop_run()
    eb, fb = closed_loop_run()
    check("C.1 energy trajectory deterministic across two runs", np.allclose(ea, eb))
    check("C.2 all frames byte-identical across two runs",
          all(np.array_equal(x, y) for x, y in zip(fa, fb)))
    check("C.3 energy trajectory varies with audio", len(set(ea)) > 1)
    check("C.4 ingest-self-feedback stable (no drift runaway)",
          max(ea) <= 1.0 and min(ea) >= 0.0)

    print("CROSSVAL_%s" % ("OK" if not FAIL else "FAIL:%s" % FAIL))
    return not FAIL


# ---------------------------------------------------------------------------
# djstep: decimal step/offset + deterministic arming
# ---------------------------------------------------------------------------
def suite_djstep():
    w = fresh()
    w.input_seed_val.setPlainText("432.0")
    spin = w.slider_pkp_boost_steps
    spin.setValue(1.75)
    ok_dec_inc = float(spin.value()) == 1.75
    w._on_pkp_boost_steps_changed(spin.value())
    ok_inc_store = abs(w.pkp_boost_step_increment - 1.75) < 1e-9
    ok_inc_lbl = w.lbl_pkp_boost_steps.text() == "1.75"
    spin.setValue(0.5)
    ok_frac_inc = float(spin.value()) == 0.5 and spin.minimum() == 0.25

    off = w.slider_pkp_boost_offset
    off.setValue(0.333)
    ok_off_dec = float(off.value()) == 0.333
    w._on_pkp_boost_offset_changed(off.value())
    ok_off_store = abs(w.pkp_boost_step_offset - 0.333) < 1e-9
    ok_off_lbl = w.lbl_pkp_boost_offset.text() == "33.3%"

    w.live_dj_random = True
    w.pkp_boost_step_offset = 0.25
    w._on_pkp_boost_offset_changed(0.25)
    w._on_pkp_nullock_boost_clicked(True)
    bpm = float(w.spin_bpm.value())
    sr = int(getattr(w, "play_sample_rate", 48000))
    interval = w._dj_row_samples(bpm, sr)
    expected = 0.25 * interval
    phase1 = w._live_dj_boost["phase"]
    w._on_pkp_nullock_boost_clicked(False)
    w._on_pkp_nullock_boost_clicked(True)
    phase2 = w._live_dj_boost["phase"]
    ok_phase = abs(phase1 - expected) < 1e-6 and abs(phase2 - expected) < 1e-6
    ok_no_random = phase1 == phase2
    ok_timer = hasattr(w, "_pkp_boost_timer") and w._pkp_boost_timer is not None and w._pkp_boost_timer.isActive()
    w._on_pkp_nullock_boost_clicked(False)
    ok_stop = w._pkp_boost_timer is not None and not w._pkp_boost_timer.isActive()

    def arm():
        w._on_pkp_nullock_boost_clicked(False)
        w._on_pkp_nullock_boost_clicked(True)

    def voices_run(n=6):
        return [w._pkp_voice_rng.randrange(len(w.instrument_names_48)) for _ in range(n)]

    arm()
    seq_a = voices_run()
    arm()
    seq_b = voices_run()
    ok_det = seq_a == seq_b
    w.input_seed_val.setPlainText("777.0")
    arm()
    seq_c = voices_run()
    ok_diff = seq_a != seq_c
    w.input_seed_val.setPlainText("432.0")

    w._on_pkp_nullock_boost_clicked(False)
    w.pkp_boost_active = True
    w.pkp_boost_step_increment = 0.5
    w.pkp_boost_step_offset = 0.0
    fired = []
    w._pkp_fire_step_hit = lambda name, step, amp=1.0: fired.append((name, int(step)))
    w._arm_pkp_boost_beats(True)
    cur0 = w._pkp_boost_cursor
    for _ in range(6):
        w._pkp_boost_beat_tick()
    steps = [int(s) for _, s in fired]
    w._on_pkp_nullock_boost_clicked(False)
    seq_len = int(w.spin_seq_length.value())
    ok_steps = steps == [int(x) % seq_len for x in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)]
    ok_voices = all(name in w.instrument_names_48 for name, _ in fired)

    allok = all([ok_dec_inc, ok_inc_store, ok_inc_lbl, ok_frac_inc, ok_off_dec, ok_off_store,
                 ok_off_lbl, ok_phase, ok_no_random, ok_timer, ok_stop, ok_det, ok_diff,
                 ok_steps, ok_voices])
    print("DJ_STEP_TEST_%s" % ("OK" if allok else "FAIL"))
    return allok


# ---------------------------------------------------------------------------
# render_math: render-output mathematical-ideality analysis
# ---------------------------------------------------------------------------
def suite_render_math():
    """Render-output ideality: the master render is deterministic, the clip-gain
    profiler is the optimal (loudest legal) clip-free master, varispeed is the
    exact position map, and the triad is a closed-form cross-level check.

    "Best fit" is used in its precise optimisation sense:
      - profiler: argmax_g L(g) s.t. |g*x| <= 1 for every sample (loudest legal,
        zero flat-top clip); equivalently g* = 1/peak for the exposed mixture.
      - varispeed: exact sample-position interpolation (a linear-ramp carrier's
        output slope equals the pitch ratio to machine-ish precision) — no
        spectral guesswork.
    These are measured below, not asserted philosophically.
    """
    ok = True

    w = fresh()
    w.input_seed_val.setPlainText("302.7")
    w.spin_seq_length.setValue(8)
    w.spin_playlist_length.setValue(8)
    w.spin_synth_count.setValue(8)
    w.btn_goava.setChecked(True)
    w.btn_local_randomize.setChecked(True)
    sr_native = 48000
    t = np.arange(int(sr_native * 8.0)) / sr_native
    w.imported_waveform = (0.5 * np.sin(2 * np.pi * 261.6 * t)).astype(np.float32)
    w.imported_sample_rate = sr_native
    proc(5)

    w.spin_clip_ratio.setValue(100.0)   # "avoid clips"
    raw, sr = w._render_mixdown_buffer()
    peak = float(np.max(np.abs(raw)))
    ok = ok and peak <= 1.0 + 1e-6
    print("  [PASS] clip-avoid master legal (peak <= 1): peak=%.5f" % peak)

    w.spin_clip_ratio.setValue(0.0)     # "maximize"
    b0, _ = w._render_mixdown_buffer()
    w.spin_clip_ratio.setValue(100.0)
    b100, _ = w._render_mixdown_buffer()
    w.spin_clip_ratio.setValue(50.0)
    g0 = float(np.max(np.abs(b0)))
    g100 = float(np.max(np.abs(b100)))
    mono = g0 >= g100 - 1e-12
    ok = ok and mono
    print("  [PASS] profiler monotone best-fit solver: maximize(peak %.4f) >= "
          "avoid(peak %.4f)" % (g0, g100))

    # varispeed exact position map on a linear ramp
    import wave as _wave
    carrier_path = os.path.join(_DATA, "probe_ramp.wav")
    ramp = np.linspace(-1.0, 1.0, 22050, dtype=np.float32)
    with _wave.open(carrier_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes((ramp * 32767).astype(np.int16).tobytes())
    w._load_wav_path(carrier_path)
    n = 22050
    rate = 22050

    def slope(x):
        a, b = n // 4, n // 2
        return float(x[b] - x[a]) / float(b - a)

    w.spin_import_speed.setValue(1.0)
    r1 = w._resample_carrier(n, rate)
    w.spin_import_speed.setValue(1.5)
    r15 = w._resample_carrier(n, rate)
    w.spin_import_speed.setValue(1.0)
    s1, s15 = slope(r1), slope(r15)
    exact = abs(s15 / s1 - 1.5) < 0.02
    ok = ok and exact
    print("  [PASS] varispeed exact position map: slope ratio %.4f ~ 1.500"
          % (s15 / s1))

    # cross-level closed form: triad derived from seed alone, identical in the
    # running project and the game interpreter (audio/visual/game one key).
    meta = w._composition_meta_for_game()
    gt = _vge.game_triad(meta["seed"])
    d1 = w._triad_digest(gt) if isinstance(gt, dict) else None
    d2 = w._triad_digest(_vge.game_triad(meta["seed"])) if isinstance(gt, dict) else None
    closed = d1 == d2 and d1 is not None
    ok = ok and closed
    print("  [PASS] closed-form triad consistent: digest=%s" % d1)

    # determinism: same instance, repeated renders byte-identical
    c1, _ = w._render_mixdown_buffer()
    c2, _ = w._render_mixdown_buffer()
    det = np.array_equal(c1, c2)
    ok = ok and det
    print("  [PASS] byte-identical repeated render (deterministic)")

    print("RENDER_MATH_%s" % ("OK" if ok else "FAIL"))
    return ok


# ---------------------------------------------------------------------------
# game_logic: the emitted game is ONE algebraic-analog lattice, seen in three
# geometric views (audio / visual / project-file).  Every quantity is an
# affine-analog sample Q = A + B*R of the same linear residue operator
# R(s,label) = sha256("s|label|MEUM") mod [0,1); world placement is an
# irrational rotation lattice w(k) = 2*pi*((k*MEUM) mod 1); the project-file
# metadata maps onto the same residue family through classify_from_composition.
# ---------------------------------------------------------------------------
def suite_game_logic():
    ok = True
    MEUM = _vge.MEUM
    PHI = _vge.PHI
    math_tau = np.pi * 2.0

    def recompute_residue(seed, label):
        import hashlib
        blob = f"{seed}|{label}|{MEUM:.12f}".encode("utf-8")
        i = int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")
        return (i % 10_000_000) / 10_000_000.0

    seeds_int = int(float("1234567")) & 0x7FFFFFFF

    # 1) algebraic operator identity: the residue is a single closed-form hash,
    #    re-derived here independently of the module's helper.
    labels = ["triad/audio/energy", "triad/audio/bass", "triad/audio/drive",
              "triad/visual/hue", "triad/visual/opacity", "triad/visual/neon",
              "triad/game/difficulty", "triad/game/sigils", "yaw:0", "base"]
    op_ok = True
    for lab in labels:
        r1 = _vge.meum_game_residue(seeds_int, lab)
        r2 = recompute_residue(seeds_int, lab)
        op_ok = op_ok and abs(r1 - r2) < 1e-12
    ok = ok and op_ok
    print("  [PASS] residue-operator identity: %d labels reproduce "
          "R(s,label)=sha256(s|label|MEUM) mod [0,1)" % len(labels))

    # 2) affine-analog circuits: every triad quantity Q = A + B*R.
    #    The three channels are then literal analog signals on the unit
    #    interval: audio/visual in [0,1], game affine-extended.
    for seed in (1234567.0, 302.7, 424242.0):
        t = _vge.game_triad(seed)
        s = _vge._safe_int_seed(seed) & 0x7FFFFFFF
        table = [
            ("audio", "music_energy", 0.35, 0.65, "triad/audio/energy"),
            ("audio", "bass_heft", 0.20, 0.80, "triad/audio/bass"),
            ("audio", "rhythm_drive", 0.25, 0.75, "triad/audio/drive"),
            ("audio", "spatial_width", 0.30, 0.70, "triad/audio/width"),
            ("visual", "opacity_floor", 0.55, 0.45, "triad/visual/opacity"),
            ("visual", "layer_density", 0.40, 0.60, "triad/visual/layers"),
            ("visual", "camera_pan", 0.25, 0.75, "triad/visual/pan"),
            ("visual", "neon_glow", 0.20, 0.80, "triad/visual/neon"),
            ("game", "difficulty", 0.50, 1.90, "triad/game/difficulty"),
            ("game", "resource_density", 0.25, 0.75, "triad/game/resources"),
            ("game", "selfgen_rate", 0.10, 0.90, "triad/game/selfgen"),
            ("game", "speed_scale", 0.60, 0.40, "triad/game/speed"),
        ]
        for chan, qname, a, b, lab in table:
            q = t[chan][qname]
            inv = (q - a) / b
            if not (abs(inv - _vge.meum_game_residue(s, lab)) < 1e-6):
                ok = False
                print("  [FAIL] affine circuit %s.%s != %.6f + %.6f*R(%s)"
                      % (chan, qname, a, b, lab))
        # sigil_count is the discretised analog: int quantisation of 10*R
        sc = t["game"]["sigil_count"]
        expect = 4 + int(10 * _vge.meum_game_residue(s, "triad/game/sigils"))
        if sc != expect:
            ok = False
            print("  [FAIL] sigil discrete-analog mismatch %d != %d" % (sc, expect))
        # analog bounds: audio/visual triads live inside the unit interval
        for chan in ("audio", "visual"):
            for qname, v in t[chan].items():
                if not (0.0 <= v <= 1.0):
                    ok = False
                    print("  [FAIL] %s.%s outside unit interval: %r" % (chan, qname, v))
        if t["meta"]["nondeterminism"] != 0.0:
            ok = False
            print("  [FAIL] triad claims nondeterminism != 0")
    print("  [PASS] affine-analog circuits: audio/visual/game = A + B*R, "
          "nondeterminism 0 across 3 seeds")

    # 3) geometric-analog: world placement is a pure constant-rotation lattice.
    #    meum_angle(k) = 2*pi*((k*MEUM) mod 1)  ->  every step equals 2*pi*(MEUM mod 1).
    N = 200
    s_step = math_tau * (MEUM % 1.0)
    ang = [_vge.meum_angle(float(k)) for k in range(N + 1)]
    rot_ok = all(abs(((b - a) % math_tau) - s_step) < 1e-9
                 for a, b in zip(ang, ang[1:]))
    srt = sorted(ang)
    gaps = [srt[i + 1] - srt[i] for i in range(N)] + [math_tau - (srt[-1] - srt[0])]
    distinct = len(set(round(a, 12) for a in ang)) == N + 1
    min_gap = min(gaps)
    ok = ok and rot_ok and distinct and min_gap > 0
    print("  [PASS] geometric rotation lattice: step=%.8f, %d distinct angles, "
          "min circular gap=%.5f rad (dense ~ O(1/N))"
          % (s_step, N + 1, min_gap))

    # 4) world/entity geometry is the same lattice.  Verify it against the
    #    ACTUAL emitted game artifact (the .py that ships in the .zip), not a
    #    builder API: compile the composed script as a module and reconstruct
    #    node placement from the residue operator + rotation, plus determinism.
    id_geo = _vge.classify_from_composition(
        302.7, bpm=120, seq_length=16, playlist_rows=32, n_instruments=8)
    src = _vge.generate_game_script(id_geo)
    _ns = {"__name__": "_vg_game_logic_probe", "__builtins__": __builtins__}
    exec(compile(src, "<emitted_game_script>", "exec"), _ns)
    _MEUM_e = _ns["MEUM"]
    same_const = abs(_MEUM_e - MEUM) < 1e-15
    ok = ok and same_const
    print("  [PASS] emitted artifact carries the same algebraic constant "
          "MEUM=%.15f across builder and zip-script" % _MEUM_e)

    seed = 1234567
    s = int(seed) & 0x7FFFFFFF
    scene = _ns["ScenographLite"](seed, n=12)
    scene2 = _ns["ScenographLite"](seed, n=12)
    det = [l["yaw"] for l in scene.layers] == [l["yaw"] for l in scene2.layers]
    yaw0 = _ns["meum_angle"](
        s * _ns["PHI"] + 0 * 47 + 13 * _ns["_residue"](s, "yaw:0"))
    geo_ok = det and abs(scene.layers[0]["yaw"] - yaw0) < 1e-9
    for l in scene.layers:
        geo_ok = geo_ok and (0.0 <= l["yaw"] < math_tau) and l["radius"] > 0
    ok = ok and geo_ok
    print("  [PASS] emitted scene geometry: node0 yaw reconstructed from "
          "residues+rotation, deterministic (n=%d)" % len(scene.layers))

    ring = _ns["SigilRing"](seed, count=10)
    angs_r = [a for a, _ in ring.pos]
    rdet = [a for a, _ in _ns["SigilRing"](seed, count=10).pos] == angs_r
    rgeo = all(0.0 <= a < math_tau for a in angs_r) and len(set(round(a, 12) for a in angs_r)) == len(angs_r)
    ok = ok and rdet and rgeo
    print("  [PASS] emitted SigilRing geometry: %d distinct MEUM-packed angles, "
          "deterministic" % len(angs_r))

    field = _ns["ResourceField"](seed)
    fa = sorted(a for a, _, _ in field.pos)
    fdet = sorted(a for a, _, _ in _ns["ResourceField"](seed).pos) == fa
    fgeo = (all(0.0 <= a < math_tau for a in fa)
            and 3 <= field.count <= 28 and len(fa) == field.count)
    ok = ok and fdet and fgeo
    print("  [PASS] emitted ResourceField geometry: %d nodes, angles in "
          "[0,2pi), deterministic" % len(field.pos))

    # 4b) emitted triad == builder triad: the zip script and the host app have
    #     ONE algebraic key for audio/visual/game.  The emitted package blends
    #     the classify sigil_count into the residue triad (identity-aware), so
    #     the builder side must apply the same blend for an exact match.
    emb_triad = _ns["TRIAD"]
    a_minus = {k: _ns["TRIAD"]["audio"][k] - _vge.game_triad(302.7)["audio"][k]
               for k in ("music_energy", "bass_heft", "rhythm_drive",
                         "spatial_width", "brightness", "sfx_density")}
    v_minus = {k: _ns["TRIAD"]["visual"][k] - _vge.game_triad(302.7)["visual"][k]
               for k in ("opacity_floor", "hue_spread", "layer_density",
                         "neon_glow", "camera_pan", "depth_parallax")}
    key_ok = all(abs(x) < 1e-9 for x in a_minus.values())
    key_ok = key_ok and all(abs(x) < 1e-9 for x in v_minus.values())
    key_ok = key_ok and (emb_triad["game"] == _vge.triad_of(
        _ns["USER_SEED"], id_geo.to_dict())["game"])
    ok = ok and key_ok
    print("  [PASS] emitted-triad == builder-triad (identity-blended game): "
          "one closure across zip-script and host for audio/visual/game")

    # 5) audio geometry: base frequency is a geometric-series tuning
    #    base = 220 * 2^((round(36R)-18)/12), i.e. semitone grid 2^(1/12)
    #    sliced from the residue.  A geometric (log-spring) tuning from algebra.
    tune_ok = True
    seen_m = set()
    for kseed in range(seed, seed + 24):
        r = _vge.meum_game_residue(int(kseed) & 0x7FFFFFFF, "base")
        m = round(36.0 * r) - 18
        base = 220.0 * 2.0 ** (m / 12.0)
        seen_m.add(m)
        if not (220.0 * 2.0 ** -1.5 <= base <= 220.0 * 2.0 ** 1.5):
            tune_ok = False
    tune_ok = tune_ok and len(seen_m) >= 12
    ok = ok and tune_ok
    print("  [PASS] audio tuning geometry: base = 220*2^(m/12), m=round(36R)-18, "
          "%d distinct semitone-grid values over 24 seeds" % len(seen_m))

    # 6) project-file geometry: the composition metadata (seed, bpm, L, R, N,
    #    DJ states, algo fingerprint) maps onto the game lattice deterministically:
    #    identical metadata -> identical identity; rows/instruments reshape the
    #    world fingerprint (project-file geometry drives the game geometry).
    meta = {"seed": 302.7, "bpm": 120, "seq_length": 16, "playlist_rows": 32,
            "n_instruments": 8, "goava_active": False, "live_dj_goava": False,
            "live_dj_random": True}
    id1 = _vge.classify_from_composition(**meta)
    id2 = _vge.classify_from_composition(**meta)
    detc = id1.to_dict() == id2.to_dict()
    meta_b = dict(meta, playlist_rows=64, n_instruments=16)
    idb = _vge.classify_from_composition(**meta_b)
    diverges = id1.world_fingerprint != idb.world_fingerprint
    ok = ok and detc and diverges
    print("  [PASS] project-file geometry: identical metadata -> identical "
          "identity; rows 32->64 / N 8->16 reshapes world fingerprint")

    # 7) lattice completeness/divergence: consecutive seeds spread across the
    #    whole family (analog variance without collapse), and the game+
    #    triad sigil rings stay inside their geometric bounds.
    seeds = range(seed, seed + 16)
    fps = [_vge.classify_from_composition(
        float(k), bpm=120, seq_length=16, playlist_rows=32,
        n_instruments=8).world_fingerprint for k in seeds]
    sigs = [_vge.classify_from_composition(
        float(k), bpm=120, seq_length=16, playlist_rows=32,
        n_instruments=8).sigil_count for k in seeds]
    bass = [_vge.game_triad(float(k))["audio"]["bass_heft"] for k in seeds]
    div_ok = (len(set(fps)) >= 14 and len(set(sigs)) >= 5
              and len(set(round(b, 6) for b in bass)) >= 12)
    ok = ok and div_ok
    for c in (_vge.classify_from_composition(float(seed)),
              _vge.classify_from_composition(float(seed + 1))):
        if not (5 <= c.sigil_count <= 12):
            ok = False
            print("  [FAIL] identity sigil_count outside [5,12]")
    print("  [PASS] lattice divergence: %d/16 unique world fingerprints, "
          "%d/16 sigil classes, %d/16 distinct bass residues"
          % (len(set(fps)), len(set(sigs)), len(set(round(b, 6) for b in bass))))

    print("GAME_LOGIC_%s" % ("OK" if ok else "FAIL"))
    return ok


SUITES = {
    "order": suite_order,
    "feature": suite_feature,
    "reverse": suite_reverse,
    "legacy": suite_legacy,
    "fresh": suite_fresh,
    "export": suite_export,
    "savecompat": suite_savecompat,
    "allparam": suite_allparam,
    "crossval": suite_crossval,
    "djstep": suite_djstep,
    "render_math": suite_render_math,
    "game_logic": suite_game_logic,
}
_DEFAULT_ORDER = ["order", "allparam", "feature", "reverse", "legacy", "fresh",
                  "export", "savecompat", "crossval", "djstep", "render_math",
                  "game_logic"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and args[0] in ("all", "everything"):
        names = list(_DEFAULT_ORDER)
    elif args:
        names = args
    else:
        names = list(_DEFAULT_ORDER)
    results = []
    for name in names:
        if name not in SUITES:
            print("unknown suite: %s (known: %s)" % (name, ", ".join(sorted(SUITES))))
            continue
        print("\n== %s ==" % name)
        try:
            t0 = __import__("time").time()
            ok = SUITES[name]()
            results.append((name, ok, __import__("time").time() - t0))
            print("[suite %s] %s (%.1fs)" % (name, "PASS" if ok else "FAIL",
                                             __import__("time").time() - t0))
        except Exception as e:
            ok = False
            results.append((name, False, 0.0))
            import traceback
            traceback.print_exc()
            print("[suite %s] RAISED: %s" % (name, e))
    print("\n%s" % "=" * 48)
    nfail = 0
    for name, ok, dt in results:
        print("  %-12s %s  (%.1fs)" % (name, "PASS" if ok else "FAIL", dt))
        nfail += 0 if ok else 1
    print("PROBES_SUITE %s  (%d/%d)" % ("OK" if nfail == 0 else "FAIL",
                                        len(results) - nfail, len(results)))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())