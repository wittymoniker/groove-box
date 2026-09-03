# Groovebox Trio Architecture

## Responsibilities

### Python
Authoritative application layer: UI, sequencing, composition state, seed/script evaluation, playlist semantics, phase carry, project I/O, visual/game integration, and high-level effects.

### Julia
Numerical middle layer: readable reference DSP, batch numerical experiments, optimization/profiling candidates, and a direct `ccall` bridge into the C++ ABI. This makes Julia useful without putting a high-overhead process boundary in the audio path.

### C++
Hot inner loops: deterministic oscillator/partial synthesis, Meum modulation vectors, and hard clipping. Built with optimization and LTO where supported, without `-ffast-math` so canonical numerical behavior is not casually changed.

## Data flow

`Python state -> Julia numerical layer (optional) -> C++ kernel -> contiguous buffers -> Python effects/master/output`

For real-time safety, the Julia layer is optional in the default callback path. It should be used for batch rendering, optimization and experimental DSP until a persistent embedded Julia runtime is configured.

## Determinism rule

Do not introduce naive parallel accumulation into the canonical renderer. Use per-thread/per-voice buffers followed by a deterministic reduction if parallelism is added later.
