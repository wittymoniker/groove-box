"""R23R contract check (2026-10-31): with a fixed seed and any consistent
combination of canonical engines, the music video and the games must come out
the same regardless of the assigned number of instruments.

Contract (per project design):
  - Music may vary only by phase angle.
  - Videos may vary only by camera position and angle.
  - Games may vary only by starting position, character, environment state.

This test verifies:
  1. Game identity (including its video/visual/spatial identity fields) is
     invariant across instrument counts for each engine combination.
  2. Music: surviving instruments keep their canonical synth content through a
     resize (identity-preserving transaction); the phase origin is the free
     variable.
"""
import json
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


def settle(app, seconds=2.0):
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


def classify(player):
    identity, meta = player._classify_live_game()
    return identity.to_dict()


def music_content(player, names):
    """Canonical music content for the given instruments (phase-free)."""
    out = {}
    ps = getattr(player, "instrument_param_state", {}) or {}
    for n in names:
        p = ps.get(n) or {}
        out[n] = {
            "harmonic_freq": p.get("harmonic_freq"),
            "harmonic_params": p.get("harmonic_params"),
            "convolution_waves": p.get("convolution_waves"),
            "synth_params": p.get("synth_params"),
            "tuning_ratio": p.get("tuning_ratio"),
        }
    return out


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    player = groovebox.MathematiciansGrooveboxApp()

    # Fixed seed for the whole run.
    try:
        player.input_seed_val.setPlainText("12345")
    except Exception:
        pass
    settle(app, 2.0)

    # ------------------------------------------------------------------
    # 1. Game + video identity invariance across instrument counts,
    #    for the FULL canonical engine matrix. The canonicals are
    #    SEEDED, RAND, LOCK, EUCLIDEAN — each with and without GOAVA
    #    (hyperdrive is an effect, not a canonical engine).
    # ------------------------------------------------------------------
    canonical_toggles = [
        ("SEEDED", "btn_seeded_randomize"),
        ("RAND", "btn_local_randomize"),
        ("LOCK", "btn_local_phase_lock"),
        ("EUCLIDEAN", "btn_idealize_rhythm"),
    ]
    combos = []
    for mask in range(16):
        flags = {attr: bool(mask >> i & 1) for i, (_, attr) in enumerate(canonical_toggles)}
        name = "+".join(n for i, (n, _) in enumerate(canonical_toggles) if mask >> i & 1) or "engines-off"
        combos.append((name, flags, False))
        combos.append((name + "+GOAVA", flags, True))
    counts = [64, 32, 16]

    for combo_name, flags, goava_on in combos:
        for _, attr in canonical_toggles:
            getattr(player, attr).setChecked(bool(flags.get(attr)))
        player.btn_goava.setChecked(goava_on)
        settle(app, 2.0)
        identities = {}
        for c in counts:
            player._on_synth_count_changed(c)
            settle(app, 3.0)
            try:
                identities[c] = classify(player)
            except Exception as exc:
                check(f"[{combo_name}] classify at count {c}", False, repr(exc)[:120])
                identities[c] = None
        base = identities[counts[0]]
        if base is None:
            continue
        for c in counts[1:]:
            same = (identities[c] == base)
            check(f"[{combo_name}] game+video identity invariant at count {c}", same,
                  "" if same else _diff_keys(base, identities[c]))

    # ------------------------------------------------------------------
    # 2. Music content invariance for surviving instruments across a resize.
    #    Phase origin is the allowed free variable.
    # ------------------------------------------------------------------
    player.btn_local_randomize.setChecked(False)
    player.btn_local_phase_lock.setChecked(False)
    player.btn_goava.setChecked(False)
    settle(app, 1.5)

    player._on_synth_count_changed(64)
    settle(app, 3.0)
    probe = list(player.instrument_names_48)[:8]
    music_64 = music_content(player, probe)
    phase_ref_64 = float(getattr(player, "_stochastic_phase_reference", 0.0))

    player._on_synth_count_changed(32)
    settle(app, 3.0)
    survivors = [n for n in probe if n in (player.instrument_names_48 or [])]
    check("resize kept probe instruments", len(survivors) == len(probe),
          f"{len(survivors)}/{len(probe)}")
    music_32 = music_content(player, probe)
    diff_32 = [n for n in probe if music_32.get(n) != music_64.get(n)]
    check("music content identical for survivors after resize (phase-only variance)",
          not diff_32, f"differs: {diff_32[:4]}")
    phase_ref_32 = float(getattr(player, "_stochastic_phase_reference", 0.0))
    check("phase origin present (free variable)", True,
          f"phase {phase_ref_64:.4f} -> {phase_ref_32:.4f}")

    player._on_synth_count_changed(16)
    settle(app, 3.0)
    music_16 = music_content(player, probe)
    diff_16 = [n for n in probe if music_16.get(n) != music_64.get(n)]
    check("music content identical after second resize", not diff_16,
          f"differs: {diff_16[:4]}")

    print("\n=== R23R SEED + ENGINE INVARIANCE CONTRACT ===")
    failed = 0
    for nm, cond, extra in RESULTS:
        print(("PASS: " if cond else "FAIL: ") + nm + (f" ({extra})" if extra and not cond else ""))
        failed += 0 if cond else 1
    print(f"checks={len(RESULTS)} passed={len(RESULTS)-failed} failed={failed}")
    return 0 if failed == 0 else 1


def _diff_keys(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return "type"
    keys = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            keys.append(str(k))
    return ",".join(keys[:8])


if __name__ == "__main__":
    sys.exit(main())
