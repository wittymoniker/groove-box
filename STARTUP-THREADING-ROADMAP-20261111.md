# Startup resilience and pooled-work roadmap — 2026-11-11

## Implemented in this repair

- Linux, macOS, desktop, and mobile source launchers now converge on `scripts/launch_entry.sh`.
- The shared launcher prefers `run_hybrid.sh` (full dependency repair) and uses `run_groovebox.py` only as a damaged-checkout fallback; the runner still enforces CPython, required imports, local FFmpeg/ffprobe, and required sCode preflight.
- The sOS shell launcher probes the complete required Python import set before selecting an interpreter. It prefers `/opt/pyvenv/bin/python3`, then tries `/usr/bin/python3`/the configured system Python. It never invokes the desktop package installer.
- The generated `/usr/bin/groovebox-appliance.real` now has the same preferred-venv/system-Python import-probe fallback. The ISO staging validator accepts either executable runtime and still rejects dangling interpreter links.
- If startup-selector construction fails after the main window has been constructed, the runner logs the failure, reveals Main Groovebox, attempts to install autosave, and continues into the Qt event loop.
- The active ISO application overlay has been synchronized with the updated `run_groovebox.py`.

## Recommended next migration: explicit task assignment, not more ad-hoc threads

1. **One process-wide concurrency budget.** `thread_budget.py` currently has separately sized bulk and interactive executors. Their maximums can add together (for example, the bulk cap and interactive cap are independently computed), so a future change should enforce one aggregate worker ceiling while retaining interactive priority. This is the highest-value scheduler improvement; do not simply increase either pool.
2. **Typed task lanes and task envelopes.** Standardize task metadata: `task_id`, `kind`, immutable input snapshot, owner/window generation, cancellation token, priority, deadline class, and deterministic result key. Keep lanes for interactive UI I/O, bulk CPU, media I/O, canonical serial writes, and export/render processes.
3. **Canonical serialization boundary.** Canonical jobs receive only the approved seed snapshot, composition-trigger events, and playlist contents. All other widget state is excluded from canonical task payloads. Canonical writes stay serialized; workers return immutable results and the GUI applies them through the queued dispatcher.
4. **Deterministic parallel reductions.** Partition work by stable instrument/operator IDs, collect partials by stable task index, and merge in a fixed order. Avoid completion-order reductions, global mutable RNG, and thread-count-dependent floating-point accumulation. No probability/random scheduling for composition.
5. **Backpressure and coalescing.** Meter/preview/thumbnail refreshes should coalesce by key; project saves and canonical writes must not silently coalesce distinct committed states. Saturated producers should receive an explicit queued/rejected/deferred result rather than spawning another thread.
6. **Startup DAG with critical and optional phases.** Keep interpreter/Qt, writable data layout, required codec pair, sCode, QApplication, dispatcher, and main-window construction as critical gates. Move optional network discovery, MIDI enumeration, device inventories, thumbnails, background rendering, and WebEngine warmup behind first paint in cancellable workers. A failed optional phase must publish a degraded-feature status, never abort Main.
7. **Shutdown ownership.** Every lane and long-lived service should register with one application task supervisor. On close: stop accepting work, cancel queued work, invalidate UI generations, drain bounded critical writes, stop hardware callbacks, then tear down Qt. Never block the GUI waiting for unbounded media/network jobs.
8. **Observability before migration.** Record per-lane queue depth, active workers, queue wait, runtime, cancellations, stale-result drops, and saturation. This lets worker assignments be tuned against actual latency instead of intuition.

## Keep outside the pools

- Real-time audio callbacks and MIDI callback entry points: no blocking locks, filesystem, Qt widget access, or waits.
- Qt widget creation/mutation: GUI thread only.
- Hardware access semantics: retain existing ownership and explicit device-open/close behavior; background probes return snapshots, not live Qt/audio objects.
- Canonical source-of-truth state: immutable snapshots only; never let worker completion order redefine composition.

## Validation limits

The launcher scripts were syntax-checked, launcher/selector contract tests passed, and ISO launcher staging fixtures passed. This is source/contract validation only: no real Windows/macOS/sOS boot, package repair, physical audio/MIDI hardware, Qt GUI launch, or ISO boot was performed in this environment.

## Implemented in the follow-on pooled-host migration

- `thread_budget.py` now uses one aggregate CPU ceiling across the bulk and interactive executor classes. When the budget permits, one worker is reserved for interactive file/dialog/preview work and the remaining workers are bulk capacity; on one-worker systems both classes alias the same sole executor. This fixes the previous additive pool ceiling.
- `scode/window_host.py` adds an SCode-owned per-window task scope: generation invalidation, bounded logical lanes, cancellation of queued work, and stale-result rejection. Qt top-level windows are registered automatically; completion callbacks are delivered through a queued Qt signal. Widgets remain GUI-thread-only.
- The main launcher and the alternate SCode `SCodeRuntime` launcher install the window host. Host failure is optional and degrades to existing shared workers rather than preventing Main from opening.
- Julia package activation/instantiation is no longer triggered during module import or by an unready call path. The main runner schedules optional Julia warmup after the first UI paint on a bounded bulk lane; Python/native fallback remains available until Julia is ready. Backend availability is re-probed after warmup.
- `process_policy.Backends.report()` no longer calls its lock-taking availability method while holding the same non-reentrant lock.
- Flatpak, installed Linux, and crash-relaunch entrypoints now converge on the hardened runner/shared launcher fallback instead of bypassing the Qt/sCode preflight.
- `platform_runtime.accelerator_status()` provides a non-invasive capability snapshot for Rust, C++, sCode stage-0, Julia, and the guaranteed Python fallback; it does not build or initialize optional runtimes.

## Follow-on validation

The new pooled-host and launcher tests, prior export/panel/convolution tests, sCode pool tests, Rust isolation/build-kit tests, UI runtime contract tests, Julia bridge structural tests, sCode descriptor/completion tests, and seed/autosave round-trip tests pass in the current environment. These remain source/contract tests. No real Qt window launch, Windows/macOS boot, appliance boot, Julia package initialization, native benchmark, or physical hardware/audio test was performed.
- Fractal UI/project/encode lanes now use the same scheduler instead of three process-independent executors; the nested producer path detects a one-worker bulk budget and runs inline to avoid self-deadlock.
- Nearby subnet discovery submits bounded batches through the shared bulk lane, and the ad-hoc toggle reuses its service-owned lane rather than creating a duplicate pool. Hardware component scans and optional hardware warmup also use shared lanes when available.
- Live recording no longer creates a local worker eagerly. The dedicated compatibility executor is created only when the shared lane is absent; when the shared lane is merely saturated, a video frame is skipped instead of silently exceeding the global worker budget.
- ISO payload synchronization now includes the Python `scode` package and `groovebox_fractal` runtime package (plus their language/data assets), not just root-level modules. This ensures the active overlay can actually import the new window host and shared fractal lanes.

## Additional SCode hybrid-pool hardening — 2026-11-11

- The shared worker budget now exposes `is_managed_worker_thread()` so native bridges can detect when work is already executing inside the process-wide pool.
- Rust inner parallelism is forced to one worker when invoked from a shared SCode worker. Independent outer tasks therefore share the global worker budget instead of multiplying nested Rust threads. Main-thread offline kernels may still use the sCode-planned Rust width; small blocks remain single-threaded.
- Julia oscillator construction no longer initializes Julia synchronously. It requires the deferred warmup to have completed; until then callers use the established Python/native fallback.
- SCodeWindowHost now closes all per-window task scopes on Qt `aboutToQuit`, including the alternate `SCodeRuntime` launcher path.
- The alternate SCode launcher installs the same queued UI dispatcher as the primary launcher, but treats dispatcher installation as optional so Main can still open if that integration fails.
- Active ISO overlay synchronization refreshed all runtime sources and language package assets; `scripts/sync_runtime_payload.py --check` passes byte-for-byte.

### Additional validation

- 35 targeted tests passed across pooled-host lifecycle, worker-budget behavior, launcher fallback contracts, export/panel/convolution contracts, and Rust isolation/acceleration contracts.
- sCode stage-0 descriptor parity passed for all nine pool descriptor cases.
- Both installed Linux native libraries loaded through ctypes and passed hard-clip input/output parity on the four-sample boundary fixture; Rust reports accelerator ABI 3.
- Python compilation passed for all modified Python modules.
- This remains source/contract/native-kernel validation. A live Qt multi-window session, live Julia initialization, audio callback stress, and physical hardware were not exercised here.
- Additional UI-dependent memoization tests were attempted; eight could not start because PyQt6 is not installed in this environment (two other cases skipped). This is an environment limitation, not a passing GUI validation.
