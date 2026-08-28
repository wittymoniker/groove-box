# Groovebox — Complete V1

## Run
```bash
pip install PyQt6 numpy sounddevice scipy
./launch_eqr.sh
# or: python3 groovebox.py
```

## What to look for

| Control | Where |
|---------|--------|
| **Visual objects 1–64** | Own row under transport (cyan “Visual objects:”) |
| **EQR** | Global slider (default 42%) — drives tensor + P/E/D path |
| **Random / Elaborate / Prev Seed** | Seed panel — complex scripts with P,E,D |
| **Step algorithm** | Prime / Square / Coprime / … → Apply |
| **Engine path / Unison blend** | Under seed panel |

## Visualizer HUD (left scope)

- Bottom: voices · seed values · **ENG:** active engines  
- Right strip: **EQR, Frac, BPM, BaseHz, VisN, EngStr, Unison, Vol** + mini meters  

## Render path

- Sequence panels blend 50/50 with master  
- EQR tensor + P/E/D modulation on mixdown  
- Scenograph item count + engine-linked fades  
- Failures stay in the status line / console — no spam popups on play  

## Spectrum
5.2 Hz – 27.5 kHz design window · preferred 96 kHz  

## Package
`groovebox.py` · `launch_eqr.sh` · `launch_eqr.py` · this README · `eqr-v1-complete.zip`


## Live DJ pair engine

This build adds two realtime performance effects:

- **GOAVA DJ MORPH** — GOAVA-derived ring/drive movement keyed to the active sound pair.
- **RANDOM PARAMETRIC DJ** — deterministic seed/BPM/pair macro movement that feels random without using RNG in the audio callback.

The 48-sound pair space contains **1,128 unique unordered pairs** (`C(48,2)`). `(A,B)` and `(B,A)` resolve to the same pair index and signature, so the pair space is non-redundant. The same pair identity drives the live audio transform and a dedicated scenograph orbit.

The DJ effects are reversible bus transforms: they do not rewrite canonical playlist composition.
