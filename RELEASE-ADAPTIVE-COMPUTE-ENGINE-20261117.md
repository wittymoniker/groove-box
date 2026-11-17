# Adaptive Compute Engine — 2026-11-17

This source pass adds an optional adaptive compute layer on top of the existing sCode scheduler and hybrid runtime.

- Optional CUDA/CuPy oscillator backend. It is considered only for large blocks (131072 samples and above); missing CUDA, transfer/runtime errors, and numerical mismatches fall back to existing backends.
- Hybrid backend selection remains reference-checked and workload-size-class aware. Existing Go, Rust/native, LuaJIT, Julia, and NumPy paths are retained.
- Added persistent backend hints and bounded in-memory result caching keyed by exact operation inputs, including array dtype/shape/content. Cached arrays are returned as copies to prevent callers mutating shared cache state.
- Added bounded reusable host scratch buffers and routed the NumPy oscillator reference through them.
- sCode identity-block cache now retains the computed immutable audio block, not only its control vector, and returns an owned copy on cache hits. It is bounded by both entry count and memory bytes.
- sCode diagnostics expose optional GPU status, cache occupancy, and hit/miss/fallback counters.
- Executable packaging explicitly includes adaptive_compute and conditionally collects CuPy only when present in the build environment.
- The Go accelerator embeds its Go source in the Python loader, avoiding dependence on a source-tree path in PyInstaller one-file deployments.
- No new worker pool is created. Expensive calls remain the responsibility of the existing sCode lanes. Audio device callbacks must not invoke cache hashing, GPU transfers, compilation, or worker submission.
- CPU/GPU firmware limits, thermal throttling, and electrical protections are not modified or bypassed.

## Validation status

Per instruction, no tests, syntax checks, static checks, builds, benchmarks, GUI/audio tests, or hardware validation were run. GPU availability and performance depend on the target machine and optional CuPy/CUDA installation. GPU acceleration is therefore optional and not claimed to be faster on every workload.
