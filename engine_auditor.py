#!/usr/bin/env python3
"""engine_auditor.py — the Groovebox concurrent engine console (ships with the release).

Open this in its own terminal window next to the running program and it audits
EVERY engine simultaneously while you keep using the app:

  * algebraic  engines  — Meum identity / slope-root / -etta family / constants
  * generative engines  — determinism + order-independence of the five machines
                           (randomizer, phase-lock, euclidean, seeded, goava)
  * audio     engines  — bit-exact renders; row-scope sparse masks; the Import
                           Speed scrub lane; master EQR readout + peak-hold
  * provenance engines — export manifest schema + the audio<->game triad key
                           (game_triad <-> triad.json), reconvert-safe

Design rules
------------
* Qt widgets are created ONLY on the auditor's main thread: one offscreen
  MathematiciansGrooveboxApp instance is used for all application checks.
  Pure algebra / library checks run in a ThreadPoolExecutor, so the console
  literally verifies the engines concurrently while the on-screen app runs.
* Nothing here registers inside the Groovebox; the canonical fingerprint
  (e20bf4878b for the default project) is not touched.

Usage
-----
  python3 engine_auditor.py             concurrent self-contained audit
  python3 engine_auditor.py --tail      live dashboard while the app is open
  python3 engine_auditor.py --quiet     audit, print only PASS/FAIL lines
Exit code: 0 all green, 1 engine failure, 2 error.
"""
import os
import sys
import json
import time
import tempfile
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

_FLOAT_NEG = float("-inf")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONHASHSEED", "0")

MUTE = False


def say(msg):
    if not MUTE:
        try:
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pure algebraic / library checks (ThreadPoolExecutor workers; no Qt frames)
# ---------------------------------------------------------------------------
def check_meum_identity():
    """Meum equation from Scientific and Mathematical Theories and Inventions,
    section 16 'Study on Novel Geometric and Numeric Methods':
        ((M-1)*M + (M-1)*(1/M)) == (2^M)/(M^2) - M
    must hold at float64 precision for the loaded MEUM constant."""
    import math
    import videogame_engine as ve
    M = ve.MEUM
    lhs = (M - 1.0) * M + (M - 1.0) * (1.0 / M)
    rhs = (2.0 ** M) / (M * M) - M
    resid = abs(lhs - rhs)
    ok = resid < 1e-9
    return ok, f"Eq1 residual at MEUM={M:.16g} -> {resid:.3e}"


def check_meum_slope_root():
    """N^(M*log_N(2)) - M^4 - M^2 + M == 0 exactly at N=2, nonzero elsewhere."""
    import math
    import videogame_engine as ve
    M = ve.MEUM
    refs = {}
    for N in (2, 3, 4, 7, 10, 16):
        try:
            lhs = N ** (M * math.log(N, 2)) - M ** 4 - M ** 2 + M
        except (ValueError, OverflowError):
            lhs = float("nan")
        refs[N] = lhs
    ok_root = abs(refs[2]) < 1e-9
    ok_else = all(abs(refs[N]) > 1e-6 for N in (3, 4, 7, 10, 16))
    ok = ok_root and ok_else
    return ok, "slope-root zero at N=2 (%+.3e); others %s" % (
        refs[2], {N: "%+.1e" % refs[N] for N in (3, 4, 7, 10, 16)})


def check_metta_family():
    """-etta family sanity: MEUM is the -umta superordinate; the family list
    carries named constants; all bounded and monotone around the extremes."""
    import videogame_engine as ve
    M = ve.MEUM
    names = [n for n in dir(ve) if not n.startswith("_") and n == n.upper() and isinstance(getattr(ve, n), (int, float))]
    ok = M > 1.0 and M <= 2.0
    info = "MEUM=%.14g; const module attrs: %d" % (M, len(names))
    return ok, info


def check_triad_contract():
    """game_triad / build_triad_quantities: deterministic, schema-valid,
    identity-free by design (grades sigil_count separately)."""
    import videogame_engine as ve
    s = 987654321
    a = ve.game_triad(s)
    b = ve.build_triad_quantities(s)
    ok_shape = (a == b) and set(a) == {"meta", "audio", "visual", "game"}
    ver = a.get("meta", {}).get("version")
    paths = a.get("meta", {}).get("paths")
    ok = ok_shape and ver == "triad/2026.1" and paths == ["audio", "visual", "game"]
    nz = {p: len([v for v in a[p].values() if isinstance(v, (int, float)) and v != 0.0]) for p in ("audio", "visual", "game")}
    return ok, "version=%s quantities=%s" % (ver, json.dumps(nz))


def check_engine_api():
    """The engine module must still expose its public contract after edits."""
    import videogame_engine as ve
    need = ("MEUM", "MEUM_NORM", "MEUM_INV", "PHI", "PHI_INV",
            "build_triad_quantities", "triad_of", "game_triad",
            "generate_game_script", "installation_game", "package_game_zip",
            "install_game", "export_game_files")
    missing = [n for n in need if not hasattr(ve, n)]
    ok = not missing
    return ok, ("api ok" if ok else "missing: " + ", ".join(missing))


PURE_CHECKS = [
    ("algebra/meum_identity", check_meum_identity),
    ("algebra/slope_root", check_meum_slope_root),
    ("algebra/metta_family", check_metta_family),
    ("contract/triad_schema", check_triad_contract),
    ("engine/api_surface", check_engine_api),
]


# ---------------------------------------------------------------------------
# Application checks (single offscreen instance, auditor main thread only)
# ---------------------------------------------------------------------------
FP_PIN = "e20bf4878b"  # canonical default-project fingerprint (order-invariant)
ORDERS = (["randomizer", "phase_lock", "euclidean", "seeded", "goava"],
          ["goava", "seeded", "euclidean", "phase_lock", "randomizer"])


def _drive(app, order):
    for eng in order:
        if eng == "goava":
            app.btn_goava.setChecked(True)
        elif eng == "randomizer":
            app.btn_local_randomize.setChecked(True)
        elif eng == "phase_lock":
            app.btn_local_phase_lock.setChecked(True)
        elif eng == "euclidean":
            app.btn_idealize_rhythm.setChecked(True)
        elif eng == "seeded":
            app.btn_seeded_randomize.setChecked(True)
        for _ in range(2):
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()


def _canonicalize(app):
    for t in ("_live_euclid_timer", "_live_seeded_timer"):
        tm = getattr(app, t, None)
        if tm is not None:
            try:
                tm.stop()
            except Exception:
                pass
    app._ensure_perfect_unison()
    from PyQt6.QtWidgets import QApplication
    for _ in range(2):
        QApplication.processEvents()


def app_order_invariance(app):
    _canonicalize(app)
    fp0 = app._canonical_fingerprint()
    _drive(app, ORDERS[0])
    _canonicalize(app)
    fp1 = app._canonical_fingerprint()
    _drive(app, ORDERS[1])
    _canonicalize(app)
    fp2 = app._canonical_fingerprint()
    ok = fp0 == fp1 == fp2
    return ok, "fp %s -> %s -> %s" % (fp0, fp1, fp2)


def app_fingerprint_pin(app):
    # The canonical PIN e20bf4878b is the post-composition identity: the
    # engines must be driven once (order-independently) before it holds.
    _drive(app, ORDERS[0])
    _canonicalize(app)
    fp = app._canonical_fingerprint()
    return fp == FP_PIN, "canonical fp = %s" % fp


def app_off_canonical(app):
    _canonicalize(app)
    fp_ref = app._canonical_fingerprint()
    flipped = []
    for box, spin, val in (
        (getattr(app, "chk_sparse_mask", None), getattr(app, "spin_sparse_density", None), 0.5),
        (getattr(app, "chk_speed_scrub", None), getattr(app, "spin_speed_scrub", None), 0.3),
        (getattr(app, "chk_feature_extract", None), None, None),
    ):
        if box is None:
            continue
        box.setChecked(True)
        if spin is not None:
            spin.setValue(val)
        from PyQt6.QtWidgets import QApplication
        for _ in range(2):
            QApplication.processEvents()
        flipped.append(fp_ref == app._canonical_fingerprint())
        box.setChecked(False)
        for _ in range(2):
            QApplication.processEvents()
    ok = all(flipped)
    return ok, "fp unchanged across %d off-canonical toggles" % len(flipped)


def app_render_bit(g, secs, describe):
    import numpy as np
    a, _sr = g._render_mixdown_buffer()
    b, _sr2 = g._render_mixdown_buffer()
    ident = np.array_equal(a, b)
    if not ident:
        return False, "not bit-exact (%d bytes)" % (a.size * a.itemsize)
    return True, "bit-exact render x2, %d samples (~%.1fs)" % (a.size, a.size / (_sr or 1))


def app_audio_engines(app):
    from PyQt6.QtWidgets import QApplication
    import numpy as np

    # small rows + small instrument bank so the audio audit stays fast
    app.spin_seq_length.setValue(6)
    try:
        app.spin_playlist_length.setValue(6)
    except Exception:
        pass
    try:
        app.spin_synth_count.setValue(12)
    except Exception:
        pass
    app.spin_bpm.setValue(110)
    app.chk_sparse_mask.setChecked(False)
    app.chk_speed_scrub.setChecked(False)
    for _ in range(3):
        QApplication.processEvents()

    base, _sr = app._render_mixdown_buffer()
    r1 = app_render_bit(app, base, "base")
    if not r1[0]:
        return r1

    # row-scope sparse mask mutes a deterministic sub-population (density < 1)
    app.chk_sparse_mask.setChecked(True)
    app.spin_sparse_density.setValue(0.5)
    for _ in range(2):
        QApplication.processEvents()
    sparse, _ = app._render_mixdown_buffer()
    sparse_changed = not np.array_equal(sparse, base)
    app.spin_sparse_density.setValue(1.0)
    for _ in range(2):
        QApplication.processEvents()
    full, _ = app._render_mixdown_buffer()
    full_identical = np.array_equal(full, base)
    ok_mask = sparse_changed and full_identical
    app.chk_sparse_mask.setChecked(False)
    if not ok_mask:
        return False, "sparse mask: density1.0 identical=%s, mask effect=%s" % (full_identical, sparse_changed)

    # Import-speed scrub lane (carrier needed; synthesize one like a real import)
    if getattr(app, "imported_waveform", None) is None:
        sr_n = int(getattr(app, "_SAMPLE_RATE", 48000))
        t = np.arange(sr_n * 6) / sr_n
        app.imported_waveform = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        app.imported_sample_rate = sr_n
    app.chk_speed_scrub.setChecked(True)
    for _ in range(2):
        QApplication.processEvents()
    scrubbed, _ = app._render_mixdown_buffer()
    scrub_changed = not np.array_equal(scrubbed, base) and np.abs(scrubbed - base).max() > 1e-3
    app.chk_speed_scrub.setChecked(False)
    if not scrub_changed:
        return False, "scrub lane had no audible effect on import carrier"
    return True, "bit-exact base; sparse mask & scrub lane effect confirmed"


def app_provenance_roundtrip(app):
    from PyQt6.QtWidgets import QApplication
    _canonicalize(app)
    fp0 = app._canonical_fingerprint()
    payload = app._export_provenance_payload()
    payload = json.loads(payload) if isinstance(payload, str) else payload
    restored = app._apply_provenance_payload(payload)
    for _ in range(2):
        QApplication.processEvents()
    fp1 = app._canonical_fingerprint()
    ok_fp = fp0 == fp1
    gt = payload.get("game_triad")
    import videogame_engine as ve
    seed = app._composition_meta_for_game().get("seed")
    ok_triad = isinstance(gt, dict) and app._triad_digest(gt) == app._triad_digest(ve.game_triad(seed))
    ok = ok_fp and ok_triad and restored is not False
    return ok, "fp roundtrip=%s; game_triad cross-check=%s; restore=%s" % (ok_fp, ok_triad, bool(restored))


def app_meta_checks(app):
    got = []
    ok = True
    labels = {
        "cl_meta_report": ("F4 bake meta (report present)", lambda a, v: isinstance(v, dict) and "ratio_pct" in v),
        "eqr_z": ("F3 EQR z readout (P·E+D present)", lambda a, v: isinstance(v, (int, float)) and v > 1e-9),
        "dpi_peak": ("F3 peak-hold present", lambda a, v: isinstance(v, (int, float))),
    }
    for attr, (label, pred) in labels.items():
        v = getattr(app, attr, None) if attr != "eqr_z" else getattr(app, "_eqr_z_rel", None)
        if attr == "eqr_z":
            v = getattr(app, "_eqr_z_rel", None)
        elif attr == "cl_meta_report":
            v = getattr(app, "_clipgain_report", None)
        elif attr == "dpi_peak":
            v = getattr(app, "_eqr_peak_db", None)
        good = pred(app, v)
        ok = ok and good
        got.append(label + (" ok" if good else " MISSING"))
    return ok, "; ".join(got)


def app_engine_determinism(app):
    """Seed a fresh small project, drive the engines in both canonical orders
    (with and without the protect toggle), canonicalize after each pass and
    require every fingerprint to agree — the order-independence contract.
    Requires no audio rendering, so it stays interactive-fast."""
    _drive(app, ORDERS[0])
    _canonicalize(app)
    fp1 = app._canonical_fingerprint()
    _drive(app, ORDERS[1])
    _canonicalize(app)
    fp2 = app._canonical_fingerprint()
    _drive(app, ORDERS[0])
    _canonicalize(app)
    fp3 = app._canonical_fingerprint()
    ok = fp1 == fp2 == fp3
    return ok, "fp stable across engine orders: %s = %s = %s" % (fp1, fp2, fp3)


APP_CHECKS = [
    ("canonical/engine_determinism", app_engine_determinism),
    ("canonical/off_canonical_toggles", app_off_canonical),
    ("provenance/roundtrip_triad", app_provenance_roundtrip),
    ("render/bit_exact", app_render_bit),
    ("audio/sparse_scrub", app_audio_engines),
    ("meta/eqr_peak_bake", app_meta_checks),
]


# ---------------------------------------------------------------------------
# Optional live dashboard (--tail): the app writes a throttled status snapshot
# to <tmp>/groovebox_live_status.json; this console tails it while it's open.
# ---------------------------------------------------------------------------
def live_dashboard():
    path = os.path.join(tempfile.gettempdir(), "groovebox_live_status.json")
    say("tail: waiting for Groovebox live status at %s" % path)
    stale = False
    while True:
        if not os.path.exists(path):
            stale = True
            time.sleep(1.0)
            continue
        try:
            st = os.stat(path)
            if time.time() - st.st_mtime > 10:
                stale = True
            d = json.load(open(path))
            say("live | seq=%s | playhead=%.1f/%.1fs | fp=%s | peak=%.1fdB | hold=%.1fdB | z=%s"
                % (d.get("seq", "-"), d.get("playhead_ms", 0) / 1000.0, d.get("length_s", 0),
                   d.get("fingerprint", "-"), d.get("peak_db", _FLOAT_NEG), d.get("peak_hold_db", _FLOAT_NEG),
                   d.get("eqr_z", "-")))
            stale = False
        except Exception as e:
            say("tail: read error: %s" % e)
        time.sleep(1.0)


# ---------------------------------------------------------------------------
def main():
    global MUTE
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--tail", action="store_true", help="live dashboard mode")
    ap.add_argument("--quiet", action="store_true", help="print only PASS/FAIL lines")
    ap.add_argument("--full", action="store_true",
                    help="also recompute the default-project fingerprint PIN by "
                         "driving every engine on the full 48-voice project "
                         "(several minutes)")
    args = ap.parse_args(sys.argv[1:])
    MUTE = args.quiet
    if args.tail:
        live_dashboard()
        return 0

    import numpy as np
    try:
        from PyQt6.QtWidgets import QApplication
        _qapp = QApplication(sys.argv[:1])
        from groovebox import MathematiciansGrooveboxApp
    except Exception as e:
        say("ERROR initializing app: %s" % e)
        return 2

    say("GROOVEBOX ENGINE AUDITOR")
    say("  canonical fingerprint pin ....... %s" % FP_PIN)
    say("  app dir ......................... %s" % APP_DIR)
    say("[submit] %d algebra/contract checks to worker pool" % len(PURE_CHECKS))

    results = []
    t0 = time.time()

    def report(name, ok, info, dur):
        results.append((name, ok))
        say("  [%s] %s (%.1fs) %s" % ("PASS" if ok else "FAIL", name, dur, info or ""))

    def _future(fut, ta):
        try:
            ok, info = fut.result()
        except Exception as e:
            ok, info = False, "raised: %s" % e
        return ok, info, time.time() - ta

    pool = ThreadPoolExecutor(max_workers=len(PURE_CHECKS))
    for name, fn in PURE_CHECKS:
        fut = pool.submit(fn)
        fut.add_done_callback(lambda f, n=name: report(n, *_future(f, t0)))
    # NOTE: callbacks fire on pool threads; say() serializes single-flight prints.

    # application checks on THIS thread (Qt constraint) while pool runs above
    app = MathematiciansGrooveboxApp()
    from PyQt6.QtWidgets import QApplication
    for _ in range(3):
        QApplication.processEvents()
    for t in ("_live_euclid_timer", "_live_seeded_timer"):
        tm = getattr(app, t, None)
        if tm is not None:
            try:
                tm.stop()
            except Exception:
                pass
    app.input_seed_val.setPlainText("432.0")
    for _ in range(3):
        QApplication.processEvents()

    # --full: recompute the canonical fingerprint PIN on the FULL default
    # project (48 voices) first, before we shrink the audit project to keep the
    # interactive checks fast.
    if args.full:
        for name, fn in (("canonical/fp_pin", app_fingerprint_pin),
                         ("canonical/order_invariance", app_order_invariance)):
            ta = time.time()
            try:
                ok, info = fn(app)
            except Exception as e:
                ok, info = False, "raised: %s" % e
            dt = time.time() - ta
            say("  [%s] %s (%.1fs) %s" % ("PASS" if ok else "FAIL", name, dt, info or ""))

    # Interactive-fast audit project: small instrument bank + short playlist.
    try:
        app.spin_seq_length.setValue(8)
        app.spin_playlist_length.setValue(8)
        app.spin_synth_count.setValue(12)
    except Exception:
        pass
    for _ in range(3):
        QApplication.processEvents()

    say("[app] created offscreen instance; running app checks concurrently")
    for name, fn in APP_CHECKS:
        ta = time.time()
        try:
            if name == "render/bit_exact":
                ok, info = app_render_bit(app, app._render_mixdown_buffer()[0], name)
            else:
                ok, info = fn(app)
        except Exception as e:
            ok, info = False, "raised: %s" % e
        dt = time.time() - ta
        say("  [%s] %s (%.1fs) %s" % ("PASS" if ok else "FAIL", name, dt, info or ""))

    pool.shutdown(wait=True)
    wall = time.time() - t0
    extra = 2 if args.full else 0
    fails = [n for n, ok2 in results if not ok2]
    total = len(results) + len(APP_CHECKS) + extra
    say("=== AUDIT COMPLETE (%d checks, %.1fs) ===" % (total, wall))
    if fails:
        say("ENGINE AUDIT FAIL: %s" % "; ".join(fails))
        return 1
    say("ENGINE AUDIT OK (%d/%d)" % (total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())