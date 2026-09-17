# Bounded long-render patch — 2026-09-17

Groovebox long audio/video export now switches to a bounded-memory path once a render exceeds 2,000,000 audio samples.

- Removes the former 30-minute video frame ceiling.
- Avoids allocating the full float64 render time grid for long projects.
- Uses block-sized DSP working sets selected from installed RAM.
- Writes temporary PCM16 WAV audio incrementally instead of allocating a second whole-render int16 copy.
- Computes RMS/proof statistics in chunks and avoids retaining redundant full-length proof buses during long renders.
- Keeps project duration independent of installed RAM: 8 GB and 16 GB systems use the same project/output math; RAM changes block/cache size, not an artificial duration limit.

The appliance target remains x86_64 and is intended to use the same ISO on Latitude 3560/3570 hardware. Installed RAM is detected at runtime; no model-specific ISO is required.
