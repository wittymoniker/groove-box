# Bounded long render + Latitude appliance pass — 2026-09-17

Groovebox now switches to bounded-block DSP for long mixdowns (over 2,000,000 samples):

- no full-duration float64 time grid;
- row time is generated only for the active row;
- canonical/user proof RMS is chunked;
- DomainEQ and seed-script T-axis modulation are chunked;
- Global Convolve uses overlap-add FFT on long buffers;
- EQR/Meum spatial processing is vectorized and block/overlap based;
- video frames are still streamed directly to FFmpeg;
- temporary WAV conversion is streamed in chunks instead of allocating a second full PCM buffer;
- the old 30-minute video ceiling is removed; project duration and disk space are the practical limits.

The sOS BUILD_ISO kit now has a dedicated `BUILD_LATITUDE_35X0_ISO.sh`. The fat builder copies the live kernel from the same package release as its module tree, validates i915/AHCI/xHCI/HDA and firmware presence, and includes a memory profile for 8/16 GiB appliance hosts.
