# Groovebox — Complete V1

## Run
```bash
pip install PyQt6 numpy sounddevice scipy
./launch_desktop.sh    # 96 kHz desktop
# or: ./launch_mobile.sh  # 48 kHz mobile
# or: python3 groovebox.py
```

## Packages
- `groovebox.zip` — full source (default)
- `desktop.zip` — desktop profile (96 kHz launch)
- `mobile.zip` — mobile profile (48 kHz launch)

## Live Parametrics column
Playlist column **Live Parametrics** stores a scriptable predicted-phase blob
(`live_params = {...}`) unifying pattern + panel + playlist state for the
master parametric engine. Live composition updates the same field.

## Notes
- Sequence amplitudes/pitches/offsets use continuous floats (any decimal).
- Engine retoggles are seed-deterministic.
- Convolve-fit blends carrier toward reference without killing per-voice identity.
