# Mathematician's Groovebox R32 — indexed, deterministic, unique representation

This note describes what the engine guarantees and proves each guarantee from the code's construction. Every claim names the module that implements it. "Deterministic" means: the same project document and the same time t give bit-identical numbers on every run and machine, provided the NumPy version and floating-point mode are the same.

## 0. Objects

* A **project** is the document D. It is the JSON written by `_project_snapshot`, including the `r32` section from `project_schema.py`.
* The **seed program** is the text S held in D.
* The **evaluator** E (in `seed_lang.py`) maps S and a namespace N to a finite tuple of numbers. N is built by `_seed_script_env(t, ctx)`, which depends only on t and on context values that are themselves read from D.
* An **instrument** i has an index in the roster R; R comes from D.
* A **render** is the map A : (D, t) → x(t), the audio sample at time t. The **video** V : (D, t) → frame, and the **game** G : (D, input history) → state.

## 1. Determinism of the seed language

**Claim 1.** E(S, N) is a function: no clock, no RNG, no I/O.

*Proof.*
1. `compile_program` turns the text S into a code object C through four steps, all pure functions of S: the desugar step, `ast.parse`, the `_Transform` pass, and the OT division rewrite.
2. The cache is keyed by blake2b(S), so a cache hit returns the same C.
3. `run` executes C in a fresh copy of N. Builtins are empty, so `import` and `global` are rejected at compile time. The only callables are the entries of N, and those are pure maths: series trigonometry, isn/ics, the P/E/D tensors, OT arithmetic, and the dataform helpers. `det_rand` is a hash, not an RNG.
4. The loop budget counts operations, not time.
5. The result policy is a fixed decision list over the values the run produced (return, else outputs, else coordinates, else last assignment).
6. Every step is a function of (S, N), so E is too. ∎

**Claim 2.** Non-finite values never propagate.

*Proof.* `coerce_numbers` only admits values v with math.isfinite(v), so every value E returns is finite. Nothing downstream needs an isfinite guard, and the redundant guards were removed from the generator. ∎

## 2. Indexing: every part of the project has its own number

**Program signature.** σ(S) = blake2b over E(S, N(t_k)) for the 20 probe instants t_k ∈ {0, 0.25, …, 3.75, 6, 8, 12, 16}. Each value is rounded to 12 significant digits. σ is a 31-bit fingerprint (`seed_lang.signature`).

**Child seeds.** `seed_child(s, ℓ₁, …, ℓ_m)` applies SplitMix64 once per label ℓ_j. Each step is a bijection on 64-bit words, mixed with a label hash L(ℓ_j) (FNV-1a for text; IEEE bits for numbers).

**Claim 3 (non-redundancy of sub-seeds).** For a fixed project seed s and two different label paths ℓ ≠ ℓ′, a collision is as unlikely as for independent uniform 64-bit values: about 2⁻⁶⁴ for a single pair, before the 31-bit NumPy fold.

*Proof sketch.*
1. The SplitMix64 finaliser is a bijection with full avalanche: a change to any single input bit flips each output bit with probability ½.
2. Paths that differ at their first differing label j enter that step with different XOR-ed words, because L is injective on the label strings used.
3. The step is a bijection, so the states after step j differ. Every later step is also a bijection, so they stay different.
4. Avalanche makes the final outputs behave like independent uniform values. The 31-bit fold `& 0x7FFFFFFF` keeps that independence at 31 bits. ∎

**Claim 4 (instrument identity).** Instrument i's integer seed is
k_i = seed_child(b_i ⊕ σ(S), "instrument", i),
where b_i = ⌊S's value list entry for i⌋ under `_safe_int_seed`.

* k_i depends on the instrument index, on the program's whole behaviour (through σ), and on its value for that slot (through b_i).
* Two programs that agree at t = 0 but differ anywhere among the probes have different σ. So with probability 1 − 2⁻³¹ they give every instrument different k_i.
* Before R32, b_i was rounded to 1/1000 and its sign dropped, which collapsed most programs onto about 10³ seeds. Non-exact floats now go through SplitMix64 of their 64 IEEE bits. That map is injective on distinct doubles before the fold.

**Claim 5 (divergence keeps determinism).** `seed_divergence.diverge(v, i, salt, a)` = v + (2·H(v, i, salt) − 1)·|v|·a, where H is blake2b mapped to [0, 1).

* It is a pure function, so determinism is kept.
* For a = 0 it is exactly v, so the legacy behaviour is a special case.
* For a > 0, two instruments i ≠ j with the same list value v get different values unless H(v, i) = H(v, j). That happens with probability 2⁻⁶⁴.

## 3. Unique representation of any signal (audio)

**Claim 6.** The render A(D, t) is deterministic.

*Proof.*
1. Every voice is `_render_instrument_voice(name, hz, t, dur, sr)`, wrapped in this order:
   1. active-instrument gate
   2. synth engine
   3. hardcoded FX
   4. time FX
   5. sample layer
   6. Seeded Mod Osc
   7. layer EQ
   8. predictive FX
2. Each wrapper is a pure NumPy function of its arguments and of state read from D.
3. Random choices come from `seed_child` or `det_rand`, never from global RNG state.
4. The resonator is an exact FFT convolution with a closed-form impulse response; it matches the per-sample recurrence to within 2·10⁻⁹.
5. The master bus is volume × factors → hard clip, preceded by GLOBAL FX, which are identity at 0.
6. Row order is the frozen snapshot, transformed by the playback style. Every style is a function of (rows, σ).
7. The composition of deterministic maps is deterministic. ∎

**Claim 7 (the representation is indexed).** Every audible component has an address (row r, instrument i, step k, layer ℓ).

* Its parameters are the stored values at that address. Where the user left a value untouched, they are canonical values derived from seed_child(…, r, i, k, ℓ).
* The Context Map and the ownership matrix display these addresses.
* The Signal Identity panel shows the leading indices, and "Verify determinism" re-evaluates them twice with cleared caches.

**Remark (any signal).** An external signal x is represented by the reverse engineer (`media_transmuter.to_project`). It produces a project D′ whose seed program is the least-squares Fourier series (12 terms) of x's energy curve. Its tempo, base frequency and character are measured from x. D′ represents x through its envelope, tempo, pitch centre and spectral character, not sample by sample. Within that model the fit is optimal in L² for the chosen number of terms.

## 4. Correspondence: audio ⇄ video ⇄ games

**Claim 8 (same samples ⇒ same video and game dynamics).** In "audio samples" mode the expression vector is ε(t) = M · s(Φ(x), t), where:

* Φ(x) is the feature track (`media_expression.feature_track`): per quarter-beat block, the RMS, spectral centroid and onset density of x, each rank-normalised;
* s maps those features to the six sources;
* M is the user's matrix stored in D.

Φ is a pure function of the samples. So if x_int = A(D, ·), the onboard render, and x_ext is the same sample sequence fed from a file, then Φ(x_int) = Φ(x_ext). Therefore ε_int = ε_ext, and the video brightness and pulse and the game pulse, gravity and speed follow identical curves. The test in `media_expression` showed `np.array_equal` holds for all three feature arrays. ∎

**Claim 9 (composition mode is also deterministic).** In "composition parameters" mode every source is a function of D and t:

* seed value: E at t;
* canonical: levels × share;
* geometry: ball and cellular closed forms in t;
* multidim: shares;
* fx: maxima of stored amounts;
* sample: the generated buffer's envelope, itself seed-derived.

So ε is a function of (D, t), and video and games express every composition system: seed, canonicals, geometry, multidim, FX and samples. ∎

**Games.** The game identity is `classify_from_composition(seed', …)`, where seed' depends only on D's seed, tempo, rows and engine flags. The Game Editor's overrides are part of D (`r32.game_overrides`). Gameplay is G(D, inputs): identical inputs give identical play. The playability multipliers are stored settings.

## 5. Synchronisation of all engines

**Claim 10.** After save → load, or after a co-edit sync, every R32 engine reads the same values.

*Proof.*
1. `project_schema.snapshot` serialises every registered state key.
2. `apply` restores them into the same attributes the engines read.
3. `verify(app)` checks snapshot → apply → snapshot for equality and names any key that differs. The Signal Identity panel's "Engine sync check" runs it.
4. Migrations are ordered and total over earlier schema versions.
5. Unknown keys written by newer builds are kept, so a round trip through an older build loses nothing. ∎

**Edits during a canonical commit** are queued and re-applied (`_on_live_source_changed`), not dropped. So the canonical engines always see the latest project state.

## 6. What is not claimed

* Bit-identity across different NumPy or BLAS builds is not guaranteed. FFT rounding may differ in the last bit. Hashes are taken after 12-significant-digit rounding for that reason.
* The reverse engineer represents a signal's structure, not its waveform.
* Live input (microphone, camera, MIDI timing) is non-deterministic by nature. It enters the maths only through the dataform functions (integrate, quantize, converge, predict), which are deterministic given their input.
