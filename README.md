# Groovebox 3.7.0 — deterministic audiovisual composition engine

## Run

```bash
pip install PyQt6 numpy sounddevice scipy
./launch_desktop.sh
# or:
./launch_mobile.sh
# or:
python3 groovebox.py
```

`dj_effects.py` is the deterministic live-DJ dependency. `videogame_engine.py`
is the composition-to-game compiler used by **PLAY VIDEO GAME** and **EXPORT
GAME SCRIPT**.

## Deterministic design

The canonical path is:

`seed + composition state → labelled digest → cyclic-group residue → signal / scene / game`

The finite visual background has a **process-wide budget of 24 wave objects,
24 shape objects and 24 Meum blocks**, shared across decorated windows. Repeated
Qt decoration calls reuse the existing background instead of stacking another
field.

The scenograph uses affine permutations of `Z/n` for instrument placement. A
valid multiplier satisfies `gcd(a,n)=1`, so each finite orbit is a permutation
with no repeated index before closure. GOAVA is included in the state and
therefore changes audio, scenograph and generated-game identity together.

Noise processors use a stable hash of parameters and a persistent sample index
instead of process-global random state. Interactive randomize controls remain
explicit user actions and are not part of canonical replay.

## Live DJ / game panel

The **LIVE DJ PANEL** contains:

- GOAVA DJ MORPH
- PKP NullLock BOOST
- RANDOM PARAMETRIC DJ
- PLAY VIDEO GAME
- EXPORT GAME SCRIPT
- PKP boost/pitch/step controls

The generated game derives genre, camera, topology, social mode, mood, 1D/2D/3D
model sets, gameplay hooks and long-form variation from the live composition.
If classification selects online multiplayer, the generated start screen offers
host mode and the deterministic host port.

The game begins with a composition splash, then a start screen, then a playable
PyQt6 scene. WASD movement, deterministic music, scene motion and gameplay score
share the same composition kernel.

## Project persistence

Project JSON now stores the existing composition state plus UI handles, sequence
selection, GOAVA/DJ state, game identity/path, the deterministic-kernel contract,
and compatibility version information. Unknown newer keys are ignored on load.
