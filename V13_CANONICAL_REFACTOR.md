# Groovebox v13 — Single Source of Truth Canonical Refactor

## What changed

`canonical_authority.py` is now the explicit read/write authority for the project composition.

The existing Groovebox state is retained as a compatibility surface so the mature audio/video/game engines do not need a risky all-at-once rewrite. Before persistence, rendering, video export, or videogame generation, live state is synchronized into the canonical document. Project loading restores the canonical document through the existing loader and then re-synchronizes the authority.

## Canonical data

The authority carries the existing project composition, including sequence memory and banks, playlist/automation, instrument parameters and samples, patch connections, domain/global algorithm state, timing, imported media references, notes, UI state, and cross-media information.

## Cross-media rule

The canonical document feeds audio, video, and videogame consumers. Rendered music waveform analysis is attached to that document and includes RMS, peak, energy envelope, zero-crossing rate, spectral centroid, spectral flatness, normalized spectrum, and deterministic fingerprints.

## Read/write API

- `app.canonical_authority.read(path)`
- `app.canonical_authority.write(path, value)`
- `app._canonical_document()`
- `app._canonical_write(path, value)`
- `app._sync_canonical_authority()`

## Persistence/export

Project save/load, export provenance, video/game metadata, and cross-media state use the same canonical boundary. Legacy mirrors remain only for compatibility with older engine code and are re-synchronized at boundaries.

## Verification

- Python compileall: passed
- Cross-media tests: 2/2 passed
- Canonical authority tests: 3/3 passed
- No PyQt6 GUI launch test was claimed because PyQt6 is not installed in the build environment.
