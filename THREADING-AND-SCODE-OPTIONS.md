# Threading and sCode options

## Current revision

The updated source includes an exact-input sCode canonical projection lane over copied, widget-free state; a bounded latest-request policy; digest-checked result publication; exact seed/EQ memoization; and asynchronous scenograph resize requests. An optional low-priority predictive process speculates one exact adjacent engine state and never blocks foreground work. It is disabled on CPU budgets below three cores, with `GROOVEBOX_PREDICTIVE_BUFFER=0` available as an explicit override.

Your requested priority is `0.048 * window_selected + 0.19758 * activity + 1.0 * tedious`, with each input clamped to 0–1. The all-active total is 1.24558, so the normalized contributions are approximately 3.85%, 15.86% and 80.28%. Predictive admission is bounded by one third of available capacity and remains limited to one speculative process; GUI refresh and real-time audio are not queued under this score.

Static cooperative canonical kernels are included as a prototype, rather than parsing or obfuscating the application at runtime. They are OFF by default because validation was stopped at your request; `GROOVEBOX_COOPERATIVE_CANONICAL=1` opts in. The established synchronous GUI-owned commit remains the default, so large canonical commits may still pause. A compact work key or an obfuscated representation is not a substitute for exact identity, lifecycle safety or an ownership boundary.

The objective should be maximum useful work without audible dropouts, blocked interaction, changed seeded mathematics or accidental rewriting of user-authored data. Increasing thread counts alone does not establish that objective. The strongest next improvement is to separate expensive canonical computation from a small, ordered GUI commit.

## Changes already included

The safe merge adds coalesced nonblocking foreground sCode planning, stale-result serials, correct Future cancellation semantics, weak viewer completion guards, and avoids redundant copies before filling private scratch buffers. Tiny RNG setup is now inline rather than submitted to workers and immediately waited on. These changes do not turn every canonical writer into a background transaction.

## Recommended options

| Option | Pros | Cons / risks | Recommendation |
|---|---|---|---|
| Immutable canonical snapshots, worker computation, ordered GUI commit | Removes substantial computation from GUI callbacks; allows cancellation/coalescing; preserves deterministic commit order | Requires separating model calculations from widget reads and user-data writes; snapshot cost can be large | Highest priority. Capture minimal plain data on GUI, compute off-thread, validate a generation token, then commit only current results |
| Chunked GUI commits with a short per-event-loop budget | Keeps repaint/input responsive even when thousands of rows must be installed; works without moving Qt objects to workers | More transaction state; needs rollback/cancel rules and protection against observing a half-committed project | Pair with snapshot workers. Disable only conflicting edits during commit, retain a stable playback snapshot and commit canonical engines in deterministic order |
| Priority-aware shared executor with reserved interactive capacity | Prevents decorative/video/export work from occupying all useful workers; can favor a new user edit | A policy change needs fairness and starvation metrics; existing lanes do not constitute a strict reservation | Prefer a few explicit classes: interactive planning, canonical compute, export, decorative work. Limit background concurrency rather than maximizing it |
| Bounded leased array slabs | Reuses actual writable memory instead of allocating a private copy on every borrow; useful for predictable repeated shapes | Returning a lease too early can corrupt queued audio, cached results or editable data; harder lifecycle discipline | Add an explicit context-manager/ownership API, not a silent change to `borrow_vector`; copy only at ownership boundaries |
| Read-only exact result memoization | Avoids recomputing identical pure math; naturally suited to seeded work | Hashing large inputs and cache growth can outweigh saved work; mutable aliases invalidate assumptions | Extend measured hot paths only, with complete keys, byte budgets and immutable cached results |
| Native batched sCode/C++/Rust kernels that release the GIL | Good throughput for sufficiently large, pure operations; less Python scheduling overhead | ABI/build portability and error reporting become more important; tiny jobs may be slower after conversion overhead | Batch related work and retain exact Python/reference parity. Keep Qt/document access out of kernels |
| Process workers for proven pure-Python CPU bottlenecks | Can bypass the GIL for computations that do not release it | Serialization, memory duplication, startup cost and platform spawn behavior; never send Qt objects | Use only after profiling identifies a real Python CPU bottleneck; prefer coarse jobs and explicit shared-memory ownership |
| Adaptive laptop profiles | Can trade throughput for latency, heat and battery life; helps avoid nested BLAS/worker oversubscription | Hardware varies; blind affinity or realtime priorities can worsen behavior | Offer Balanced and Render profiles with visible settings. Start conservatively and measure sustained work, not just a short burst |

## Why not simply maximize the pools?

The application already shares a global executor through logical lanes, and its numerical libraries can create their own native threads. Adding more outer workers can multiply native thread counts, increase memory-bandwidth contention and worsen tail latency. It can also leave more stale work queued after the user changes a seed.

The current scratch pools intentionally return private arrays. They are not equivalent to a leased, in-place slab allocator, and should not be described as eliminating all allocation. The included filled-buffer change avoids one unnecessary template read/copy while keeping that private-ownership contract.

The existing result cache is a better fit for exact repeated pure calculations than caching mutable project objects. Cache keys must include all mathematical inputs, engine/compiler version where relevant, shape, dtype and policies that affect a result. Presentation-only state should not invalidate pure DSP results, but editor changes that affect mathematics must.

## A safe implementation sequence

- **Instrumentation:** Record GUI heartbeat gaps, callback/commit duration, queue depth, cancelled/superseded jobs, cache-hit bytes and audio underruns. Keep measurement out of the realtime audio callback.
- **One-engine migration:** Choose a canonical engine with clean plain-data inputs. Add an immutable snapshot and a pure compute function while retaining the existing implementation as a reference.
- **Deterministic publication:** Attach project/engine generations, reject stale results, and perform a bounded ordered commit on the GUI thread. Never let a worker mutate live sequence arrays or inspect widgets.
- **Scheduling policy:** Give interactive jobs priority and cap speculative work. Coalesce repeated UI requests before they fill a queue.
- **Memory ownership:** Add leased buffers only once each producer, consumer, cache and cancellation path has an explicit lifetime contract.
- **Scaling:** Compare a short edit workload and a sustained render workload on the intended laptop. Tune worker/BLAS counts from observed latency and throughput, not the largest available number.

No claim is made that these proposed architecture changes have already been implemented or benchmarked. They are the next steps I would prioritize after this safe-source merge.
