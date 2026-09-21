# Fedora 44 WebEngine/runtime repair — v35.22d

- Stop installing RPM Fusion `ffmpeg` / `ffmpeg-libs` from the required dependency transaction.
- Preserve Fedora's installed `ffmpeg-free` / `libswscale-free` stack; it already supplies ffmpeg, ffprobe and ffplay.
- Prefer Fedora's synchronized `python3-pyqt6-base`, `python3-pyqt6-webengine`, and Qt 6 WebEngine packages on Fedora 44.
- Project `.venv` continues to use `system-site-packages`; local pip Qt wheels are removed on Fedora so they cannot shadow or mismatch distro Qt libraries.
- Scientific/audio packages may still be repaired locally in `.venv`.
- `mpv`, gamescope, SDL and OpenAL are optional and cannot block the required browser/runtime repair.
- Runtime probe now prints the actual WebEngine/native loader error instead of hiding stderr.
- `run_hybrid.sh --allowerasing --skip-broken` consumes those dnf-oriented flags and does not pass them to Groovebox. `--allowerasing` is intentionally not used to mutate the host multimedia stack.
