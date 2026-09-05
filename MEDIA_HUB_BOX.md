# Groovebox Media Hub box deployment

This build is prepared for Raspberry Pi 4/5 and Debian/Ubuntu mini PCs. Run `./install_media_hub_box.sh` once, then `./run_media_hub_box.sh` to launch. The installer adds FFmpeg/ffprobe, mpv (used for responsive JSON-IPC speed control), PortAudio/libsndfile, creates a local `.venv`, and installs `requirements.txt` without moving the project.

## Recommended appliance setup

Use a Pi 5 or x86 mini PC with active cooling, SSD/NVMe storage when possible, and HDMI/USB audio. Keep Groovebox projects/renders on the SSD rather than an SD card for batch rendering. mpv is preferred over VLC/ffplay because the Media Hub can change playback speed on a running file without restarting it.

For unattended installations, configure the desktop environment to auto-login and launch `run_media_hub_box.sh`; keep the machine on a local network only if remote administration is actually required. Avoid running Groovebox itself as root. The installer uses `sudo` only for OS packages.

## Media Hub additions in this build

The Playlist tab can arrange queued media by a deterministic size/intensity arc, A/V interleave, seeded shuffle, or name. Its 0.25×–4× live speed slider updates an active mpv process through local JSON IPC. The Parametric Remix tab includes a control-rate expression script that can continuously drive GOAVA, RAND PARAM, Boost, speed, playlist advance events, and a sparse `media_hub_pattern` value in host playlist automation. The Batch Re-render tab accepts exported media or `.mgpr` files directly and maps a project set across start/end FPS and audio-bitrate values with linear, ease-in, ease-out, or smoothstep trends.
