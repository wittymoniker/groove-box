# The mathematics of Mathematician's Groovebox

This is the technical companion to the README. It says what the system computes, which properties are
proven (and how they were measured), and in what sense the design is scientifically sound. It also says
plainly what is *not* claimed.

## 0. The thesis, and what supports it

**Thesis.** The number and style of synths put together in Groovebox (the instruments, the GOAVA sum, the
L-system mapping, the panel layout) are a personal, rather complex choice. The method underneath is not. It
models mathematics strictly enough that seeds can express any discrete signal, and that the result with
simple defaults and initial convolution is the correct, neutral one. That second property holds *because*
Meum and the other irrationals are used the way they are: as rationally independent ratios that never
re-align, so a default adds no structure of its own and everything heard comes from the seed.

Below, each part of the thesis is marked as **proven** (a mathematical proof or a measurement in this
document), **design argument** (reasoning from proven facts), or **not claimed**.

| Part of the thesis | Status | Where |
|---|---|---|
| Meum is uniquely defined, irrational and transcendental | **Proven** | §1a |
| Meum's powers never land on an octave; the Meum lattice fills the octave uniformly in the limit | **Proven** (Weyl) and measured | §1a |
| The kernel and modulation ratios 1, M, φ, M² never re-align (no common period) | **Proven** (rational independence) | §1a |
| Every finite note sequence is exactly some seed | **Proven** constructively; 200 / 200 measured, 0.0 Hz error | §9 |
| With every engine off, defaults change nothing (curve exactly 1.0, kernel = base + Meum pair) | **Measured** | §6, §7, §10 |
| Same seed → the same bytes; effects are separable from drift | **Measured** | §10 |
| Simple defaults + initial convolution give the *correct* result *because* of the irrationals | **Design argument** | §1a "Why the defaults are correct" |
| Any recorded waveform can be produced from a seed through the synths | **Not claimed**: exact only through the direct converters and A − B (§11) |
| No other choice of constants would work, or this one sounds best | **Not claimed** |

So "ideal" means the instrument behaves like a good experiment. Every result can be repeated, attributed
to its causes, compared exactly with another and falsified, and the defaults are neutral by construction
rather than by tuning.

## 1. Constants

* **Meum** M is the unique root in (1, 2) of **2^M = M⁴ + M² − M** (§1a):
  M = 1.197580734338526518831326189268352139462000770610620512690713161173612434527857961133371127128476968476…
  At this 100-digit value the residual is 1.7 × 10⁻¹⁰². The runtime uses the correctly rounded binary64
  value `0x1.3294a6a84dbb1p+0` from `meum_constants.py`. M⁻¹ = 0.83501677…, MEUM_NORM = (M − 1)/M.
* **Golden ratio** φ = (1 + √5)/2 = 1.6180339887…, φ⁻¹ = φ − 1.
* `series_sin` / `series_cos` are the project's own series forms of sin / cos, used so that every
  platform computes the same digits.

## 1a. Meum is not arbitrary: an irrational dimensional-propagation constant

The *equation* is a choice. Once it is chosen, nothing about M is free: the equation fixes M uniquely, and
M has the properties below whether or not anyone wanted them.

**Unique.** Let f(x) = 2^x − x⁴ − x² + x. Its real roots are −0.4638, **1.1976** and 16.0082. On [1, 2],
f′(x) = 2^x·ln 2 − 4x³ − 2x + 1 ≤ 4 ln 2 − 5 < 0 (the measured maximum is −3.61). Since f(1) = 1 > 0 and
f(2) = −14 < 0, there is exactly one root in (1, 2). That root is M.

**Irrational.** Suppose M = p/q in lowest terms. The right side, M⁴ + M² − M, is then a positive rational
a/b in lowest terms, and 2^(p/q) = a/b gives 2^p·b^q = a^q. Since gcd(a, b) = 1, b = 1, so a^q = 2^p.
Then a = 2^k with kq = p, so q divides p. With p/q in lowest terms that forces q = 1, making M a whole
number. But 1 < M < 2. So M is irrational.

**Transcendental.** Suppose M were algebraic. It is irrational, so by the Gelfond–Schneider theorem
(a^b is transcendental for algebraic a ∉ {0, 1} and algebraic irrational b), 2^M is transcendental. But
M⁴ + M² − M is a polynomial with integer coefficients in an algebraic number, so it is algebraic, a
contradiction. So M is transcendental: it satisfies no polynomial equation with integer coefficients.

**Never an octave, and log₂ M is irrational.** If log₂ M = p/q, then M^q = 2^p and M would be algebraic.
So log₂ M = 0.26012291784… is irrational and no power M^k (k ≠ 0) is ever an exact octave 2^j. As an
interval, M is 1200·log₂ M = 312.1475… cents, a little wider than a minor third, and it never closes a
cycle. The nearest approach among M¹ … M¹⁰⁰⁰ is M⁸¹⁵, still 0.21 cents from an octave.

**Uniform in the limit (Weyl).** For any irrational α, the sequence kα mod 1 is equidistributed
(Weyl, 1916). With α = log₂ M, the octave-reduced Meum powers fill the octave uniformly: measured over
k = 1 … 10⁶ in 12 equal bins, the counts are 83,331 … 83,335. With α = M/12, the instrument-slot coordinate
uᵢ = (3iM) mod 36 = 36·{iM/12} is equidistributed on [0, 36): measured over 10⁶ slots in 36 bins,
27,748 … 27,804 (expected 27,778). This is a limit statement. For the 48 actual instrument slots the bins
hold 0 … 5 (expected 1.3), so a small rig is *spread without repeats*, not perfectly even.

**Never re-aligns (rational independence).** The numbers 1, M, M² and φ are linearly independent over the
rationals. If a + bM + cM² + dφ = 0 with rationals not all zero and b or c ≠ 0, then M would be a root of a
polynomial with algebraic coefficients, so algebraic, contradiction. If b = c = 0, then a + dφ = 0 forces
a = d = 0, because φ is irrational. By Kronecker's theorem, partials at f·(1, M, φ, M²) (the Global Convolve
kernel, §7) and phases advanced by M and φ (the modulation and lattice phases, §6) trace a path that is dense
on the torus and never exactly periodic. No two partials ever share a common period, so they never lock
into a repeating beat pattern.

**In the author's book.** Meum comes from *Scientific and Mathematical Theories and Inventions* by Noah
Girouard King (Eski), included as `resources/Scientific_and_Mathematical_Theories_and_Inventions.pdf`. It
is listed with the author's other self-referential numbers (p. 60, "M = 1.1975807343…") and defined on
pp. 63–64. Every identity the book states was checked here at 80 significant digits:

| The book's statement (pp. 63–64) | Check |
|---|---|
| (M − 1)·M + (M − 1)·(1/M) = 2^M/M² − M | Multiplying by M² gives 2^M = M⁴ + M² − M exactly; residual 2 × 10⁻⁸⁰ |
| "With two other numbers as additional solutions" | Matches: f has exactly three real roots, −0.4638, M and 16.0082 |
| For any number N: 2^M/M^(N+1) − M^(3−N) = (M − 1)/M^N | Holds for every N tried (−3, 0, 1, 2.5, 7, 40); residuals ≤ 6 × 10⁻⁸⁰. Multiplying by M^N always gives back the same equation, so the identity holds at every power N |
| N^(M·log_N 2) − M⁴ − M² + M = 0, roots at Meum "for any value N" | N^(M·log_N 2) = 2^M for every base N > 0, N ≠ 1 (checked for N = 0.5, 3, 10, 1000), so the equation is the same in every base |
| M is "the only root … which doesn't change its slope sign over any value N, and is unique" | F_N(x) = 2^x/x^(N+1) − x^(3−N) − (x − 1)/x^N equals f(x)/x^(N+1), so its slope at M is f′(M)/M^(N+1) = −6.68/M^(N+1) < 0 for every N. M is the only root where the curve **falls**; the other two rise (f′ = +2.83 and +29,246) |

The book gives the definition and these equivalent forms. The irrationality and transcendence proofs above
build on that definition. The "for any N" family is what makes the dimensional-propagation reading natural:
scaling the identity by M^N, for any power or dimension N, leaves it unchanged.

**Where Groovebox uses Meum.** Every item is in the source. The status says what is proven about the role.

| Use | Where | What it does | Status |
|---|---|---|---|
| Seed-language constant `MEUM` | seed environment, `scode/libs/meum.scode` (constant M from `meum_constants.py`) | Lets every seed program use M | Definition |
| Meum AM / FM / PM modulation vectors | `meum_modulation_vectors` | Per-voice amplitude, frequency and phase modulation | Deterministic |
| Meum power lattice P_j = M^(j−6) and slot uᵢ = (3iM) mod 36 | `MEUM_POWERS_*` | Per-instrument scaling factors | Equidistributed in the limit (Weyl, §1a) |
| Normalised weight M_n = (M − 1)/M | `MEUM_NORM` (≈ 110 uses), `isn` EQR path, partial-ratio warp | Blends and warps | Definition |
| Spatial fields and activity | `meum_spatial_*` (x/y/z potential, operator field, EQR spatial effect, activity resolver), `meum_state_transition` | Spatial audio effect and the canonical spatial branch | Deterministic |
| GOAVA stepping | GOAVA irrational sampling s = ½·f_b·M⁻¹·t; RAND token step × M | Moves along GOAVA's curve | Never periodic (M irrational) |
| Global Convolve kernel | partials g·M and g·M² (§7) | Convolution colour | No common period with g and φ (rational independence, §1a) |
| Hyperdrive FX depth | `fi_hyperdrive` amount (M − 1)·4 | Drive amount | Definition |
| `.MEUM` project container | `meum_compression.py` | File format name only | Not mathematical |

What the irrationality guarantees here is **no common period**: the lattice, the kernel partials and
GOAVA steps never fall back into a repeating grid (harmonic locking). It does *not* guarantee that phase
cancellation never happens. Irrational partials still cancel momentarily; they just never lock into a
repeating cancellation pattern.

**Dimensional propagation (interpretation).** Two readings make the defining equation geometric. These are
interpretations, not further theorems.

* In the similarity-dimension relation N = s^D, scaling a D-dimensional self-similar object by s = 2
  multiplies its measure by 2^D. The left side, 2^M, is therefore *how much an M-dimensional measure
  propagates when its length doubles*.
* The right side is M^(2²) + M^(2¹) − M^(2⁰): the 4-volume plus the 2-area, minus the 1-length, of a cube
  of side M. The dimensions 1 → 2 → 4 are themselves successive doublings.

So M is the one dimension in (1, 2) where doubling-propagation of measure (exponential in dimension)
balances a doubling chain of geometric measures (polynomial in side length). It is a fractional dimension
between a line and a plane, which is why the code uses it as a *spatial* constant: x/y/z fields, the power
lattice M^(j−6), and spatial activity all scale by powers of M, never by a rational step that would tile
back on itself.

**Why the defaults are correct (design argument).** A default is correct here if it adds no structure the
seed did not ask for.
1. With rational ratios (3/2, 2, 5/4 …), any default modulation, lattice or convolution kernel has an exact
   common period. That recurrence is structure (a beat, a grid, a resonance) that comes from the constant,
   not from the seed.
2. With 1, M, φ, M², there is no common period (rational independence), no octave closure (log₂ M
   irrational) and no preferred bin in the limit (Weyl). A default built from them is non-committal: it
   colours, but it does not impose a pattern.
3. On top of that, every canonical term is gated by engine level. With every engine off, the modulation curve
   is exactly 1.0 and the kernel reduces to the original base + Meum pair (measured, §10). Initial
   convolution is capped at 18 % wet while a seed program is active, and the tracking kernel is
   Hann-tapered, so even its residual colour is broad, not a sharp resonance.
4. So the structure in the result comes from the seed and the user's edits. The defaults contribute only a
   neutral, irrational, non-repeating colour. That is the precise sense in which the net result is correct
   with simple defaults and initial convolution *because* of how Meum and the other irrationals are used.

What is not proven is that this neutrality is the *only* way to be correct, or that listeners prefer it.
Those are aesthetic claims, and a measurement would have to test them.

## 2. Seeds, signatures and the seed tree

* A **seed program** P is a pure function of beat time t, v(t) = P(t; env). The environment `env`
  supplies only deterministic names (isn, ics, floor, tanh, MEUM, PHI, …), with no clock and no OS randomness.
* Its **signature** is σ(P) = BLAKE2b-64( ⊕_{t∈T} round₁₂ v(t) ) mod 2³¹ over 20 probe beats,
  T = {0, ¼, ½, …, 3¾, 6, 8, 12, 16}. Two programs that agree only at t = 0 still differ.
* **Sub-seeds** come from one rule, seed_child(s, l₁…lₙ), SplitMix64 folded over labels:

  z ← s ⊕ (h(lᵢ)·γ); z ← z + γ; z ← (z ⊕ z≫30)·c₁; z ← (z ⊕ z≫27)·c₂; s ← z ⊕ z≫31,
  γ = 0x9E3779B97F4A7C15, c₁ = 0xBF58476D1CE4E5B9, c₂ = 0x94D049BB133111EB.

  Every label changes every output bit and order matters. The same map applies at every scale:
  project → instrument → sequence → engine → frame → game object. That makes the seed tree
  **self-similar**, which is the precise sense in which Groovebox is "a fractal of seeds".

## 3. The canonical engines

Six sources write canonical (seed-owned) material: SEEDED, RAND, LOCK (phase lock), EUCLIDEAN, GOAVA and
FRACTAL SEED (on by default). Each has a level Lₖ ∈ [0, 1].

* **Unison.** With u the unison amount and A the active set, an active engine's working level is
  L′ₖ = (1 − u)·Lₖ + u·mean_{j∈A} Lⱼ. A lone engine keeps its own level.
* **Fractal Seed (L-system).** d = SHA-256(seed text). The axiom is the 32 bytes of d, each taken mod 26
  as a letter A–Z. Each letter X rewrites to the two letters given by bytes 0 and 1 of
  SHA-256(d ‖ "|fractal-rule|" ‖ X). Depth 6 gives 32·2⁶ = 2,048 symbols, rendered on a 16 × 16 step
  raster in minor pentatonic from MIDI 60. The identity is the axiom plus the rules. Depth, tempo and the
  window are viewing parameters only and never redefine the seed. No probability is used.
* **GOAVA getNote.** For an assigned number a, a step s and the seed values x₁…x_m:

  G(a, s; x) = | Σᵢ (1 + cos(1 + |π a / 2| + (π/2)(|xᵢ| + |a|)·s + [xᵢ = 0]·s)) / (m + |a − xᵢ|) |

  G is a continuous function of s, so GOAVA can index a curve defined entirely by the seed.
* **RAND token.** Each OFF→ON transition captures one 64-bit token τ and freezes it (it is saved with the project).
  * Fractal source (default): τ = seed_child64(seed, "rand", generation). Every variation is a new,
    reproducible child of the seed.
  * Pure source (right-click RAND): τ comes from OS entropy. This is for live jamming and exploration,
    where unrepeatable randomness is the point. Because τ is frozen, a saved project still replays exactly.
  * RAND × GOAVA: τ indexes GOAVA's curve, with a = (τ mod 2³²) + 1 and s = ((τ ≫ 11) mod 2²¹)/2²¹ · M.
* **LOCK × GOAVA.** With GOAVA on, LOCK's target seed is BLAKE2b(seed, G(seed, MEUM_NORM)). It is still
  a function of the seed alone.

## 4. Divergence

For a value v, index i, domain salt k and amount a: u = BLAKE2b(v, i, k)/2⁶⁴ and
D(v) = v + (2u − 1)·|v|·a. At a = 0 this is exactly the legacy behaviour. The default a = 0.6 applies only
while a canonical engine is on.

## 5. Ownership: how the engines meet a person's work

A value still at its factory default is canonical-owned (share s = 1). A value the user moved or touched
is user-owned (s = ½). The effective value is v = (1 − s)·user + s·canonical for continuous controls;
discrete choices keep the user's value. Engines therefore add structure without erasing what a person
made, and with every engine off, nothing changes.

## 6. Modulation: the engines working together

The growth of canonical modulation is

  G = 1 − exp(−m/3),  m = Σᵢ (i + 1)·Lᵢ over (GOAVA, RAND, LOCK, SEEDED, EUCLIDEAN) ∩ active.

G = 0 with no engine on. G saturates toward 1, so more activity means more departure from the baseline,
never a wrap back toward it.

The Canonical Mod Depth for instrument o on playlist row r of n rows starts from

  w = sin(2π(r + ½)/n + slotₒ·(1 − c·L_lock) + φ_G),
  d = clamp(1 + G·(T·(1 + w/2) − 1), 0, 2),

where T is the seed's canonical XMOD target and c is the lock coupling. The engines then compose, each
term inert unless its engines are on:

| Engine(s) | Term |
|---|---|
| SEEDED | w ← (1 − Lₛ/2)·w + (Lₛ/2)·(2u − 1), u = seed_child64(seed, "modrow", o, r)/2⁶⁴ |
| LOCK | instrument offsets shrink by c·L_lock, so all voices move together |
| EUCLIDEAN | rows off the pulses of E(k, 16), k = 3 + (seed mod 6), have d pulled to 1 by L_e |
| LOCK × FRACTAL SEED | w ← (1 − p)·w + p·F(r), F = the L-system pitch contour, p = c·L_lock·L_f |
| RAND × GOAVA | φ_G = 2π·L_rand·G(τ) |

The Euclidean set is the maximally even one: step i (rotated by the seed) is a pulse when (i·k) mod 16 < k.

## 7. Global Convolve

The structural mix is cross-convolved, y = (1 − α)·x + α·(x ∗ k)·env, with α set by the Global Convolve control.
α is capped at 0.18 while a seed program is active. When a carrier WAV is loaded, the carrier is the kernel.
Otherwise the kernel **tracks the workspace**:

  k[n] = A[n]·Σⱼ wⱼ·sin(2π fⱼ n / sr + 2π uⱼ·(1 − L_lock)·max(Lₛ, L_rand))

* Frequencies: f = g·(1, M, φ, M²), where g is the base frequency.
* Weights: w = (1, ½, ½·L_fractal, ⅓·L_goava).
* Phases: uⱼ = seed_child64(Δ, "conv", j)/2⁶⁴. Δ is a BLAKE2b digest of every workspace variable that
  shapes the sound: FX, time FX, synth engine, canonical mode, divergence, key, tuning, playback style,
  song form, active instruments, Mod Osc, EQ, predictive FX, automation, instrument mixer, per-sequence
  state, the canonical context and levels, the seed and τ.
* Envelope: A = exp(−3·div·n/N) × (Euclidean 5-in-8 gate) × (Hann taper over the first N/2 samples, zero after).

A sum of sines is a narrow resonant filter. The Hann taper removes its hard edges, which broadens the
peaks into colouring. Measured: the spectral peak-to-mean ratio of the kernel falls from **121 to 56**
(about 6.7 dB less peaky).

## 8. Per-sequence variables

Every sequence can hold its own copy of workspace variables. During a render, a playlist row morphs the
global value g toward the mean of the local values of the sequences it plays: v = g + s·(mean(local) − g),
where s ∈ [0, 1] is the row's shift vote.

## 9. Symbolic completeness

Any finite note sequence (p₀ … p_{L−1}) on a 16th-note grid is exactly the seed program

  i = ⌊4t⌋ mod L,  f(t) = 0 if pᵢ is a rest, else 440·2^((pᵢ − 69)/12).

So the seed space contains all discrete music, not only what the engines invent. MIDI → seed uses this
form and is lossless. Measured: 200 / 200 random melodies reproduced at every step, maximum error 0.0 Hz.

## 10. Measured results (offscreen, the app's real code paths)

| Test | Result |
|---|---|
| Determinism | Same seed → identical SHA-256 for audio and frames, in-process and across processes |
| Any kind → any kind (sound, image, video, MIDI, text, data, seed, project, game) | 81 / 81 pairs |
| Save → load of the workspace | 303 / 312 changed controls exact; the rest are excluded on purpose or recomputed |
| Engine state sync (snapshot → apply → snapshot) | Passes with defaults and with every engine on |
| Paired engine measurement, control | Two OFF renders: audio Δ 0.000000, video Δ 0.000 |
| Paired engine effect (1 row, RMS audio Δ / mean pixel Δ) | SEEDED 0.240 / 15.2 · RAND 0.213 / 13.8 · LOCK 0.179 / 18.5 · EUCLIDEAN 0.202 / 19.4 |
| Engine coupling (§6) | 19 / 19 checks. Defaults leave the curve unchanged. SEEDED is deterministic. EUCLIDEAN off-pulse rows are neutral (mean deviation 0.000 vs 0.692 on-pulse). LOCK roughly halves instrument spread (0.038 → 0.017). The all-on render is deterministic and finite |
| RAND sources | Fractal source reproducible from the seed; pure source unrepeatable; both saved |
| Per-voice stages reach the export mixdown (paired, then undone) | LOCAL FX fractal 0.8: Δ 0.0122 · Layer EQ high +12 dB: Δ 0.0959 · Mod Osc 0.8 @ 6 Hz: Δ 0.1015 · each returns to Δ 0.000000 when undone |
| GLOBAL FX at the master stage of every export | Hyperdrive 0.8: Δ 0.0850 |
| Save to drive | "Choose a folder…" sets the target; a Live Player take is written to <folder>/Groovebox Exports/<project>/; unmounted and read-only sticks are reported with the reason |

## 11. What is not claimed

* That these constants or mappings are optimal, natural or unique (§0).
* That every recorded sound has a short seed. Audio → seed is a structural estimate (tempo, pitch,
  brightness, onset density, energy envelope). Arbitrary recordings are reproduced exactly only by the
  direct converters and by A − B.
* That a measured difference is a better sound. The Δ values show that an engine *acts*, not that it
  improves the music. Listening remains the judge.
* The LOCK × FRACTAL contour pull is weak at default levels: the correlation of the mean modulation with the
  L-system contour rises only from 0.196 to 0.212. Raise LOCK and FRACTAL SEED levels for a stronger effect.
