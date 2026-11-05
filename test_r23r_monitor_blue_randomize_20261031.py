"""Static regression: R23R monitor blue scheme + Randomize All scope
(GROOVEBOX_R23R_MONITOR_BLUE_20261031 / GROOVEBOX_R23R_RANDOMIZE_ALL_20261031)
plus the R23R Scenograph step-preview contract (GROOVEBOX_R23R_SCENE_PREVIEW)."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
ov = (ROOT / "BUILD_ISO/app-overlay-v35.22zz/groovebox.py").read_text(encoding="utf-8")


def _class_body(name):
    start = src.index(f"class {name}(")
    nxt = re.search(r"\nclass ", src[start + 1:])
    end = start + 1 + nxt.start() if nxt else len(src)
    return src[start:end]


scope_body = _class_body("VisualOscilloscope")
spectrum_body = _class_body("SpectrumAnalyzer")

checks = {
    "overlay identical to root": src == ov,
    # --- Blue monitor scheme -------------------------------------------------
    "scope blue marker": "GROOVEBOX_R23R_MONITOR_BLUE_20261031" in src,
    "scope trace stays blue family": 'c = QColor.fromHsv(200 + (hue_shift % 45), 210, 245)' in scope_body,
    "scope ribbon stays blue": "QColor.fromHsv(215 + (hue_shift % 30), 180, 255, 140)" in scope_body,
    "scope seed ticks blue": 'hue = 200 + int((abs(v) * 13.7)) % 45' in scope_body,
    "scope label blue-white": "QColor(200,225,255,210)" in scope_body,
    "scope engine strip blue": "QColor(90, 180, 255, 160)" in scope_body,
    "scope engine strip text blue": "QColor(180, 215, 255, 200)" in scope_body,
    "spectrum seed dots blue": "QColor.fromHsv(200 + int(abs(v) * 13.7) % 45, 160, 220)" in spectrum_body,
    "no green scope engine strip": "QColor(180, 255, 200, 200)" not in scope_body,
    "no green scope meter fill": "QColor(80, 220, 160, 160)" not in scope_body,
    "no yellow scope peak marker": "QColor(255, 255, 230, 200)" not in scope_body,
    "no mint scope label": "QColor(220,255,240,210)" not in scope_body,
    "no raw seed-hue scope ticks": "int((abs(v) * 0.37) % 360)" not in scope_body,
    "no raw seed-hue spectrum dots": "int(abs(v) * 0.37) % 360" not in spectrum_body,
    # --- Randomize All scope -------------------------------------------------
    "randomize marker": "GROOVEBOX_R23R_RANDOMIZE_ALL_20261031" in src,
    "randomize block present": 'params["harmonic_lattice"] = float(rng.uniform(0.0, 1.0))' in src,
    "harmonic_freq never randomized": 'params["harmonic_freq"] = float(rng.uniform' not in src,
    "geo vector randomized": 'vec["drive"] = float(rng.uniform(0.0, 1.0))' in src,
    "geo wavetable randomized": 'wt["curvature"] = float(rng.uniform(0.25, 0.75))' in src,
    "geo ball randomized": 'ball["gravity"] = float(rng.uniform(-4.0, 4.0))' in src,
    "geo cellular randomized": 'ca["rule"] = int(rng.integers(0, 256))' in src,
    "mixer depths randomized": 'mix[lane] = float(rng.uniform(0.0, 1.0))' in src,
    "instance x main coupling randomized": 'mix["cross_mod"] = float(rng.uniform(0.0, 0.008))' in src,
    "instance x global mod coupling randomized": 'mix["ensemble_mod_amt"] = float(rng.uniform(0.0, 0.5))' in src,
    "drawn cycles stay user-owned": "# A hand-drawn cycle stays user-owned" in src,
    # --- Scenograph step preview (verify still intact) -----------------------
    "scenograph preview marker": "GROOVEBOX_R23R_SCENE_PREVIEW_20261031" in src,
    "scenograph decimal step control": "spin_scene_preview_step" in src,
    "scenograph refresh button": "btn_scene_preview_refresh" in src,
    "scenograph arrows drawn when stopped": 'if not self._transport_playing():\n            try:\n                total, step, n, rows = self._preview_geometry()\n                for rect, glyph in zip(self._arrow_rects(), ("◀", "▶")):' in src,
    "scenograph step arrows": "◀" in src and "▶" in src,
    "scenograph midpoint preview": "self.set_preview_position(k + 1.5)     # middle of the step" in src,
    "scenograph decimal position": "Preview at a decimal step position (1-based; 3.5 = middle of step 3)." in src,
    # --- Help credits --------------------------------------------------------
    "help credits list perplexity": "Perplexity (Perplexity AI)" in src,
    # --- Geometric convolution defaults (R23R) --------------------------------
    "geo convolution marker": "GROOVEBOX_R23R_CONVOLUTION_DEFAULTS_20261031" in src,
    "geo factory density mapping": 'fac["vector"]["drive"] = float(np.clip(0.25 + 0.5 * n, 0.0, 1.0))' in src,
    "geo factory uses edit-synth convolution schema": "_eq_convolution_default_band_count(int(instrument_count))" in src,
    "global convolve convolves equally": "c = (float(self.spin_global_convolve.value()) / 100.0)" in src,
    "convolve slider wired to geo rescale": "self.spin_global_convolve.valueChanged.connect(lambda *_: self._rescale_geometric_convolution_defaults())" in src,
    "ensemble resize rescales geo defaults": "_n = self._rescale_geometric_convolution_defaults()" in src,
    "geo reset uses convolution preset": 'fac = self._geometric_convolution_defaults()  # R23R convolution preset\n        if lane == "ball":' in src,
    "at-default instances only": "if all(cur.get(k) == v for k, v in ref.items() if k in cur):" in src,
}


def test_r23r_monitor_blue_randomize():
    bad = [k for k, v in checks.items() if not v]
    assert not bad, bad


if __name__ == "__main__":
    ok = True
    for k, v in checks.items():
        print(("PASS: " if v else "FAIL: ") + k)
        ok = ok and v
    sys.exit(0 if ok else 1)
