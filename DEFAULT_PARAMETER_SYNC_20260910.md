# Groovebox Default Parameter Sync — 2026-09-10

This release consolidates the current main Groovebox defaults so startup, Clear Memory,
missing-widget fallbacks, playlist/sequence generation, project-state serialization,
preview/render helpers, and UI documentation use the same baseline.

Authoritative synchronized defaults:

- EQR: 0.4014
- Fractallizer: 0.5995
- PKP Envelope: 0.5000
- Step Sequence Length: 12 steps
- Automation Sequence Length: 12 steps
- Playlist row duration: 8 beats
- Playlist Rows: 32
- Canonical Signal Control: Full Canonical / 100%
- Canonical Resonance: 100%
- Canonical -> Instrument Convolve: 50%
- Canonical Live Overblend: 50%
- Full-Unison OFF adherence fallback: 0.55

The stale Canonical Live Overblend tooltip that described 0% as the default has been
corrected; 0% is user-waveform-only and 50% is the default equal waveform boundary.
Legacy 8/16/48 sequence and 64/96 playlist fallback values were removed from the main
sequence/automation/project-sync paths and replaced by named authoritative constants. The
playlist row duration remains independently fixed at its 8-beat default.

Validation performed in this release:

- Python compileall: PASS
- default parameter synchronization contract: PASS
- five-canonical / Euclidean integration: 24/24 PASS
- final determinism purity groups: 7/7 PASS
- visual determinism invariant groups: 5/5 PASS
