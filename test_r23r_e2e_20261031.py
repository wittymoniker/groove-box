"""R23R end-to-end verification (offscreen): Randomize All scope, save/load
round trip, instrument-count invariance, and a full-window screenshot.

GROOVEBOX_R23R_E2E_20261031
"""
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication  # noqa: E402

import groovebox  # noqa: E402

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), str(extra)))


def settle(app, seconds=2.0):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    t0 = time.time()
    player = groovebox.MathematiciansGrooveboxApp()
    settle(app, 5.0)
    check("app constructs", True, f"{time.time()-t0:.1f}s")

    # ------------------------------------------------------------------
    # 1. Randomize All: harmonic_freq stays the tuning anchor; everything
    #    else in Edit Synth + the four geometric instances + mixer/couplings
    #    is randomized.
    # ------------------------------------------------------------------
    names = sorted(player.instrument_param_state.keys())[:3]
    anchors = {}
    for i, n in enumerate(names):
        st = player.instrument_param_state[n]
        st["harmonic_freq"] = 220.0 * (i + 1)
        st["morph"] = 1.0
        st["chaos"] = 0.1
        st["fold_depth"] = 2.0
        st["harmonic_lattice"] = 0.2
        anchors[n] = 220.0 * (i + 1)
    # user-owned content that must survive Randomize All
    drawn = [(0.1, -0.2), (0.5, 0.8), (0.9, -0.4)]
    geo0 = player.instrument_param_state[names[0]].setdefault("geo", groovebox.MathematiciansGrooveboxApp._geo_factory())
    geo0["wavetable"]["drawn"] = [list(p) for p in drawn]
    geo0["ball_locked"] = True
    ball_before = dict(geo0["ball"])
    mix_before = dict(player.geometric_synth_mixer_state)
    for n in names:
        st = player.instrument_param_state[n]
        if not isinstance(st.get("geo"), dict):
            st["geo"] = groovebox.MathematiciansGrooveboxApp._geo_factory()

    player._randomize_everything_scoped()
    settle(app, 1.0)

    for n in names:
        st = player.instrument_param_state[n]
        check(f"harmonic_freq anchor fixed [{n}]", st["harmonic_freq"] == anchors[n],
              f"{st['harmonic_freq']} vs {anchors[n]}")
        check(f"morph randomized [{n}]", st["morph"] != 1.0, st["morph"])
        check(f"chaos randomized [{n}]", st["chaos"] != 0.1, st["chaos"])
        check(f"fold_depth randomized [{n}]", st["fold_depth"] != 2.0, st["fold_depth"])
        check(f"harmonic_lattice randomized [{n}]", st["harmonic_lattice"] != 0.2, st["harmonic_lattice"])
        g = st.get("geo") or {}
        check(f"geo vector randomized [{n}]", g.get("vector", {}).get("drive") not in (None, 0.5), g.get("vector"))
        check(f"geo wavetable randomized [{n}]", g.get("wavetable", {}).get("curvature") not in (None, 0.5), g.get("wavetable"))
    # ball was locked: Randomize All must respect the user lock.
    g0 = player.instrument_param_state[names[0]].get("geo") or {}
    check("ball lock respected", g0.get("ball") == ball_before, g0.get("ball"))
    check("drawn cycle preserved", g0.get("wavetable", {}).get("drawn") == [list(p) for p in drawn],
          g0.get("wavetable", {}).get("drawn"))
    mix_after = player.geometric_synth_mixer_state
    for lane in ("vector", "wavetable", "ball", "cellular"):
        check(f"mixer depth randomized [{lane}]", mix_after[lane] != mix_before[lane], mix_after[lane])
    check("instance x main coupling randomized", mix_after["cross_mod"] != mix_before["cross_mod"], mix_after["cross_mod"])
    check("instance x global mod coupling randomized",
          mix_after["ensemble_mod_amt"] != mix_before["ensemble_mod_amt"], mix_after["ensemble_mod_amt"])

    # ------------------------------------------------------------------
    # 2. Save / load round trip preserves the canonical identity.
    # ------------------------------------------------------------------
    fp_before = player._refresh_canonical_fingerprint()
    tmp = os.path.join(ROOT, "e2e_r23r_project.mcc")
    if os.path.exists(tmp):
        os.remove(tmp)
    saved_path = player._save_project_document(tmp, show_saved=False)
    ok = False
    for _ in range(600):  # save runs on the project memory worker
        app.processEvents()
        if saved_path and os.path.isfile(saved_path):
            try:
                with open(saved_path, "rb") as f:
                    if len(f.read()) > 0:
                        ok = True
                        break
            except Exception:
                pass
        time.sleep(0.05)
    check("project saved", ok, saved_path)
    if ok:
        loaded = player.open_project_path(saved_path, show_message=False)
        settle(app, 2.0)
        check("project loaded", loaded)
        fp_after = player._refresh_canonical_fingerprint()
        check("save/load preserves canonical fingerprint", fp_before == fp_after,
              f"{fp_before} vs {fp_after}")

    # ------------------------------------------------------------------
    # 3. Instrument-count invariance: unison holds with all canonicals, so
    #    every playlist row references the full active roster — the canonical
    #    write plan must not depend on the instrument count beyond the roster
    #    itself. (Raw payload equality is not the invariant: the resize also
    #    builds the canonical playlist and the unison list tracks the roster.)
    # ------------------------------------------------------------------
    def roster_refs_complete():
        rows = player._canonical_project_identity_payload()["rows"]
        roster = set(player.instrument_names_48)
        ok = bool(rows) and bool(roster)
        for r in rows:
            refs = set(str(x).rsplit(":", 1)[0] for x in (r[3] or ()))
            if refs != roster:
                ok = False
                break
        return ok, len(rows)

    old_count = len(player.instrument_names_48)
    new_count = max(2, old_count // 2)
    player._on_synth_count_changed(new_count)
    settle(app, 3.0)
    check("instrument count changed", len(player.instrument_names_48) == new_count,
          f"{old_count} -> {len(player.instrument_names_48)}")
    ok_a, rows_a = roster_refs_complete()
    check("unison rows carry all canonicals at new count", ok_a, f"rows={rows_a} roster={new_count}")
    # A second resize must keep the property: canonical output identity is
    # roster-driven, not count-history-driven.
    player._on_synth_count_changed(max(2, new_count // 2))
    settle(app, 3.0)
    ok_b, rows_b = roster_refs_complete()
    check("unison rows carry all canonicals after second resize", ok_b,
          f"rows={rows_b} roster={len(player.instrument_names_48)}")

    # ------------------------------------------------------------------
    # 4. Full-window screenshot.
    # ------------------------------------------------------------------
    player.show()
    player.resize(1600, 900)
    settle(app, 2.0)
    pix = player.grab()
    shot = os.path.join(ROOT, "e2e_full_window_r23r.png")
    ok_shot = pix.save(shot)
    check("full-window screenshot", ok_shot and pix.width() >= 1200, f"{pix.width()}x{pix.height()}")

    # ------------------------------------------------------------------
    print("\n=== R23R E2E RESULTS ===")
    failed = 0
    for name, cond, extra in RESULTS:
        print(("PASS: " if cond else "FAIL: ") + name + (f" ({extra})" if extra and not cond else ""))
        failed += 0 if cond else 1
    print(f"checks={len(RESULTS)} passed={len(RESULTS)-failed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
