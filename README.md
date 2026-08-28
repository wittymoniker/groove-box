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


## 3.7.2 canonical-unified pass

- Runtime modules consume the same live canonical project document; JSON is a persistence/export boundary, not an internal prototype interchange format.
- Project save/load and Project JSON export use the same snapshot contract.
- Video-game classification is derived from that same canonical document, including Global Player state.
- Live DJ remains a deterministic, unordered-pair transform over canonical seed/pair identity.
- The three visual monitors below the sequencer are constrained to one equal square footprint; the scenograph no longer stretches down to the window bottom.
- Project Notes is positioned immediately to the left of the consolidated LIVE DJ panel.
- Existing export menu remains unified across WAV, MP4, WebM, AVI, and deterministic video-game script/JSON output.
