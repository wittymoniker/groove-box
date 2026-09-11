# Smooth runtime + Numeric Symbols readability — 2026-09-11

## Performance / smoothness

1. **`_low_power_mode()` expanded**
   - Still respects `GROOVEBOX_LOW_POWER=0|1`.
   - New: `GROOVEBOX_SMOOTH=1` forces low-power behaviour (recommended for appliance / live HDMI use).
   - Auto-triggers when Math Symbols are ON (glyph overlays are paint-heavy).
   - Auto-triggers on ≤ 6 logical CPUs (was ≤ 4) and on ARM/aarch64 as before.

2. **Timers**
   - Symbol overlay sync: 16 ms normal → **33 ms** under low-power (≈ 30 Hz is enough for readability).
   - Live scope / spectrum update: 50 ms normal → **200 ms** under low-power (was 150 ms).

3. **Existing protections kept**
   - Math Symbols still default **OFF** (zero overlay work until toggled).
   - Decorative background still slows / drops instances under low-power.
   - Audio path remains untouched by these UI throttles.

**Recommended appliance launch**

```bash
export GROOVEBOX_SMOOTH=1
# optional hard force:
# export GROOVEBOX_LOW_POWER=1
python3 groovebox.py
# or the normal sOS / hybrid launcher
```

## Numeric Symbols readability

1. **Larger cells**
   - Widget minimum size raised (148×42, max height 52).
   - Per-glyph cell size floor raised from 20 → **26**, ceiling from 42 → **48**.

2. **Higher-contrast role colours** (`ot_symbol_notation.py`)
   - Independent variable: `#ff4d4d`
   - Independent constant: `#30d158`
   - Result: `#5ac8fa` (brighter sky blue)
   - Dependent constant: `#1c1c1e` (near-black) with guaranteed light cell fill
   - Dependent variable: `#f2f2f7` (off-white) with guaranteed dark cell fill

3. **Clearer zero**
   - Empty zero still has no count strokes, but now carries two short corner ticks so it is not confused with a blank / missing cell.

4. **Learning cue**
   - When a cell is ≥ 26 px, a tiny base-10 digit is drawn in the lower-right corner (alpha 160). This does **not** change encoding or arithmetic; it only helps the eye learn the 0–9 mapping while symbols are on.

5. **Stroke weight**
   - Slightly heavier outer box and center ring at typical sizes so strokes stay visible on HDMI and laptop panels.

## Files touched

- `ot_symbol_notation.py` — role colour palette
- `groovebox.py` — `_low_power_mode`, glyph painter, cell sizing, overlay/scope timers

## What this does *not* change

- Deterministic math / OT arithmetic
- sCode logic-math duality or process pooling ABI
- Audio callback path
- ISO / appliance build scripts (those remain as previously documented)

Copy these two files back over the corresponding paths in the release tree (and into the appliance rootfs copy under `APPLIANCE_ISO/source/rootfs/opt/groovebox/`) before rebuilding.

## Operator Theory seed-script Operations substitutions — 2026-09-11

When **Operator Theory = ON**, seed / coordinate / multi-line seed scripts and
graph scripts (instrument, domain, algorithm) now route ordinary arithmetic
operators through the book Operations substitutions:

| Python op | Routes to (OT ON) | Book rule |
|-----------|-------------------|-----------|
| `+`       | `math_add` → `ot_add`   | band-biased sum |
| `-`       | `math_sub` → `ot_sub`   | signed OT sub |
| `*`       | `math_mul` → `ot_prod`  | signed product (0·0→1) |
| `/`, `//` | `math_div` → `ot_div`   | book division |
| `**`      | `math_pow` → `ot_pow`   | same-hand / opposite-hand |
| unary `-` | `math_sub(0, x)`        | OT sign |

Implementation: deterministic AST rewrite (`_ot_rewrite_seed_ast` in
`groovebox.py`, `_ot_rewrite_graph_ast` in `graph_script_context.py`).

- OT **OFF**: trees unchanged → ordinary IEEE arithmetic (previous behaviour).
- Explicit `ot_*` / `math_*` calls remain available and unchanged.
- Named functions already present in the seed env continue to work.
- `%` (modulo) is left as ordinary Python (no distinct book remainder rule).

Files:
- `groovebox.py` — rewriter + wired into expression, coordinate, and exec paths
- `graph_script_context.py` — same rewrite for instrument/domain/algorithm scripts
