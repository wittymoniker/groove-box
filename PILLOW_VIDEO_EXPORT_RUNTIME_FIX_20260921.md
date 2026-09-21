# v35.20a Pillow / video-export runtime fix

- `run_hybrid.sh` now selects one Python interpreter for the whole Groovebox process.
- If host Python lacks `PIL`, Groovebox creates `.venv` with `--system-site-packages`, installs `Pillow` locally, and launches the GUI with that venv Python.
- This prevents the late `No module named PIL` failure during video/image export.
- Linux launcher delegates to `run_hybrid.sh` so direct launch and hybrid launch use the same runtime.
- FFmpeg local provisioning remains unchanged.
