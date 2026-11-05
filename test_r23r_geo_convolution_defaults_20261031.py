"""R23R functional check: preset geometric defaults follow the convolution
scheme (GROOVEBOX_R23R_CONVOLUTION_DEFAULTS_20261031) — density from the
instrument-count convolution schema, Global Convolve slider convolving
equally, and rescale on instrument-count rescale."""
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

    fixed = groovebox.MathematiciansGrooveboxApp._geo_factory()
    name = sorted(player.instrument_param_state.keys())[0]

    # Ensure the probe instrument has a fresh at-default geo instance.
    player.instrument_param_state[name]["geo"] = groovebox.MathematiciansGrooveboxApp._geo_factory()
    ps = player.instrument_param_state[name]

    # 1. At Global Convolve 0% the preset is the dry (fixed) default.
    player.spin_global_convolve.setValue(0.0)
    app.processEvents()
    preset = player._geometric_convolution_defaults()
    check("slider 0% => dry fixed defaults",
          preset["cellular"]["width"] == fixed["cellular"]["width"]
          and preset["vector"]["drive"] == fixed["vector"]["drive"])

    # 2. The convolution density follows the instrument-count schema.
    n_inst = len(player.instrument_names_48)
    d = groovebox._eq_convolution_default_band_count(n_inst)
    n = d / 128.0
    player.spin_global_convolve.setValue(100.0)
    app.processEvents()
    preset = player._geometric_convolution_defaults()
    check("slider 100% => full convolution density",
          abs(preset["vector"]["drive"] - min(1.0, 0.25 + 0.5 * n)) < 1e-9,
          f"drive={preset['vector']['drive']} expected~{0.25 + 0.5 * n}")
    check("convolution density matches Edit Synth schema", d == max(2, min(128, 130 - n_inst)),
          f"count={n_inst} d={d}")

    # 3. The slider convolves equally: at-default instances follow the preset.
    check("at-default instance rescaled by slider",
          ps["geo"]["cellular"]["width"] == preset["cellular"]["width"]
          and abs(ps["geo"]["vector"]["drive"] - preset["vector"]["drive"]) < 1e-9,
          f"width={ps['geo']['cellular']['width']} drive={ps['geo']['vector']['drive']}")

    # 4. User-touched instances stay untouched.
    user_lane = dict(ps["geo"]["cellular"])
    user_lane["width"] = 33
    user_lane["height"] = 33
    ps["geo"]["cellular"] = user_lane
    player.spin_global_convolve.setValue(0.0)
    app.processEvents()
    check("user-touched instance preserved", ps["geo"]["cellular"]["width"] == 33)

    # 5. Instrument-count rescale: at-default instances follow the new density.
    player.instrument_param_state[name]["geo"] = groovebox.MathematiciansGrooveboxApp._geo_factory()
    old_count = len(player.instrument_names_48)
    new_count = max(2, old_count // 2)
    player._on_synth_count_changed(new_count)
    app.processEvents()
    ps2 = player.instrument_param_state.get(name) or {}
    geo2 = ps2.get("geo") or {}
    preset2 = player._geometric_convolution_defaults()
    check("instrument count rescaled", len(player.instrument_names_48) == new_count,
          f"{old_count} -> {len(player.instrument_names_48)}")
    check("at-default instance follows count rescale",
          geo2.get("cellular", {}).get("width") == preset2["cellular"]["width"],
          f"width={geo2.get('cellular', {}).get('width')} preset={preset2['cellular']['width']}")

    print("\n=== R23R GEO CONVOLUTION DEFAULTS ===")
    failed = 0
    for nm, cond, extra in RESULTS:
        print(("PASS: " if cond else "FAIL: ") + nm + (f" ({extra})" if extra and not cond else ""))
        failed += 0 if cond else 1
    print(f"checks={len(RESULTS)} passed={len(RESULTS)-failed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
