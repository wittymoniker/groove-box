# MP3 / 24-bit audio export level fix — 2026-09-13

## Root cause

The audio export dialog defaults to a 48 kHz / 24-bit render. The render master
was nevertheless always converted with a 16-bit multiplier (`32767`) and stored
as `int16`. `_write_audio_parts_and_final()` then cast those small integers to
`int32` and packed them as 24-bit PCM before FFmpeg encoded MP3/Opus/OGG.

A full-scale 16-bit integer (`32767`) occupies only about `32767/8388607` of a
24-bit signal, which is roughly **-48.16 dBFS**. That is why an MP3 could be
several megabytes yet sound silent or nearly silent.

## Fix

- Added Qt-free `audio_export_integrity.py`.
- 16-bit export now quantizes at ±32767.
- 24-bit export now quantizes at ±8388607 into int32 storage before packed PCM24.
- MP3/Opus/OGG/other FFmpeg outputs are level-probed after encode. A non-silent
  rendered master that collapses to exact silence or suffers gross unexpected
  attenuation is now treated as an export-integrity failure instead of success.
- Intentional exact silence remains valid.
- Fixed the Bake & Compare helper's stale reference to the audio-dialog-local
  `export_bit_depth` variable; its documented comparison stream is int16.

## Regression coverage

`test_mp3_export_integrity_20260913.py` verifies:

1. true full-scale 24-bit quantization;
2. unchanged 16-bit quantization;
3. the historical bug is ~48.16 dB low;
4. a real 24-bit WAV -> libmp3lame encode decodes with audible/nonzero level;
5. the Groovebox export path calls the depth-aware quantizer and encoded-level check.
