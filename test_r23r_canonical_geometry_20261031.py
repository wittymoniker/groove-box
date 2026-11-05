"""R23R functional check: the canonical project data write fully integrates the
four geometric synth components (GROOVEBOX_R23R_CANONICAL_GEOMETRY_20261031).

The canonical sequence runtime payload must carry Vector / Wavetable / Ball /
Cellular as first-class lanes (live instance state, mixer depths, Instance ×
Main synth / Instance × Global mod couplings, ownership flags), and the
declared canonical lanes must include them."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication  # noqa: E402

import groovebox  # noqa: E402

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), str(extra)))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    player = groovebox.MathematiciansGrooveboxApp()
    for _ in range(50):
        app.processEvents()

    name = sorted(player.instrument_param_state.keys())[0]
    # Give the probe instrument a distinctive live geometric instance.
    player.instrument_param_state[name]["geo"] = groovebox.MathematiciansGrooveboxApp._geo_factory()
    geo = player.instrument_param_state[name]["geo"]
    geo["vector"]["x"] = 0.25
    geo["wavetable"]["drawn"] = [[0.1, -0.2], [0.5, 0.8]]
    geo["cellular"]["manual_cells"] = [[1, 2]]
    geo["ball_locked"] = True

    player._canonical_write_sequence_runtime(name)
    app.processEvents()

    doc = getattr(player, "_canonical_composition_document", None) or {}
    payload = doc.get("canonical_sequence_runtime") or {}
    comps = payload.get("geometric_components")

    check("canonical write produced payload", bool(payload), str(payload.keys())[:120])
    check("geometric components present", isinstance(comps, dict), type(comps).__name__)
    if isinstance(comps, dict):
        for lane in ("vector", "wavetable", "ball", "cellular"):
            check(f"{lane} lane in write plan", isinstance(comps.get(lane), dict), str(comps.get(lane))[:80])
        check("vector carries live state", comps.get("vector", {}).get("x") == 0.25, comps.get("vector"))
        check("mixer depths in write plan",
              all(k in (comps.get("mixer") or {}) for k in ("vector", "wavetable", "ball", "cellular")),
              comps.get("mixer"))
        check("instance x main coupling in write plan", "cross_mod" in (comps.get("mixer") or {}))
        check("instance x global mod coupling in write plan", "ensemble_mod_amt" in (comps.get("mixer") or {}))
        own = comps.get("ownership") or {}
        check("ownership flags in write plan",
              own.get("ball_locked") is True and own.get("has_drawn_cycle") is True
              and own.get("has_manual_cells") is True, own)
    lanes = payload.get("canonical_lanes") or []
    check("canonical lanes declare geometry",
          all(l in lanes for l in ("vector", "wavetable", "ball", "cellular")), str(lanes)[-80:])
    # The per-instrument runtime map carries the same integrated payload.
    per_inst = doc.get("canonical_sequence_runtime_all") or {}
    check("per-instrument runtime map updated", f"{name}:0" in per_inst or any(name in k for k in per_inst),
          str(list(per_inst.keys())[:3]))

    # The project document surfaces the integrated runtime write.
    snap = player._project_snapshot()
    surfaced = snap.get("canonical_sequence_runtime") or {}
    check("project document surfaces geometric write",
          isinstance(surfaced.get("geometric_components"), dict))

    print("\n=== R23R CANONICAL GEOMETRY INTEGRATION ===")
    failed = 0
    for nm, cond, extra in RESULTS:
        print(("PASS: " if cond else "FAIL: ") + nm + (f" ({extra})" if extra and not cond else ""))
        failed += 0 if cond else 1
    print(f"checks={len(RESULTS)} passed={len(RESULTS)-failed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
