# EQR Groovebox — Final V1 (multi-channel seeds)

## Claim (practical)
Within the limits of a finite sample rate and pixel grid, **one multi-channel numeric seed field** can specify independent musical and visual control without redundant parallel UIs for the same degrees of freedom.

## Multi-channel seed syntax

```text
pitch: scale_deg(i % 12, 12, 220) * (0.5 + 0.5 * density)
amp: gate(isn(t * timewarp), 0.2 + 0.3 * morph)
gate: step(sin(t * MEUM))
visual: 0.35 + 0.65 * abs(ics(t))
hue: (i * 29 + t * 50) % 360
mod: isn(t)
```

| Channel | Affects |
|---------|---------|
| `pitch:` / `hz:` | Voice frequency / seed identity |
| `amp:` | Voice amplitude scale |
| `gate:` | On/off or partial gate |
| `visual:` | Scenograph field strength |
| `hue:` | Scenograph hue shift |
| `dens:` | Scenograph item density |
| `mod:` / `pan:` / `fx:` | Extra numeric buses |

Unlabeled text = **pitch** (legacy single-expression seeds still work).

## Run
```bash
./launch_eqr.sh
```

## Files
`groovebox.py` · `launch_eqr.sh` · `launch_eqr.py` · this README
