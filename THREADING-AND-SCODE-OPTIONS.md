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

## R7: help-while-waiting lanes (POOL_HELP_R7)

Every `SharedWorkLane` future is a `_LaneFuture`. When a managed worker calls `.result()` or
`.exception()` on a job that has not started, the waiting worker runs the job itself if that keeps lane
semantics:

- (a) the job already holds a lane slot and is only waiting in the shared executor FIFO, or
- (b) the job is next in the lane and the caller is running a job of that same lane (its slot is blocked anyway).

A per-job claim lock guarantees exactly one runner. If a waiter ran the job, the executor's copy becomes a
no-op. Lane order and `max_workers` limits are unchanged, so a worker never sits blocked on queued work and
nested submit-and-wait cannot deadlock. The GUI thread never helps; it is never handed heavy work.
Inline-run stats are now updated under the lane lock (that was a race).

## R7: pooled scratch without the junk copy (POOL_SPEED_R7)

`borrow_vector(fill=None)` returns `np.empty(n)` instead of copying an uninitialised template slab.
The contract is the same (uninitialised contents), and there is one less full memcpy per multidim voice render.

## R7: live inputs never re-route outputs (LIVE_INPUTS_R7)

The Live Play mic opens with `reroute=False`: no `set-default-sink` and no combined-sink rebuild while
playback runs. Live Play also has an output watchdog: if the speaker callback stalls for 1.5 s, the output
is reopened at the same rate (at most 5 times per session), and the queue, keys, mic, media and the take carry on.

## R7r/R7s — memory-shaped simplifications (2026-11-12)

* **STREAM_IDENTITY_R7** `stable_numeric_identity` feeds SHA-256 the exact bytes `json.dumps` would make,
  walking big top-level lists/dicts instead of building one string. Same 52-bit identity, no 500 MB strings.
* **IDENTITY_SCOPE_R7** `bridge.host_identity_scope(host)` — inside it the deep host categories are computed
  once. The canonical pass (plan + claim) now walks the project once instead of twice. Nothing is cached
  outside a scope.
* **HISTORY_POOL_R7** (`history_pool.py`) undo/redo/randomizer snapshots store large lists/dicts per element
  as pickled, content-addressed blobs in one weak pool: unchanged rows are shared by every snapshot, freed
  automatically with the last snapshot, and restored as fresh objects. Restore now walks the same key list
  the snapshot captured (it previously skipped ~25 captured stores).
* **UNDO_BUDGET_R7** history keeps 64 steps unless the shared pool exceeds 1/4 of RAM (min 2 steps).
* **STRUCTURE_FIT_R7** growing playlist rows x synths is clamped to free memory (2x headroom) with one notice;
  load and undo never clamp.
* **WORKER_RULE_R7** `thread_budget.memory_worker_cap(preferred, heavy=)` is the single RAM rule for lanes,
  math threads and `memory_guard.adaptive_workers` render/export pools.

## R7u — forecast, sizer and the virtual horizon

- `forecast()` keeps a running mean and variance of run time for each job signature (`predicted_cost`).
- The bulk class width grows to `base / cpu_share` (at most 2 × base). The width of an unordered lane follows Little's law: `workers = ceil(arrival rate × expected cost)`, checked by `math_invariants.littles_law`.
- `resolve_horizon(key, q)` is `μ + kσ` with `k = √(q/(1−q))`. By Cantelli's inequality the job finishes within that time with probability ≥ q, whatever the run-time distribution. `virtual_blocks(key, block_s, q) = ceil(horizon / block)` is how long a synth should keep modulating a closed-form virtual state (`multidim_synth.virtual_voice`, exact because the voice is degree-1 homogeneous) instead of waiting.
