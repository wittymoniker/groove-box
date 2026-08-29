# =============================================================================
# Groovebox Video-Game Generator — deterministic unique non-redundant worlds
# =============================================================================
# Project goal: every seed → one ideal composition signal. The same seed must
# also yield exactly one game identity (genre, camera, topology, models, UI)
# with no redundant collisions across the seed lattice.
#
# Classification uses the Meum / φ group action on a finite product of cyclic
# groups (genre × camera × topology × social × scale). Each coordinate is a
# residue class of a hash of (seed, composition fingerprint). Intersection of
# classes yields intercombinations (e.g. offline×third-person×sandbox×survival).
# =============================================================================
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
import textwrap
import zipfile
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

# Meum lattice (same constants as the signal generator — identity partner)
MEUM = 1.1975807343385265
MEUM_INV = 1.0 / MEUM
MEUM_NORM = (MEUM - 1.0) / MEUM
PHI = 1.618033988749895
PHI_INV = PHI - 1.0

# Cyclic group coordinates — order of each factor group
GENRES = (
    "arcade", "fps", "rpg", "sandbox", "survival", "arena",
    "dating_sim", "platformer", "strategy", "racing", "puzzle", "adventure",
)
CAMERAS = ("first_person", "second_person", "third_person", "top_down", "isometric")
TOPOLOGIES = ("linear", "open_world", "hub_spoke", "arena_loop", "roguelike_deck")
SOCIAL = ("singleplayer", "local_coop", "online_multiplayer", "asynchronous")
MOODS = ("neon_noir", "pastoral", "cosmic", "industrial", "mythic", "glitch")
# WORLD_FACTORS_2026: the world/level coordinates are a second product group
# (objective × difficulty × level_type) acting on the composition fingerprint.
# They reuse the same residue calculus as composition_state.meum_effect_residue
# so the game world fan-outs from the same deterministic non-redundant lattice
# as the music: same seed+composition -> same world; anything different -> a
# different residue tuple with overwhelming probability.
OBJECTIVES = ("harvest", "escort", "survey", "siege", "nexus", "pilgrimage")
DIFFICULTIES = ("tutorial", "standard", "master", "meum_insane")
LEVEL_TYPES = ("heightfield", "boss_rush", "dungeon", "sky_islands", "coral_grid")

# TITLE_WORDBANK_2026: title generation used to be a fixed template
# ("{Mood} {Genre} [{fp}]"), which meant only len(MOODS) * len(GENRES) = 72
# distinct title shapes existed. To keep titles fitting the same "infinitely
# varied, deterministic, nonredundant" lattice as the rest of the generator,
# titles are now built from four independent word banks, each indexed by its
# own seed-mixed residue. Same seed -> same title every time (deterministic);
# different seeds spread across banks_a*banks_b*banks_c*banks_d*|GENRES|
# combinations (currently 32*32*24*20*12 = 5,898,240) instead of 72.
_TITLE_BANK_A = (  # opening epithet
    "Hollow", "Radiant", "Silent", "Feral", "Ashen", "Gilded", "Errant",
    "Fractured", "Luminous", "Withered", "Untethered", "Crowned", "Drowned",
    "Static", "Recursive", "Nameless", "Borrowed", "Unmoored", "Spiral",
    "Threadbare", "Ossified", "Flickering", "Molten", "Quiet", "Errant",
    "Tessellated", "Unwritten", "Marrow", "Glass", "Ember", "Paper", "Salt",
)
_TITLE_BANK_B = (  # core noun
    "Engine", "Choir", "Garden", "Reactor", "Ledger", "Orbit", "Threshold",
    "Cartography", "Lattice", "Season", "Harvest", "Skyline", "Vault",
    "Wager", "Ritual", "Migration", "Signal", "Cathedral", "Frontier",
    "Undertow", "Compass", "Archive", "Pilgrimage", "Static", "Refrain",
    "Foundry", "Meridian", "Aperture", "Reckoning", "Bloom", "Circuit", "Tide",
)
_TITLE_BANK_C = (  # connective / genre-flavor descriptor
    "of Glass", "of Iron", "of Echoes", "of Dust", "of Tomorrow",
    "of the Deep", "of Rust", "of Salt", "of the Fold", "of the Interval",
    "of Static", "of the Long Night", "of Thread", "of the Nine",
    "of the Hollow", "of Amber", "of the Loop", "of the Tide",
    "of the Unwritten", "of the Meridian", "Reborn", "Unbound", "Interrupted",
    "Recompiled",
)
_TITLE_BANK_D = (  # short closing flourish (kept small/punchy)
    "//", "—", "::", "∞", "◦", "○", "·", "‡", "†", "*", "~", "^", "»", "◊",
    "△", "▽", "◆", "☍", "❖", "✦",
)


def _generate_title(seed: int, genre: str, camera: str, topology: str, mood: str, fingerprint: str) -> str:
    """Deterministic word-bank title: same seed -> same title, and the
    seed lattice fans out across a much larger, still-nonredundant title
    space than the old fixed "{mood} {genre}" template. Genre/camera/topology
    still flavor word selection so titles read as belonging to their game.
    """
    a = _TITLE_BANK_A[_mix(seed, f"title_a|{genre}") % len(_TITLE_BANK_A)]
    b = _TITLE_BANK_B[_mix(seed, f"title_b|{topology}") % len(_TITLE_BANK_B)]
    c = _TITLE_BANK_C[_mix(seed, f"title_c|{camera}") % len(_TITLE_BANK_C)]
    # Flourish appears only ~1 in 3 titles (keeps most titles clean text,
    # a minority get a distinctive glyph) — another seed-mixed residue.
    use_flourish = (_mix(seed, "title_flourish") % 3) == 0
    d = _TITLE_BANK_D[_mix(seed, f"title_d|{mood}") % len(_TITLE_BANK_D)]
    base = f"{a} {b} {c}".strip()
    if use_flourish:
        base = f"{d} {base} {d}"
    return f"{base} [{fingerprint[:6]}]"


def _safe_int_seed(value) -> int:
    try:
        as_float = float(value)
    except Exception:
        as_float = 0.0
    if not math.isfinite(as_float):
        as_float = 0.0
    if as_float == int(as_float) and abs(as_float) < 2**31:
        return int(as_float) & 0x7FFFFFFF
    h = hashlib.sha256(repr(as_float).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def _mix(seed: int, label: str) -> int:
    """Deterministic avalanche mix — unique non-redundant residue per label."""
    blob = f"{seed}|{label}|{MEUM:.12f}".encode("utf-8")
    d = hashlib.sha256(blob).digest()
    return int.from_bytes(d[:8], "big")


def meum_game_residue(seed: int, label: str) -> float:
    """One deterministic unit in [0,1) from the Meum residue calculus.

    This mirrors composition_state.meum_effect_residue(): a single hash of
    (seed, label, MEUM) reduced onto the unit interval. Every label minted
    from the same seed gives an independent residue, so world coordinates,
    difficulty, sigil rings, and level packs are all closed-form
    f(seed, label) with no shared state and no redundancy.
    """
    blob = f"{seed}|{label}|{MEUM:.12f}".encode("utf-8")
    i = int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")
    return (i % 10_000_000) / 10_000_000.0


def residue_to_bipolar(r: float) -> float:
    return r * 2.0 - 1.0


def meum_angle(k: float) -> float:
    """Collision-free angle packing on the circle.

    k·MEUM mod 1 is a dense cyclic order (a golden-angle analogue). Consecutive
    integers land on distinct circle points, so MEUM-packed sigils/beats never
    overlap and the ordering stays deterministic — a repeated-divergence
    primitive for scene placement and collection timing.
    """
    return math.tau * ((float(k) * MEUM) % 1.0)


def _res_idx(seed: int, label: str, mod: int) -> int:
    """Non-redundant index in [0, mod) from a Meum residue."""
    return int(meum_game_residue(seed, label) * mod) % max(1, mod)


@dataclass
class GameIdentity:
    """Complete game classification derived from the live composition seed."""
    seed: float
    title: str
    genre: str
    camera: str
    topology: str
    social: str
    mood: str
    online: bool
    host_port: int
    model_sets_1d: List[str]
    model_sets_2d: List[str]
    model_sets_3d: List[str]
    ui_palette: Dict[str, str]
    gameplay_hooks: List[str]
    music_variation: str
    composition_fingerprint: str
    splash_bars: int = 16
    objective: str = "survey"
    difficulty: str = "standard"
    level_type: str = "heightfield"
    sigil_count: int = 8
    world_fingerprint: str = "0" * 16

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_from_composition(
    seed: float,
    *,
    bpm: float = 120.0,
    seq_length: int = 16,
    playlist_rows: int = 32,
    n_instruments: int = 8,
    goava_active: bool = False,
    live_parametrics: Optional[str] = None,
    global_algo_fingerprint: Optional[str] = None,
    global_algo: Optional[Dict[str, Any]] = None,
    live_dj_goava: bool = False,
    live_dj_random: bool = False,
) -> GameIdentity:
    """Map composition state → unique game identity (group action on Z/n factors).

    Why this satisfies the project goal
    -----------------------------------
    The music engine yields a deterministic unique non-redundant signal from
    the seed. Games must share that lattice: same seed ⇒ same game class;
    different seeds ⇒ different residue tuples with overwhelming probability.
    We take the product group
        G = Z/|GENRES| × Z/|CAMERAS| × Z/|TOPOLOGIES| × Z/|SOCIAL| × Z/|MOODS|
    and act by seed-mixed hashes. Online capability is the social coordinate
    landing in the online class; host port is a stable function of the seed.
    """
    s = _safe_int_seed(seed)
    if not global_algo_fingerprint and global_algo is not None:
        try:
            global_algo_fingerprint = hashlib.sha256(
                json.dumps(global_algo, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:16]
        except Exception:
            global_algo_fingerprint = "0" * 16
    fp_src = (
        f"{s}|bpm={bpm}|L={seq_length}|R={playlist_rows}|N={n_instruments}"
        f"|G={int(goava_active)}|DJG={int(live_dj_goava)}|DJR={int(live_dj_random)}"
        f"|GA={global_algo_fingerprint or '0'}"
    )
    if live_parametrics:
        fp_src += f"|lp={str(live_parametrics)[:120]}"
    fingerprint = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()[:16]

    g = GENRES[_mix(s, "genre") % len(GENRES)]
    cam = CAMERAS[_mix(s, "camera") % len(CAMERAS)]
    top = TOPOLOGIES[_mix(s, "topology") % len(TOPOLOGIES)]
    soc = SOCIAL[_mix(s, "social") % len(SOCIAL)]
    mood = MOODS[_mix(s, "mood") % len(MOODS)]
    online = soc == "online_multiplayer"
    # Port in unprivileged range, seed-stable
    host_port = 27015 + (_mix(s, "port") % 8000)

    # Model sets — 1D filaments, 2D panels, 3D polytopes from Meum powers
    models_1d = [f"filament_{k}" for k in range(1 + _mix(s, "m1") % 5)]
    models_2d = [f"panel_{k}" for k in range(2 + _mix(s, "m2") % 6)]
    models_3d = [f"polytope_{k}" for k in range(1 + _mix(s, "m3") % 4)]

    palette = {
        "bg": f"#{(_mix(s,'bg') & 0xFFFFFF):06x}",
        "accent": f"#{(_mix(s,'ac') & 0xFFFFFF):06x}",
        "danger": f"#{(_mix(s,'dg') & 0xFFFFFF):06x}",
        "text": "#e8f0ff",
    }
    hooks = [
        f"hook_score_meum_{_mix(s,'hk0') % 7}",
        f"hook_wave_{g}",
        f"hook_cam_{cam}",
        f"hook_top_{top}",
    ]
    if goava_active:
        hooks.append("hook_goava_sine_portal")
    if live_dj_goava:
        hooks.append("hook_live_dj_goava")
    if live_dj_random:
        hooks.append("hook_live_dj_parametric")
    if global_algo_fingerprint and global_algo_fingerprint != "0" * 16:
        hooks.append(f"hook_global_algo_{global_algo_fingerprint[:8]}")
    if isinstance(global_algo, dict):
        p = global_algo.get("params") if isinstance(global_algo.get("params"), dict) else {}
        if p.get("enable_script"):
            hooks.append("hook_gp_script")
        if p.get("enable_domain"):
            hooks.append("hook_gp_domain")
        if p.get("enable_wire"):
            hooks.append("hook_gp_wire")
    title = _generate_title(s, g, cam, top, mood, fingerprint)
    music_var = (
        "longform_dj_remix" if online else "seed_loop_with_parametric_drift"
    )
    splash_bars = max(4, int(seq_length))

    # WORLD_FACTORS_2026: world coordinates ride the composition fingerprint,
    # so even the same seed yields a different objective/difficulty/level pack
    # whenever the composition changes — highest divergence, still deterministic.
    world_fp = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()[:16]
    objective = OBJECTIVES[_res_idx(s, f"objective|{world_fp}", len(OBJECTIVES))]
    difficulty = DIFFICULTIES[_res_idx(s, f"difficulty|{world_fp}", len(DIFFICULTIES))]
    level_type = LEVEL_TYPES[_res_idx(s, f"level|{world_fp}", len(LEVEL_TYPES))]
    sigil_count = 5 + _res_idx(s, f"sigils|{world_fp}", 8)  # 5..12
    world_fp = hashlib.sha256(
        f"{world_fp}|ob={objective}|df={difficulty}|lv={level_type}|s={sigil_count}"
        .encode("utf-8")
    ).hexdigest()[:16]

    return GameIdentity(
        seed=float(seed),
        title=title,
        genre=g,
        camera=cam,
        topology=top,
        social=soc,
        mood=mood,
        online=online,
        host_port=int(host_port),
        model_sets_1d=models_1d,
        model_sets_2d=models_2d,
        model_sets_3d=models_3d,
        ui_palette=palette,
        gameplay_hooks=hooks,
        music_variation=music_var,
        composition_fingerprint=fingerprint,
        splash_bars=splash_bars,
        objective=objective,
        difficulty=difficulty,
        level_type=level_type,
        sigil_count=sigil_count,
        world_fingerprint=world_fp,
    )


def generate_game_script(identity: GameIdentity, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    """Emit a self-contained playable .py script for the classified game.

    Music/visuals remix simplified Groovebox dynamics: Meum phase, seed RNG,
    optional DJ-style macros, and a lightweight 3D scenograph analogue so
    long-session play keeps varying without leaving the deterministic lattice.
    """
    meta = composition_meta or {}
    bpm = float(meta.get("bpm", 120.0))
    seq = int(meta.get("seq_length", identity.splash_bars))
    idict = identity.to_dict()
    id_json = json.dumps(idict, indent=2)

    return textwrap.dedent(f'''\
#!/usr/bin/env python3
# Auto-generated by Groovebox Video-Game Generator
# Deterministic unique non-redundant game from composition seed {identity.seed}
# Fingerprint: {identity.composition_fingerprint}
"""
{identity.title}
  genre={identity.genre}  camera={identity.camera}  topology={identity.topology}
  social={identity.social}  mood={identity.mood}  online={identity.online}
"""
from __future__ import annotations
import hashlib, json, math, os, sys, time

MEUM = {MEUM}
PHI = {PHI}
MEUM_INV = 1.0 / MEUM
MEUM_NORM = (MEUM - 1.0) / MEUM
BPM = {bpm}
SEQ = {seq}
IDENTITY = json.loads({id_json!r})

def _mix(seed, label):
    d = hashlib.sha256(f"{{seed}}|{{label}}|{{MEUM:.12f}}".encode()).digest()
    return int.from_bytes(d[:8], "big")

def _safe_int_seed(value):
    try:
        v = float(value)
    except Exception:
        v = 0.0
    if not math.isfinite(v):
        v = 0.0
    if v == int(v) and abs(v) < 2**31:
        return int(v) & 0x7FFFFFFF
    return int.from_bytes(hashlib.sha256(repr(v).encode()).digest()[:4], "big") & 0x7FFFFFFF

def _residue(seed, label):
    blob = f"{{seed}}|{{label}}|{{MEUM:.12f}}".encode("utf-8")
    i = int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")
    return (i % 10_000_000) / 10_000_000.0

def meum_angle(k):
    """MEUM-packed circle angle: k·MEUM mod 1 collides with nothing."""
    return math.tau * ((float(k) * MEUM) % 1.0)

def residue_to_bipolar(r):
    """[0,1) residue -> [-1,1) bipolar — same transform as the main engine."""
    return r * 2.0 - 1.0

class TriggerSculptor:
    """Programmed instrument triggers — mirrors the app's DeterministicTriggerSculptor.

    Every scene object/video element is an *instrument*: it owns a density and a
    phase, both closed-form f(seed, i) residues, and fires on a looped step grid
        prob(t) = density[i] + 0.2·sin(2π(t/steps + phase[i]))
        on(t)   = residue(seed, "trig:{{i}}:{{t}}") < prob(t)
    Nothing is drawn or audible unless its instrument fires — no inserted waves,
    no raw random(), no free-running LCG. Objects are the same programmed
    triggers the music engine uses, modified only by these basic transforms.
    """
    def __init__(self, seed, count, steps=64):
        self.seed = int(seed) & 0x7FFFFFFF
        self.n = max(1, int(count))
        self.steps = max(16, int(steps))
        self.density = [0.15 + 0.70 * _residue(self.seed, f"trig_density:{{i}}") for i in range(self.n)]
        self.phase = [_residue(self.seed, f"trig_phase:{{i}}") for i in range(self.n)]
    def active(self, i, t):
        t = int(t) % self.steps
        prob = self.density[i] + 0.2 * math.sin(math.tau * (t / self.steps + self.phase[i]))
        return _residue(self.seed, f"trig:{{i}}:{{t}}") < prob

class ScenographLite:
    """3D scene analogue where each object *is* an instrument trigger.

    Appearance (yaw/pitch/dist/hue) and fire timing are pure f(seed, i, beat)
    residues + the instrument mask; layers only animate in the beat/frame their
    instrument fires.
    """
    def __init__(self, seed, n=12):
        self.seed = int(seed) & 0x7FFFFFFF
        self.n = max(3, min(24, n))  # hard cap — never replicate past 24
        self.sculptor = TriggerSculptor(self.seed, self.n)
        self.beat = 0.0
        self.layers = []
        for i in range(self.n):
            self.layers.append({{
                "yaw": meum_angle(self.seed + i * 31),
                "pitch": residue_to_bipolar(_residue(self.seed, f"pitch:{{i}}")) * 0.4,
                "dist": 0.6 + 0.8 * _residue(self.seed, f"dist:{{i}}"),
                "hue": _residue(self.seed, f"hue:{{i}}"),
                "on": True,
            }})
    def tick(self, dt, audio_rms=0.2):
        self.beat += dt * (BPM / 60.0)
        step = int(self.beat)
        for i, L in enumerate(self.layers):
            L["on"] = bool(self.sculptor.active(i, step))
            if L["on"]:
                # Cyclic group action: fired layers advance on a Meum-scaled orbit
                L["yaw"] = (L["yaw"] + dt * (0.3 + 0.5 * MEUM * (i + 1) / self.n) * (0.7 + audio_rms)) % math.tau
            L["pitch"] = 0.4 * math.sin(self.beat * MEUM + i * PHI)
        return self.layers

class MusicBed:
    """Compositional dynamics simplified from Groovebox — seed loop + DJ drift."""
    def __init__(self, seed, bpm=BPM, bars=SEQ, algo_fp="0", dj_goava=False, dj_random=False, mix=0.35):
        self.seed = int(seed) & 0x7FFFFFFF
        self.bpm = bpm
        self.bars = bars
        self.phase = 0.0
        self.dj = 0.0
        self.dj_goava = bool(dj_goava)
        self.dj_random = bool(dj_random)
        self.mix = float(mix)
        # One-time residue "instrument" values — no per-frame randomness.
        self._dj_residue = _residue(self.seed, "dj_phase")
        self._algo_spin = (_mix(_safe_int_seed(seed), algo_fp or "0") % 10007) / 10007.0
    def step(self, dt):
        beat = self.bpm / 60.0
        self.phase = (self.phase + dt * beat * math.tau) % math.tau
        self.dj = 0.5 + 0.5 * math.sin(self.phase * MEUM + self._dj_residue * 0.01)
        if self.dj_goava:
            self.dj = 0.5 * self.dj + 0.5 * (0.5 + 0.5 * math.sin(self.phase * MEUM_INV))
        if self.dj_random:
            self.dj = (self.dj + 0.15 * math.sin(self.phase * PHI + self._algo_spin)) % 1.0
        g = self.mix * math.sin(self.phase * (1.0 + self._algo_spin) * MEUM)
        sample = math.sin(self.phase) * (0.4 + 0.6 * self.dj)
        sample += 0.2 * math.sin(self.phase * (2.0 + MEUM * self.dj))
        sample += 0.15 * g
        return sample

class SigilRing:
    """Deterministic collectible world — MEUM-packed angles, residue radii.

    The ring is a closed-form f(seed, k): sigil k sits at
        angle = meum_angle(seed_offset + k)
        radius = residue(seed, "sigil:{{k}}")
    No two sigils share an angle (MEUM mod 1 is collision-free), so the world
    is maximally divergent per seed and never redundant.
    """
    def __init__(self, seed, count=8, radius=0.9):
        self.seed = int(seed) & 0x7FFFFFFF
        self.count = max(3, min(24, int(count)))
        self.radius = float(radius)
        self.pos = [
            (meum_angle(_safe_int_seed(seed) + k * 31),
             0.3 + 0.6 * _residue(self.seed, f"sr{{k}}"))
            for k in range(self.count)
        ]
        self.collected = set()

    def proximity(self, angle, bias=0.0):
        """Closest uncollected sigil angular gap, MEUM-residue scaled."""
        best = math.tau
        for k, (a, r) in enumerate(self.pos):
            if k in self.collected:
                continue
            d = abs((a - angle + math.pi) % math.tau - math.pi)
            if d < best:
                best = d
        return best + bias

    def collect(self, angle, reach=0.31):
        """Collect every sigil within `reach` radians of the player orbit."""
        got = []
        for k, (a, r) in enumerate(self.pos):
            if k in self.collected:
                continue
            d = abs((a - angle + math.pi) % math.tau - math.pi)
            if d <= reach * max(0.25, r):
                self.collected.add(k)
                got.append((k, r))
        return got

    def remaining(self):
        return self.count - len(self.collected)

class Game:
    def __init__(self, host_mode=False, port=None):
        self.id = IDENTITY
        self.host_mode = bool(host_mode) and bool(self.id.get("online"))
        self.port = int(port or self.id.get("host_port") or 27015)
        self.scene = ScenographLite(self.id["seed"], n=8 + int(_residue(_safe_int_seed(self.id["seed"]), "scene_inst") * 8))
        self.music = MusicBed(self.id["seed"], algo_fp=self.id.get("composition_fingerprint", "0"), dj_goava="hook_live_dj_goava" in (self.id.get("gameplay_hooks") or []), dj_random="hook_live_dj_parametric" in (self.id.get("gameplay_hooks") or []), mix=0.35)
        # WORLD_FACTORS_2026: objective/difficulty/level pack from the identity
        self.objective = self.id.get("objective", "survey")
        self.difficulty = self.id.get("difficulty", "standard")
        self.level_type = self.id.get("level_type", "heightfield")
        self.difficulty_mult = {{
            "tutorial": 0.5, "standard": 1.0, "master": 1.7, "meum_insane": 2.4,
        }}.get(self.difficulty, 1.0)
        self.sigils = SigilRing(self.id["seed"], count=self.id.get("sigil_count", 8))
        self.combo = 0
        self.level = 1
        self.sigil_angle = meum_angle(_safe_int_seed(self.id["seed"]) * MEUM_INV)
        self.score = 0.0
        self.t = 0.0
        self.running = True
        # MULTIPLAYER_CHAT_AND_MODE_SWITCH: chat log + host/client role are
        # switchable at any point in the session (not just at launch), so a
        # local session can flip from client to host (e.g. if the host drops)
        # without restarting the game.
        self.chat_log = []
        self.player_name = self.id.get("player_name", "Player")

    def toggle_host_mode(self):
        """Flip host/client role at any time. Safe to call mid-session."""
        if not self.id.get("online"):
            print("[NET] host/client switch has no effect — social mode is not online_multiplayer.")
            return self.host_mode
        self.host_mode = not self.host_mode
        role = "HOST" if self.host_mode else "CLIENT"
        print(f"[NET] Role switched -> {{role}} (port {{self.port}})")
        self.send_chat("system", f"{{self.player_name}} is now {{role}}")
        return self.host_mode

    def send_chat(self, sender, text):
        """Append a chat line. Works in any social mode; only broadcasts to
        other peers when social is online_multiplayer or local_coop (stub —
        integrate real transport as needed, mirroring the host/client stub)."""
        entry = {{"t": round(self.t, 2), "sender": sender, "text": text}}
        self.chat_log.append(entry)
        print(f"[CHAT] {{sender}}: {{text}}")
        return entry
    def splash(self, duration=None):
        """Splash plays composition for SEQ bars before start screen."""
        bars = duration if duration is not None else self.id.get("splash_bars", SEQ)
        seconds = max(1.0, (60.0 / max(BPM, 1.0)) * 4.0 * bars)
        print(f"=== SPLASH: {{self.id['title']}} ===")
        print(f"Playing composition bed for {{seconds:.1f}}s ({{bars}} bars @ {{BPM}} BPM)...")
        t0 = time.time()
        while time.time() - t0 < min(seconds, 8.0):  # cap preview in CLI
            self.music.step(0.05)
            time.sleep(0.05)
        print("Splash complete.")
    def start_screen(self):
        print("--- START SCREEN ---")
        print(f"Genre: {{self.id['genre']}} | Camera: {{self.id['camera']}} | Topology: {{self.id['topology']}}")
        print(f"Social: {{self.id['social']}} | Mood: {{self.id['mood']}}")
        print(f"Objective: {{self.objective}} | Difficulty: {{self.difficulty}} (x{{self.difficulty_mult:.2f}})")
        print(f"Level pack: {{self.level_type}} | Sigil ring: {{self.sigils.count}} placed")
        print(f"World fingerprint: {{self.id.get('world_fingerprint', '-')}}")
        if self.id.get("online"):
            print(f"Online host port: {{self.port}}  (host_mode={{self.host_mode}})")
        print("Models 1D/2D/3D:", self.id["model_sets_1d"], self.id["model_sets_2d"], self.id["model_sets_3d"])
        print("Press Enter to play...")
        try:
            input()
        except EOFError:
            pass
    def tick(self, dt=1/30):
        sample = self.music.step(dt)
        layers = self.scene.tick(dt, audio_rms=abs(sample))
        # Player orbit advances on the MEUM-packed angle (closed-form, no rng)
        self.sigil_angle = (self.sigil_angle + dt * MEUM * math.tau) % math.tau
        # Gameplay hook driven by music phase — long-term variation stays on-lattice
        if abs(sample) > 0.7:
            self.score += MEUM * abs(sample) * self.difficulty_mult
        # Sigil collection: MEUM-packed angles, deterministic per frame
        got = self.sigils.collect(self.sigil_angle)
        for _k, r in got:
            self.combo += 1
            self.score += MEUM * r * self.difficulty_mult * self.combo
        # Level progression: threshold grows MEUM-linearly, never stalls a world
        threshold = 5 + self.level + int(MEUM * self.level)
        if self.combo >= threshold:
            self.level += 1
            self.difficulty_mult = min(3.0, self.difficulty_mult * (1.0 + MEUM_NORM * 0.4))
            self.send_chat("system", f"level {{self.level}} — difficulty x{{self.difficulty_mult:.2f}}")
            self.combo = 0
        self.t += dt
        return sample, layers
    def run(self, seconds=20.0):
        self.splash()
        self.start_screen()
        if self.id.get("online"):
            role = "HOST" if self.host_mode else "CLIENT"
            print(f"[NET] Starting as {{role}} on 0.0.0.0:{{self.port}} (stub — integrate real net stack as needed)")
            print("[NET] Console commands during play: /host  /client  /chat <message>  /report")
        print("--- PLAY ---")
        t0 = time.time()
        frames = 0
        while self.running and (time.time() - t0) < seconds:
            self.tick()
            frames += 1
            if frames % 60 == 0:
                print(f"t={{self.t:.1f}}s score={{self.score:.2f}} dj={{self.music.dj:.3f}} layers={{len(self.scene.layers)}} sigils={{self.sigils.remaining()}} lv={{self.level}}")
        print(f"Session end. Final score={{self.score:.2f}} level={{self.level}} "
              f"sigils={{self.sigils.count - self.sigils.remaining()}}/{{self.sigils.count}} "
              f"fingerprint={{self.id['composition_fingerprint']}} world={{self.id.get('world_fingerprint', '-')}}")

    def report(self):
        """Deterministic world report (also available as --report at launch)."""
        return {{
            "title": self.id["title"],
            "genre": self.id["genre"],
            "camera": self.id["camera"],
            "topology": self.id["topology"],
            "social": self.id["social"],
            "mood": self.id["mood"],
            "objective": self.objective,
            "difficulty": self.difficulty,
            "level_type": self.level_type,
            "sigil_count": self.sigils.count,
            "host_port": self.port,
            "online": bool(self.host_mode or self.id.get("online")),
            "composition_fingerprint": self.id["composition_fingerprint"],
            "world_fingerprint": self.id.get("world_fingerprint", "-"),
            "score": round(self.score, 3),
            "level": self.level,
            "t": round(self.t, 2),
        }}

    def handle_console_command(self, line):
        """Route a console line to chat or a host/client role switch — callable
        anywhere in the session, not just at startup."""
        line = (line or "").strip()
        if not line:
            return
        if line in ("/host", "/client"):
            wants_host = line == "/host"
            if wants_host != self.host_mode:
                self.toggle_host_mode()
            else:
                print(f"[NET] Already {{'HOST' if self.host_mode else 'CLIENT'}}.")
        elif line.startswith("/chat "):
            self.send_chat(self.player_name, line[len("/chat "):])
        elif line in ("/report", "/world"):
            print(json.dumps(self.report(), indent=2))
        else:
            self.send_chat(self.player_name, line)

def main(argv=None):
    argv = list(argv or sys.argv[1:])
    host = "--host" in argv
    port = None
    for a in argv:
        if a.startswith("--port="):
            try:
                port = int(a.split("=", 1)[1])
            except Exception:
                port = None
    if "--report" in argv:
        # Headless deterministic world report — same seed + identity always
        # prints the same JSON. Useful for CI/parity checks of the lattice.
        g = Game(host_mode=host, port=port)
        print(json.dumps(g.report(), indent=2, sort_keys=True))
        return
    Game(host_mode=host, port=port).run()

if __name__ == "__main__":
    main()
''')


def export_game_files(identity: GameIdentity, out_dir: str, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    script_path = os.path.join(out_dir, f"game_{identity.composition_fingerprint}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(generate_game_script(identity, composition_meta))
    meta_path = os.path.join(out_dir, f"game_{identity.composition_fingerprint}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(identity.to_dict(), f, indent=2)
    _write_launchers(out_dir, identity.composition_fingerprint)
    return script_path


_GAME_FILENAME = "game_{fingerprint}.py"

LAUNCH_SCRIPTS = {
    "launch_windows.bat": (
        "@echo off\r\n"
        "rem Launcher for the Groovebox video-game package (Windows).\r\n"
        "rem Determinstic f(seed) world — the same script gives the same world.\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set GAME={script}\r\n"
        "where pythonw >nul 2>nul && (start \"\" pythonw \"%GAME%\" & exit /b 0)\r\n"
        "where py >nul 2>nul && (start \"\" py \"%GAME%\" & exit /b 0)\r\n"
        "python \"%GAME%\"\r\n"
        "pause\r\n"
    ),
    "launch_macos.command": (
        "#!/bin/bash\n"
        "# Launcher for the Groovebox video-game package (macOS).\n"
        "# Deterministic f(seed) world — the same script gives the same world.\n"
        "cd \"$(dirname \"$0\")\"\n"
        "GAME={script}\n"
        "python3 \"$GAME\" || python \"$GAME\"\n"
    ),
    "launch_linux.sh": (
        "#!/usr/bin/env bash\n"
        "# Launcher for the Groovebox video-game package (Linux).\n"
        "# Deterministic f(seed) world — the same script gives the same world.\n"
        "cd \"$(dirname \"$0\")\"\n"
        "GAME={script}\n"
        "python3 \"$GAME\" || python \"$GAME\"\n"
    ),
}


def _write_launchers(out_dir: str, fingerprint: str) -> None:
    """Write the three OS launchers beside the exported game. Unix launchers get
    their executable bit set so they run straight out of the unpacked package."""
    script = _GAME_FILENAME.format(fingerprint=fingerprint)
    for name, template in LAUNCH_SCRIPTS.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\r\n" if name.endswith(".bat") else "\n") as f:
            f.write(template.format(script=script))
        if name.endswith((".sh", ".command")):
            try:
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass


def package_game_zip(identity: GameIdentity, out_zip: str, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    """Package a videogame export as a single .zip: deterministic game script +
    identity JSON + Windows/macOS/Linux launchers. Unix executables keep their
    mode attribute inside the archive so they are runnable after extraction."""
    tmpdir = tempfile.mkdtemp(prefix="groovebox_game_pkg_")
    try:
        export_game_files(identity, tmpdir, composition_meta)
        os.makedirs(os.path.dirname(os.path.abspath(out_zip)) or ".", exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(os.listdir(tmpdir)):
                src = os.path.join(tmpdir, name)
                st = os.stat(src)
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                mode = (st.st_mode & 0o777)
                if name.endswith((".sh", ".command")):
                    mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                info.external_attr = (mode & 0xFFFF) << 16
                with open(src, "rb") as fh:
                    zf.writestr(info, fh.read())
        return os.path.abspath(out_zip)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
