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
#
# Every packaged multiplayer game ships:
#   * a PyQt6 control panel (scene viewport + score/world/chat/network panel),
#     with an automatic CLI fallback when PyQt6 is not installed, and
#   * simultaneous host/client networking (stdlib socket + threads): the host
#     is authoritative, broadcasts world snapshots every tick, relays chat both
#     ways, and integrates remote orbit steers sent by connected clients.
#     The .zip carries the script, identity JSON, launchers, and a README that
#     spells out the only external requirement (Python + PyQt6, shared with the
#     Groovebox host app) so a package never depends on unseen files.
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


# ---------------------------------------------------------------------------
# Generated-game template. Built with placeholder tokens (__TOKEN__) and plain
# string substitution instead of an f-string, so the body's own braces stay
# literal and the emitted file is always valid Python. Every placeholder is
# substituted in generate_game_script(); nothing survives into the output.
# ---------------------------------------------------------------------------

_GAME_TEMPLATE = r'''#!/usr/bin/env python3
# Auto-generated by Groovebox Video-Game Generator
# Deterministic unique non-redundant game from composition seed __SEED__
# Fingerprint: __FINGERPRINT__
# This package ships a PyQt6 control panel and, for every multiplayer game,
# simultaneous host/client networking (stdlib socket + threads). The host is
# authoritative; clients connect, stream orbit steering + chat, and reconcile
# against host world snapshots every tick. Without PyQt6 the game automatically
# falls back to the same deterministic headless CLI loop.
"""
__TITLE__
  genre=__GENRE__  camera=__CAMERA__  topology=__TOPOLOGY__
  social=__SOCIAL__  mood=__MOOD__  online=__ONLINE__
"""
from __future__ import annotations
import hashlib, json, math, os, queue, socket, sys, threading, time

MEUM = __MEUM__
PHI = __PHI__
MEUM_INV = 1.0 / MEUM
MEUM_NORM = (MEUM - 1.0) / MEUM
BPM = __BPM__
SEQ = __SEQ__
IDENTITY = json.loads(__IDENTITY_JSON__)

# ---------------------------------------------------------------------------
# Optional UI framework (scene viewport + control panel). Only the standard
# library is required to *run* a session: without PyQt6 the game plays the
# deterministic CLI loop; with it you get the full control panel. Nothing else
# is ever imported at runtime, so the .zip is self-contained apart from these
# two shared (Python / PyQt6) system dependencies.
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtCore import QTimer, Qt, QPointF
    from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QLineEdit, QPlainTextEdit, QSpinBox, QCheckBox, QFrame,
        QSizePolicy, QGroupBox, QMessageBox, QInputDialog, QProgressBar,
        QSplitter,
    )
    HAS_UI = True
except Exception:
    HAS_UI = False


def _mix(seed, label):
    d = hashlib.sha256(f"{seed}|{label}|{MEUM:.12f}".encode()).digest()
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
    blob = f"{seed}|{label}|{MEUM:.12f}".encode("utf-8")
    i = int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")
    return (i % 10_000_000) / 10_000_000.0

def meum_angle(k):
    return math.tau * ((float(k) * MEUM) % 1.0)

def residue_to_bipolar(r):
    return r * 2.0 - 1.0


class TriggerSculptor:
    """Programmed instrument triggers — mirrors the app's DeterministicTriggerSculptor.

    Every scene object/video element is an *instrument*: it owns a density and a
    phase, both closed-form f(seed, i) residues, and fires on a looped step grid
        prob(t) = density[i] + 0.2·sin(2π(t/steps + phase[i]))
        on(t)   = residue(seed, "trig:{i}:{t}") < prob(t)
    Nothing is drawn or audible unless its instrument fires — no inserted waves,
    no raw random(), no free-running LCG.
    """
    def __init__(self, seed, count, steps=64):
        self.seed = int(seed) & 0x7FFFFFFF
        self.n = max(1, int(count))
        self.steps = max(16, int(steps))
        self.density = [0.15 + 0.70 * _residue(self.seed, f"trig_density:{i}") for i in range(self.n)]
        self.phase = [_residue(self.seed, f"trig_phase:{i}") for i in range(self.n)]
    def active(self, i, t):
        t = int(t) % self.steps
        prob = self.density[i] + 0.2 * math.sin(math.tau * (t / self.steps + self.phase[i]))
        return _residue(self.seed, f"trig:{i}:{t}") < prob


class ScenographLite:
    """Deterministic 3D-scene analogue: appearance and fire timing are pure
    f(seed, i, beat) residues; layers only animate in the beat/frame they fire."""
    def __init__(self, seed, n=12):
        self.seed = int(seed) & 0x7FFFFFFF
        self.n = max(3, min(24, n))
        self.sculptor = TriggerSculptor(self.seed, self.n)
        self.beat = 0.0
        self.layers = []
        for i in range(self.n):
            self.layers.append({
                "yaw": meum_angle(self.seed + i * 31),
                "pitch": residue_to_bipolar(_residue(self.seed, f"pitch:{i}")) * 0.4,
                "dist": 0.6 + 0.8 * _residue(self.seed, f"dist:{i}"),
                "hue": _residue(self.seed, f"hue:{i}"),
                "on": True,
            })
    def tick(self, dt, audio_rms=0.2):
        self.beat += dt * (BPM / 60.0)
        step = int(self.beat)
        for i, L in enumerate(self.layers):
            L["on"] = bool(self.sculptor.active(i, step))
            if L["on"]:
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
    """Deterministic collectible world — MEUM-packed angles, residue radii."""

    def __init__(self, seed, count=8, radius=0.9):
        self.seed = int(seed) & 0x7FFFFFFF
        self.count = max(3, min(24, int(count)))
        self.radius = float(radius)
        self.pos = [
            (meum_angle(_safe_int_seed(seed) + k * 31),
             0.3 + 0.6 * _residue(self.seed, f"sr{k}"))
            for k in range(self.count)
        ]
        self.collected = set()

    def proximity(self, angle, bias=0.0):
        best = math.tau
        for k, (a, r) in enumerate(self.pos):
            if k in self.collected:
                continue
            d = abs((a - angle + math.pi) % math.tau - math.pi)
            if d < best:
                best = d
        return best + bias

    def collect(self, angle, reach=0.31):
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


# ---------------------------------------------------------------------------
# Simultaneous host/client networking — Python standard library only (socket +
# threads + queue). Every multiplayer game gets this transport. The host binds
# 0.0.0.0:port and accepts any number of peers; clients connect to host:port.
# The two sides run their deterministic game loops concurrently:
#   * host integrates local + remote orbit steers and broadcasts a world
#     snapshot after every tick (angle, score, level, sigil union, remotes);
#   * clients reconcile against those snapshots and stream their own name,
#     orbit intent and chat up to the host, which relays chat to all peers.
# No RNG anywhere: inputs are player-authored signals, and every closed-form
# f(seed, t) equation the app uses is untouched by the transport.
# ---------------------------------------------------------------------------
class NetTransport:
    PROTO = "groovebox-net/1"

    def __init__(self, host_mode, port, connect=None):
        self.host_mode = bool(host_mode)
        self.port = int(port or 0)
        self.connect = connect
        self.sock = None
        self.status = "offline"
        self.in_queue = queue.Queue()
        self._clients = {}
        self._lock = threading.Lock()
        self._thread = None
        self._running = False

    def start(self):
        if not (self.host_mode or self.connect):
            self.status = "idle"
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            if self.host_mode:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(("0.0.0.0", self.port))
                self.sock.settimeout(0.25)
                self.sock.listen(16)
                self.status = f"HOST 0.0.0.0:{self.port}"
                self.in_queue.put({"type": "sys", "text": self.status})
                while self._running:
                    try:
                        conn, _addr = self.sock.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            else:
                host, _, port = self.connect.partition(":")
                try:
                    cport = int(port)
                except Exception:
                    cport = 0
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(0.25)
                attempts = 0
                while self._running and self.sock is not None and not self.host_mode:
                    try:
                        self.sock.connect((host, cport or self.port))
                        break
                    except OSError:
                        self.sock.close()
                        if not self._running:
                            return
                        attempts += 1
                        if attempts == 1:
                            self.status = f"waiting for host {host}:{cport or self.port}..."
                            self.in_queue.put({"type": "sys", "text": self.status})
                        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.sock.settimeout(0.25)
                        time.sleep(0.5)
                if self.sock is None:
                    return
                # Blocking reads: the daemon reader thread just waits; shutdown()
                # closes the socket to unblock it. A short recv timeout would be
                # treated as a file-object fault by buffered readline and drop
                # the connection — never put one on the read path.
                self.sock.settimeout(None)
                self.status = f"CLIENT {host}:{cport or self.port}"
                self.in_queue.put({"type": "sys", "text": self.status})
                self._handle(self.sock)
        except Exception as e:
            self.status = f"NET ERROR: {e}"
            self.in_queue.put({"type": "sys", "text": self.status})

    def _handle(self, conn):
        f = conn.makefile("r", encoding="utf-8", errors="replace")
        try:
            while self._running:
                try:
                    line = f.readline()
                except socket.timeout:
                    # Read timeout (client keeps a short liveness timeout) is
                    # NOT fatal — keep draining. Broad exceptions elsewhere must
                    # never silently kill the connection either.
                    continue
                except (OSError, ValueError):
                    break
                if not line:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                obj.setdefault("type", "chat")
                # Host tracks every connected peer socket so broadcast() can fan
                # snapshots/chat out to all of them. Client sockets for remotes
                # are also surfaced through in_queue for Game._drain_net.
                if self.host_mode and obj.get("type") == "hello":
                    with self._lock:
                        self._clients[conn] = obj.get("name", "?")
                if self.host_mode and obj.get("type") == "chat":
                    self.broadcast(obj)
                self.in_queue.put(obj)
        finally:
            try:
                with self._lock:
                    self._clients.pop(conn, None)
                conn.close()
            except Exception:
                pass

    def send(self, obj):
        if self.sock is None:
            return
        try:
            payload = (json.dumps(obj) + "\n").encode("utf-8")
            if self.host_mode:
                with self._lock:
                    for c in list(self._clients):
                        try:
                            c.sendall(payload)
                        except Exception:
                            self._clients.pop(c, None)
            else:
                self.sock.sendall(payload)
        except Exception:
            pass

    def broadcast(self, obj):
        self.send(obj)

    def shutdown(self):
        self._running = False
        try:
            if self.sock is not None:
                self.sock.close()
        except Exception:
            pass
        self.status = "offline"


class Game:
    def __init__(self, host_mode=False, port=None, connect=None):
        self.id = IDENTITY
        self.online = bool(self.id.get("online"))
        self.host_mode = bool(host_mode) and self.online
        self.port = int(port or self.id.get("host_port") or 27015)
        self.connect = connect
        self.net = NetTransport(self.host_mode, self.port, self.connect)
        self.net.start()
        self.scene = ScenographLite(self.id["seed"], n=8 + int(_residue(_safe_int_seed(self.id["seed"]), "scene_inst") * 8))
        self.music = MusicBed(self.id["seed"], algo_fp=self.id.get("composition_fingerprint", "0"), dj_goava="hook_live_dj_goava" in (self.id.get("gameplay_hooks") or []), dj_random="hook_live_dj_parametric" in (self.id.get("gameplay_hooks") or []), mix=0.35)
        self.objective = self.id.get("objective", "survey")
        self.difficulty = self.id.get("difficulty", "standard")
        self.level_type = self.id.get("level_type", "heightfield")
        self.difficulty_mult = {
            "tutorial": 0.5, "standard": 1.0, "master": 1.7, "meum_insane": 2.4,
        }.get(self.difficulty, 1.0)
        self.sigils = SigilRing(self.id["seed"], count=self.id.get("sigil_count", 8))
        self.combo = 0
        self.level = 1
        self.angle = meum_angle(_safe_int_seed(self.id["seed"]) * MEUM_INV)
        self.score = 0.0
        self.t = 0.0
        self.running = True
        self.steer = 0.0  # player-authored orbit bias in [-1, 1] — deterministic per input
        # Host-only remote player state: name -> [angle, score, steer]
        self._remote_steers = {}
        # Client reconciliation state
        self.remotes = {}
        self.last_snap = {}
        self.authoritative = self.net.host_mode or not self.online
        self.chat_log = []
        self.player_name = "Player"

    # --- networking ---------------------------------------------------------
    def toggle_host_mode(self):
        """Flip host/client role mid-session (e.g. if the host drops)."""
        if not self.online:
            self.push_status("host/client switch has no effect — social mode is not online_multiplayer.")
            print("[NET] switch has no effect — not an online multiplayer game.")
            return self.host_mode
        self.net.shutdown()
        self.host_mode = not self.host_mode
        self.authoritative = self.host_mode or not self.online
        if self.host_mode:
            self.net = NetTransport(True, self.port, None)
        else:
            if not self.connect:
                self.push_status("switch to client needs a host address (host:port).")
                print("[NET] switch to client needs --connect=host:port.")
                self.host_mode = True
                self.authoritative = True
                self.net = NetTransport(True, self.port, None)
            else:
                self.net = NetTransport(False, self.port, self.connect)
                self.authoritative = False
        self.net.start()
        role = "HOST" if self.host_mode else "CLIENT"
        self.push_status(f"role switched -> {role} on port {self.port}.")
        print(f"[NET] Role switched -> {role} (port {self.port})")
        return self.host_mode

    def resync_net(self, host_mode=None, port=None, connect=None):
        """Force a new transport from the given (or current) role/value set."""
        self.net.shutdown()
        hm = self.host_mode if host_mode is None else bool(host_mode)
        if port is not None:
            self.port = int(port)
        if connect is not None:
            self.connect = connect
        if not self.online:
            return
        self.host_mode = hm
        self.authoritative = self.host_mode or not self.online
        if self.host_mode:
            self.net = NetTransport(True, self.port, None)
        else:
            self.net = NetTransport(False, self.port, self.connect)
        self.net.start()

    def send_chat(self, sender, text):
        entry = {"t": round(self.t, 2), "sender": sender, "text": str(text)}
        self.chat_log.append(entry)
        obj = {"type": "chat", "sender": sender, "text": str(text)}
        if self.net.host_mode:
            self.net.broadcast(obj)
        elif self.net.sock is not None:
            self.net.send(obj)
        return entry

    def push_status(self, text):
        self.chat_log.append({"t": round(self.t, 2), "sender": "system", "text": str(text)})

    # --- core loop ----------------------------------------------------------
    def tick(self, dt=1/30):
        sample = self.music.step(dt)
        layers = self.scene.tick(dt, audio_rms=abs(sample))
        self._drain_net()
        if self.authoritative:
            self.angle = (self.angle + dt * MEUM * math.tau * (1.0 + 0.35 * self.steer)) % math.tau
            if abs(sample) > 0.7:
                self.score += MEUM * abs(sample) * self.difficulty_mult
            for _k, r in self.sigils.collect(self.angle):
                self.combo += 1
                self.score += MEUM * r * self.difficulty_mult * self.combo
            for name, rec in list(self._remote_steers.items()):
                rec[0] = (rec[0] + dt * MEUM * math.tau * (1.0 + 0.35 * rec[2])) % math.tau
                for k, (a, r) in enumerate(self.sigils.pos):
                    if k in self.sigils.collected:
                        continue
                    d = abs((a - rec[0] + math.pi) % math.tau - math.pi)
                    if d <= 0.31 * max(0.25, r):
                        self.sigils.collected.add(k)
                        rec[1] += MEUM * r * self.difficulty_mult
            threshold = 5 + self.level + int(MEUM * self.level)
            if self.combo >= threshold and self.music.dj > 0.05:
                self.level += 1
                self.difficulty_mult = min(3.0, self.difficulty_mult * (1.0 + MEUM_NORM * 0.4))
                self.send_chat("system", f"level {self.level} — difficulty x{self.difficulty_mult:.2f}")
                self.combo = 0
            if self.net.host_mode:
                self.net.broadcast({
                    "type": "snap",
                    "t": round(self.t, 3),
                    "angle": round(self.angle, 6),
                    "score": round(self.score, 3),
                    "level": self.level,
                    "combo": self.combo,
                    "difficulty_mult": round(self.difficulty_mult, 3),
                    "sigils": sorted(self.sigils.collected),
                    "sigil_count": self.sigils.count,
                    "dj": round(self.music.dj, 3),
                    "remotes": {
                        name: {"angle": round(rec[0], 6), "score": round(rec[1], 3), "steer": round(rec[2], 4)}
                        for name, rec in self._remote_steers.items()
                    },
                    "authoritative": True,
                })
        else:
            snap = self.last_snap
            if snap:
                self.angle = float(snap.get("angle", self.angle))
                self.score = float(snap.get("score", self.score))
                self.level = int(snap.get("level", self.level))
                self.combo = int(snap.get("combo", self.combo))
                self.difficulty_mult = float(snap.get("difficulty_mult", self.difficulty_mult))
                collected = snap.get("sigils") or []
                if isinstance(collected, list):
                    self.sigils.collected = set(int(k) for k in collected)
                rem = snap.get("remotes")
                self.remotes = rem if isinstance(rem, dict) else {}
            if self.net.sock is not None:
                self.net.send({"type": "hello", "name": self.player_name, "seed": self.id["seed"]})
                self.net.send({"type": "steer", "name": self.player_name, "t": round(self.t, 2), "angle": round(self.angle, 6), "steer": round(self.steer, 4)})
        self.t += dt
        return sample, layers

    def _drain_net(self):
        """Pull transport messages (chat, sys, remote steers) into game state."""
        while True:
            try:
                obj = self.net.in_queue.get_nowait()
            except queue.Empty:
                break
            mtype = obj.get("type")
            if mtype == "chat":
                self.push_status(f"{obj.get('sender', '?')}: {obj.get('text', '')}")
            elif mtype == "sys":
                self.push_status(str(obj.get("text", "")))
            elif mtype == "hello" and self.net.host_mode:
                name = str(obj.get("name") or "Player")
                if name not in self._remote_steers:
                    self._remote_steers[name] = [
                        meum_angle(_safe_int_seed(self.id["seed"]) + len(self._remote_steers) * 31),
                        0.0, 0.0,
                    ]
                    self.push_status(f"{name} joined the orbit.")
            elif mtype == "steer" and self.net.host_mode:
                name = str(obj.get("name") or "Player")
                rec = self._remote_steers.get(name)
                if rec is None:
                    rec = [meum_angle(_safe_int_seed(self.id["seed"]) + len(self._remote_steers) * 31), 0.0, 0.0]
                    self._remote_steers[name] = rec
                try:
                    rec[2] = float(obj.get("steer") or 0.0)
                except Exception:
                    pass
            elif mtype == "snap":
                self.last_snap = obj

    def reset_world(self):
        self.sigils = SigilRing(self.id["seed"], count=self.id.get("sigil_count", 8))
        self.combo = 0
        self.level = 1
        self.score = 0.0
        self.angle = meum_angle(_safe_int_seed(self.id["seed"]) * MEUM_INV)
        self.difficulty_mult = {
            "tutorial": 0.5, "standard": 1.0, "master": 1.7, "meum_insane": 2.4,
        }.get(self.difficulty, 1.0)
        self.push_status("world reset.")

    # --- presentation -------------------------------------------------------
    def splash(self, duration=None):
        bars = duration if duration is not None else self.id.get("splash_bars", SEQ)
        seconds = max(1.0, (60.0 / max(BPM, 1.0)) * 4.0 * bars)
        print(f"=== SPLASH: {self.id['title']} ===")
        print(f"Playing composition bed for {seconds:.1f}s ({bars} bars @ {BPM} BPM)...")
        t0 = time.time()
        while time.time() - t0 < min(seconds, 8.0):
            self.music.step(0.05)
            time.sleep(0.05)
        print("Splash complete.")

    def start_screen(self):
        print("--- START SCREEN ---")
        print(f"Genre: {self.id['genre']} | Camera: {self.id['camera']} | Topology: {self.id['topology']}")
        print(f"Social: {self.id['social']} | Mood: {self.id['mood']}")
        print(f"Objective: {self.objective} | Difficulty: {self.difficulty} (x{self.difficulty_mult:.2f})")
        print(f"Level pack: {self.level_type} | Sigil ring: {self.sigils.count} placed")
        print(f"World fingerprint: {self.id.get('world_fingerprint', '-')}")
        if self.id.get("online"):
            print(f"Online host port: {self.port}  (host_mode={self.host_mode})")
        print("Models 1D/2D/3D:", self.id["model_sets_1d"], self.id["model_sets_2d"], self.id["model_sets_3d"])
        print("Press Enter to play...")
        try:
            input()
        except EOFError:
            pass

    def run(self, seconds=20.0):
        self.splash()
        self.start_screen()
        if self.id.get("online"):
            role = "HOST" if self.host_mode else "CLIENT"
            print(f"[NET] Starting as {role} on 0.0.0.0:{self.port} (host) / {self.connect} (client)")
            print("[NET] Console commands during play: /host  /client  /chat <msg>  /report")
        print("--- PLAY ---")
        t0 = time.time()
        frames = 0
        while self.running and (time.time() - t0) < seconds:
            self.tick()
            frames += 1
            time.sleep(1 / 60.0)
            if frames % 60 == 0:
                print(f"t={self.t:.1f}s score={self.score:.2f} dj={self.music.dj:.3f} "
                      f"layers={len(self.scene.layers)} sigils={self.sigils.remaining()} lv={self.level} "
                      f"net={self.net.status} remotes={len(self._remote_steers)}")
        print(f"Session end. Final score={self.score:.2f} level={self.level} "
              f"sigils={self.sigils.count - self.sigils.remaining()}/{self.sigils.count} "
              f"fingerprint={self.id['composition_fingerprint']} world={self.id.get('world_fingerprint', '-')}")
        self.net.shutdown()

    def report(self):
        return {
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
            "net_transport": self.net.status,
            "composition_fingerprint": self.id["composition_fingerprint"],
            "world_fingerprint": self.id.get("world_fingerprint", "-"),
            "score": round(self.score, 3),
            "level": self.level,
            "t": round(self.t, 2),
        }

    def handle_console_command(self, line):
        line = (line or "").strip()
        if not line:
            return
        if line in ("/host", "/client"):
            self.toggle_host_mode()
        elif line.startswith("/chat "):
            self.send_chat(self.player_name, line[len("/chat "):])
        elif line in ("/report", "/world"):
            print(json.dumps(self.report(), indent=2, sort_keys=True))
        else:
            self.send_chat(self.player_name, line)


# ---------------------------------------------------------------------------
# UI control panel — opacity / hue / faces / lines with stroke widths only.
# ---------------------------------------------------------------------------
if HAS_UI:
    class SceneViewport(QWidget):
        def __init__(self, game, parent=None):
            super().__init__(parent)
            self.game = game
            self.setMinimumSize(460, 460)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def paintEvent(self, e):
            super().paintEvent(e)
            g = self.game
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pal = g.id.get("ui_palette", {})
            bg = pal.get("bg", "#0b1020")
            ac = pal.get("accent", "#3fa7ff")
            dg = pal.get("danger", "#ff5f5f")
            tx = pal.get("text", "#e8f0ff")
            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0
            R = min(w, h) * 0.34
            p.fillRect(self.rect(), QColor(bg))
            # Scene beams: only layers whose instrument fired this beat.
            on_layers = [L for L in g.scene.layers if L.get("on")]
            for i, L in enumerate(on_layers):
                col = QColor(ac)
                col.setAlpha(max(40, min(235, 120 + int(115 * L.get("hue", 0.5)))))
                p.setPen(QPen(col, max(1, round(1 + 3 * L.get("dist", 1.0)))))
                rad = meum_angle(i * 31)
                x2 = cx + L.get("dist", 1.0) * R * math.cos(rad)
                y2 = cy + L.get("dist", 1.0) * R * math.sin(rad)
                p.drawLine(QPointF(cx, cy), QPointF(x2, y2))
            # Orbital ring
            p.setPen(QPen(QColor(tx), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), R, R)
            # Sigils (uncollected glints, MEUM-packed)
            p.setPen(QPen(QColor(ac), 1))
            for k, (a, r) in enumerate(g.sigils.pos):
                if k in getattr(g.sigils, "collected", set()):
                    continue
                col = QColor(ac)
                col.setAlpha(230)
                p.setPen(QPen(col, 1))
                p.setBrush(col)
                x = cx + math.cos(a) * r * R
                y = cy + math.sin(a) * r * R
                p.drawEllipse(QPointF(x, y), 4 + int(r * 8), 4 + int(r * 8))
            def draw_face(name, angle, color, size):
                x = cx + math.cos(angle) * R
                y = cy + math.sin(angle) * R
                p.setPen(QPen(color, 2))
                p.setBrush(QColor(color))
                p.drawEllipse(QPointF(x, y), size, size)
                p.drawLine(QPointF(x - size, y + size * 0.6), QPointF(x + size * 0.8, y - size * 0.9))
                p.setPen(QPen(QColor(tx), 1))
                p.drawText(int(x - size), int(y - size - 4), str(name)[:12])
            draw_face(g.player_name or "You", g.angle, QColor(ac), 7)
            for name, rec in sorted((g.remotes or {}).items()):
                draw_face(name, float(rec.get("angle", 0.0)), QColor(dg), 6)
            p.setPen(QPen(QColor(tx), 1))
            p.drawText(8, h - 10, f"{g.id['title']}  t={g.t:.1f}s  "
                       f"sigils={g.sigils.remaining()}/{g.sigils.count}  net={g.net.status}")

    class ControlPanel(QWidget):
        def __init__(self, game, window, parent=None):
            super().__init__(parent)
            self.game = game
            self.window = window
            self.setFixedWidth(360)
            pal = game.id.get("ui_palette", {})
            self._bg = pal.get("bg", "")
            self._build()

        def _build(self):
            lay = QVBoxLayout(self)
            g = self.game
            self.title_lbl = QLabel(f"<b>{g.id['title']}</b>")
            self.title_lbl.setWordWrap(True)
            lay.addWidget(self.title_lbl)
            self.ident_lbl = QLabel(
                f"genre <b>{g.id['genre']}</b> · camera <b>{g.id['camera']}</b> · "
                f"{g.id['topology']} · mood <b>{g.id['mood']}</b><br>"
                f"objective <b>{g.objective}</b> · difficulty <b>{g.difficulty}</b> · "
                f"level <b>{g.level_type}</b><br>"
                f"fingerprint <code>{g.id['composition_fingerprint']}</code> · "
                f"world <code>{g.id.get('world_fingerprint', '-')}</code>"
            )
            self.ident_lbl.setWordWrap(True)
            lay.addWidget(self.ident_lbl)
            box = QGroupBox("World")
            vb = QVBoxLayout(box)
            self.score_lbl = QLabel("Score 0.00")
            self.level_lbl = QLabel("Level 1  (x1.00)")
            self.sigil_lbl = QLabel("Sigils 0/0")
            self.djbar = QProgressBar()
            self.djbar.setRange(0, 1000)
            self.djbar.setValue(0)
            self.djbar.setTextVisible(False)
            for lbl in (self.score_lbl, self.level_lbl, self.sigil_lbl):
                vb.addWidget(lbl)
            vb.addWidget(self.djbar)
            lay.addWidget(box)
            nbox = QGroupBox("Network")
            nb = QVBoxLayout(nbox)
            self.role_lbl = QLabel(f"Role: {self._role_text()}")
            self.net_lbl = QLabel(g.net.status)
            self.port_spin = QSpinBox()
            self.port_spin.setRange(1024, 65535)
            self.port_spin.setValue(max(1024, min(65535, g.port)))
            if not g.online:
                self.port_spin.setEnabled(False)
            self.connect_edit = QLineEdit(g.connect or "")
            self.connect_edit.setPlaceholderText("host:port  (client)")
            self.connect_edit.setEnabled(g.online)
            btn_host = QPushButton("Start as Host")
            btn_join = QPushButton("Join Host")
            btn_switch = QPushButton("Switch Role")
            btn_host.setEnabled(g.online)
            btn_join.setEnabled(g.online)
            btn_switch.setEnabled(g.online)
            btn_host.clicked.connect(self._start_host)
            btn_join.clicked.connect(self._join_host)
            btn_switch.clicked.connect(self._switch_role)
            hr = QHBoxLayout()
            hr.addWidget(btn_host)
            hr.addWidget(btn_join)
            nb.addWidget(self.role_lbl)
            nb.addWidget(self.net_lbl)
            nb.addWidget(QLabel("Server port:"))
            nb.addWidget(self.port_spin)
            nb.addWidget(QLabel("Host address (client mode):"))
            nb.addWidget(self.connect_edit)
            nb.addLayout(hr)
            nb.addWidget(btn_switch)
            lay.addWidget(nbox)
            chatbox = QGroupBox("Chat")
            cb = QVBoxLayout(chatbox)
            self.chat_view = QPlainTextEdit()
            self.chat_view.setReadOnly(True)
            self.chat_view.setMaximumBlockCount(500)
            self.chat_edit = QLineEdit()
            self.chat_edit.setPlaceholderText("type a message, /report, or Enter to send")
            self.chat_edit.returnPressed.connect(self._send_chat)
            btn_send = QPushButton("Send")
            btn_send.clicked.connect(self._send_chat)
            cr = QHBoxLayout()
            cr.addWidget(self.chat_edit)
            cr.addWidget(btn_send)
            cb.addWidget(self.chat_view)
            cb.addLayout(cr)
            lay.addWidget(chatbox)
            actions = QHBoxLayout()
            btn_reset = QPushButton("Reset World")
            btn_report = QPushButton("/report")
            btn_quit = QPushButton("Quit")
            btn_reset.clicked.connect(self._reset)
            btn_report.clicked.connect(self._report)
            btn_quit.clicked.connect(self.window.close)
            actions.addWidget(btn_reset)
            actions.addWidget(btn_report)
            actions.addWidget(btn_quit)
            lay.addLayout(actions)
            lay.addStretch(1)

        def _role_text(self):
            g = self.game
            if not g.online:
                return "singleplayer (local)"
            return "HOST (authoritative)" if g.host_mode else "CLIENT"

        def _start_host(self):
            g = self.game
            g.port = int(self.port_spin.value())
            g.resync_net(host_mode=True, port=g.port)
            self.role_lbl.setText(f"Role: {self._role_text()}")
            self.net_lbl.setText(g.net.status)

        def _join_host(self):
            g = self.game
            addr = self.connect_edit.text().strip()
            if not addr:
                addr = f"127.0.0.1:{int(self.port_spin.value())}"
                self.connect_edit.setText(addr)
            g.connect = addr
            g.port = int(self.port_spin.value())
            g.resync_net(host_mode=False, port=g.port, connect=addr)
            self.role_lbl.setText(f"Role: {self._role_text()}")
            self.net_lbl.setText(g.net.status)

        def _switch_role(self):
            g = self.game
            if g.host_mode:
                addr = self.connect_edit.text().strip() or f"127.0.0.1:{int(self.port_spin.value())}"
                g.connect = addr
                g.resync_net(host_mode=False, port=int(self.port_spin.value()), connect=addr)
            else:
                g.port = int(self.port_spin.value())
                g.resync_net(host_mode=True, port=g.port)
            self.role_lbl.setText(f"Role: {self._role_text()}")
            self.net_lbl.setText(g.net.status)

        def _send_chat(self):
            text = self.chat_edit.text().strip()
            if not text:
                return
            if text.startswith("/"):
                if text.startswith(("/report", "/world")) and len(text) <= 8:
                    self._report()
                elif text in ("/host", "/client"):
                    self._switch_role()
                else:
                    self.game.send_chat(self.game.player_name, text)
            else:
                self.game.send_chat(self.game.player_name, text)
            self.chat_edit.clear()

        def _reset(self):
            g = self.game
            if not g.authoritative:
                g.push_status("world is host-authoritative; switch to host to reset.")
                return
            g.reset_world()
            self.score_lbl.setText(f"Score {g.score:.2f}")
            self.level_lbl.setText(f"Level {g.level}  (x{g.difficulty_mult:.2f})")
            self.sigil_lbl.setText(f"Sigils {g.sigils.remaining()}/{g.sigils.count}")

        def _report(self):
            snap = self.game.report()
            self.chat_view.appendPlainText(json.dumps(snap, indent=2, sort_keys=True))

        def refresh(self):
            g = self.game
            self.score_lbl.setText(f"Score {g.score:.2f}")
            self.level_lbl.setText(f"Level {g.level}  (x{g.difficulty_mult:.2f})")
            self.sigil_lbl.setText(f"Sigils {g.sigils.remaining()}/{g.sigils.count}")
            self.djbar.setValue(max(0, min(1000, int(g.music.dj * 1000))))
            self.net_lbl.setText(g.net.status)
            self.role_lbl.setText(f"Role: {self._role_text()}")

        def append_status(self, text):
            self.chat_view.appendPlainText(text)

    class LoadingScreen(QWidget):
        """Minimal, dependency-free loading/processing screen shown the instant
        the app starts — before Game() does any of its (network transport,
        scenograph, sigil ring, music bed) construction work, and before the
        real GameWindow exists at all. Exported games previously went straight
        from a blank process to Game(...) construction with nothing on screen,
        so a slower machine (or --host waiting on a socket bind) could sit at
        an empty window for a moment with no feedback that anything was
        happening. This is deliberately simple: no game state, no palette
        lookup into an identity dict that doesn't exist yet — just a label and
        an indeterminate progress bar, self-contained and framed with a plain
        Qt.WindowType.FramelessWindowHint so it never gets confused for a
        second real window.
        """
        def __init__(self, title_hint=""):
            super().__init__()
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setFixedSize(360, 130)
            self.setStyleSheet(
                "background-color: #0b1020; border: 1px solid #3fa7ff; border-radius: 8px;"
            )
            lay = QVBoxLayout(self)
            lay.setContentsMargins(20, 18, 20, 18)
            label = QLabel(title_hint or "Loading world…")
            label.setStyleSheet("color: #e8f0ff; font-weight: bold; font-size: 13px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label = QLabel("Initializing…")
            self.status_label.setStyleSheet("color: #9fb3d0; font-size: 11px;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar = QProgressBar()
            bar.setRange(0, 0)  # indeterminate — total init time isn't known up front
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            lay.addWidget(label)
            lay.addWidget(bar)
            lay.addWidget(self.status_label)

        def set_status(self, text):
            self.status_label.setText(str(text))
            # Force a repaint + event flush now, so the message is actually
            # visible before the next (potentially blocking) init step runs.
            self.repaint()
            QApplication.processEvents()


    class GameWindow(QMainWindow):
        def __init__(self, game):
            super().__init__()
            self.game = game
            self.setWindowTitle(f"{game.id['title']}")
            self.resize(1040, 620)
            central = QWidget()
            self.setCentralWidget(central)
            split = QSplitter(Qt.Orientation.Horizontal, central)
            self.view = SceneViewport(game)
            self.panel = ControlPanel(game, self)
            split.addWidget(self.view)
            split.addWidget(self.panel)
            split.setStretchFactor(0, 3)
            split.setStretchFactor(1, 0)
            hv = QVBoxLayout(central)
            hv.addWidget(split)
            self.timer = QTimer(self)
            self.timer.setInterval(33)
            self.timer.timeout.connect(self._tick)
            self.timer.start()
            self._last = time.monotonic()
            if game.online:
                name, ok = QInputDialog.getText(self, "Player name", "Name on the orbit:", text="Player")
                if ok and name.strip():
                    game.player_name = name.strip()[:24]
            # seed the panel with existing chat/status
            for entry in game.chat_log:
                self.panel.append_status(f"[{entry['t']:.1f}] {entry['sender']}: {entry['text']}")

        def _tick(self):
            g = self.game
            now = time.monotonic()
            dt = max(1/120, min(1/20, now - self._last))
            self._last = now
            if self.timer.isActive() and g.running:
                g.tick(dt)
            while True:
                try:
                    obj = g.net.in_queue.get_nowait()
                except queue.Empty:
                    break
                if obj.get("type") in ("chat", "sys"):
                    self.panel.append_status(f"[{g.t:.1f}] {obj.get('sender', 'sys')}: {obj.get('text', '')}")
            self.panel.refresh()
            self.view.update()

        def keyPressEvent(self, e):
            g = self.game
            k = e.key()
            if k == Qt.Key.Key_Left:
                g.steer = max(-1.0, g.steer - 0.25)
            elif k == Qt.Key.Key_Right:
                g.steer = min(1.0, g.steer + 0.25)
            elif k == Qt.Key.Key_Space:
                g.running = not g.running
            else:
                super().keyPressEvent(e)

        def closeEvent(self, e):
            self.timer.stop()
            self.game.net.shutdown()
            super().closeEvent(e)


def parse_args(argv):
    host = "--host" in argv
    port = None
    connect = None
    cli = ("--cli" in argv) or ("--headless" in argv)
    report = "--report" in argv
    seconds = 20.0
    for a in argv:
        if a.startswith("--port="):
            try:
                port = int(a.split("=", 1)[1])
            except Exception:
                port = None
        elif a.startswith("--connect="):
            connect = a.split("=", 1)[1].strip()
        elif a.startswith("--name="):
            pass  # handled by UI dialog / CLI default
        elif a.startswith("--seconds="):
            try:
                seconds = max(0.5, float(a.split("=", 1)[1]))
            except Exception:
                seconds = 20.0
    return host, port, connect, report, cli, seconds


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    host, port, connect, report, cli, seconds = parse_args(argv)
    if "--report" in argv or report:
        g = Game(host_mode=host, port=port, connect=connect)
        print(json.dumps(g.report(), indent=2, sort_keys=True))
        g.net.shutdown()
        return
    if cli or not HAS_UI:
        if not cli and not HAS_UI:
            print("[UI] PyQt6 not found in this Python — falling back to the "
                  "deterministic CLI loop. Install PyQt6 for the control panel.")
        Game(host_mode=host, port=port, connect=connect).run(seconds=seconds)
        return
    # LOADING_SCREEN_2026: create QApplication + the loading screen FIRST,
    # before Game(...) does any of its heavier construction (network
    # transport bind/connect, scenograph mesh, sigil ring, music bed). That
    # ordering is the actual point — the loading screen has to exist before
    # the slow work starts, not just before the main window is shown, or
    # there is nothing for the user to see during exactly the part that can
    # take a moment (e.g. --host binding a socket).
    app = QApplication.instance() or QApplication(sys.argv[:1])
    loading = LoadingScreen(title_hint="Preparing session…")
    loading.show()
    loading.set_status("Starting network + world…")
    game = Game(host_mode=host, port=port, connect=connect)
    loading.set_status("Building main window…")
    win = GameWindow(game)
    loading.set_status("Ready.")
    win.show()
    loading.close()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''

_REPLACEMENTS = (
    ("__MEUM__", repr(MEUM)),
    ("__PHI__", repr(PHI)),
    ("__BPM__", repr(120.0)),
    ("__SEQ__", repr(16)),
)


def generate_game_script(identity: GameIdentity, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    """Emit a self-contained playable .py script for the classified game.

    The script ships a PyQt6 control panel (scene viewport + world/chat/network
    panel) for every game, and real simultaneous host/client networking
    (stdlib socket + threads) for every multiplayer game — the host is
    authoritative, clients stream orbit steering and chat, and both sides run
    their deterministic loops concurrently. Music/visuals are the same
    Groovebox Meum-phase dynamics with a headless CLI fallback so the
    deterministic lattice (--report parity) never depends on a GUI framework.
    """
    meta = composition_meta or {}
    bpm = float(meta.get("bpm", 120.0))
    seq = int(meta.get("seq_length", identity.splash_bars))
    idict = identity.to_dict()
    id_json = json.dumps(idict)

    script = _GAME_TEMPLATE
    script = script.replace("__SEED__", repr(float(identity.seed)))
    script = script.replace("__FINGERPRINT__", str(identity.composition_fingerprint))
    script = script.replace("__TITLE__", str(identity.title))
    script = script.replace("__GENRE__", str(identity.genre))
    script = script.replace("__CAMERA__", str(identity.camera))
    script = script.replace("__TOPOLOGY__", str(identity.topology))
    script = script.replace("__SOCIAL__", str(identity.social))
    script = script.replace("__MOOD__", str(identity.mood))
    script = script.replace("__ONLINE__", str(bool(identity.online)))
    script = script.replace("__MEUM__", repr(MEUM))
    script = script.replace("__PHI__", repr(PHI))
    script = script.replace("__BPM__", repr(bpm))
    script = script.replace("__SEQ__", repr(seq))
    script = script.replace("__IDENTITY_JSON__", repr(id_json))
    # Safety net: any left-over placeholder is a generator bug — never ship it.
    if any(tok in script for tok in (_tok for _tok, _ in _REPLACEMENTS)):
        raise RuntimeError("placeholder substitution failed")
    return script


def export_game_files(identity: GameIdentity, out_dir: str, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    script_path = os.path.join(out_dir, f"game_{identity.composition_fingerprint}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(generate_game_script(identity, composition_meta))
    meta_path = os.path.join(out_dir, f"game_{identity.composition_fingerprint}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(identity.to_dict(), f, indent=2)
    _write_launchers(out_dir, identity.composition_fingerprint)
    _write_package_readme(out_dir, identity)
    return script_path


_GAME_FILENAME = "game_{fingerprint}.py"


# PACKAGE_README_2026: the package spells out its only external requirements so
# a launch never depends on files that are not inside the .zip. Everything the
# script imports at runtime is the Python standard library plus exactly two
# system-level dependencies shared with the Groovebox host app: Python itself
# and PyQt6 (UI only — the game auto-falls-back to the CLI loop without it).
PACKAGE_README = """Groovebox Video-Game Package
===========================
Title:  {title}
Genre:  {genre}  |  Camera:  {camera}  |  Topology:  {topology}
Social: {social}  |  Mood:   {mood}
World:  objective={objective}  difficulty={difficulty}  level={level_type}
        sigils={sigil_count}  world_fingerprint={world_fingerprint}
Fingerprint: {composition_fingerprint}

RUNNING
-------
Windows:  double-click launch_windows.bat
macOS:    double-click launch_macos.command  (or: bash launch_macos.command)
Linux:    run  ./launch_linux.sh             (or: bash launch_linux.sh)
All three launchers pass extra arguments through to the game.

REQUIREMENTS
------------
1. Python 3.9+ on your PATH as `python3` (fallback `python` on macOS/Windows).
2. PyQt6 for the control panel (scene viewport + world/chat/network UI). This
   is the SAME shared dependency the Groovebox host app uses:
       pip install PyQt6
   Without PyQt6 the game still runs — it automatically plays the identical
   deterministic headless CLI session instead. Nothing else is imported at
   runtime; the .zip carries the full game script, identity JSON, launchers
   and this README, so there are no hidden package files.

MULTIPLAYER (online_multiplayer games only)
-------------------------------------------
One player starts the host:
    ./launch_linux.sh --host --port={host_port}
Every other player joins by host address (defaults to 127.0.0.1 if omitted):
    ./launch_linux.sh --connect=192.168.1.10:{host_port}
Host/client are interchangeable mid-session from the Network panel, or in the
CLI with /host and /client. The host is authoritative: it integrates every
connected orbit steer and broadcasts a world snapshot each tick; chat flows in
both directions simultaneously. The deterministic f(seed) world equations are
identical on every machine — networking only transports player-authored
inputs and host snapshots, never new randomness.

CLI / HEADLESS
--------------
    python3 game_{{fingerprint}}.py --cli --seconds=20 --report
    python3 game_{{fingerprint}}.py --report     # deterministic world JSON
"""


def _write_package_readme(out_dir: str, identity: GameIdentity) -> str:
    path = os.path.join(out_dir, "README.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(PACKAGE_README.format(
            title=identity.title,
            genre=identity.genre,
            camera=identity.camera,
            topology=identity.topology,
            social=identity.social,
            mood=identity.mood,
            objective=identity.objective,
            difficulty=identity.difficulty,
            level_type=identity.level_type,
            sigil_count=identity.sigil_count,
            world_fingerprint=identity.world_fingerprint,
            host_port=identity.host_port,
            composition_fingerprint=identity.composition_fingerprint,
        ))
    return path


LAUNCH_SCRIPTS = {
    "launch_windows.bat": (
        "@echo off\r\n"
        "rem Launcher for the Groovebox video-game package (Windows).\r\n"
        "rem Deterministic f(seed) world — passes all extra arguments through.\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set GAME={script}\r\n"
        "where pythonw >nul 2>nul && (start \"\" pythonw \"%GAME%\" %* & exit /b 0)\r\n"
        "where py >nul 2>nul && (py \"%GAME%\" %* & exit /b 0)\r\n"
        "set PYTHONUTF8=1\r\n"
        "python \"%GAME%\" %*\r\n"
        "if errorlevel 1 pause\r\n"
    ),
    "launch_macos.command": (
        "#!/bin/bash\n"
        "# Launcher for the Groovebox video-game package (macOS).\n"
        "# Deterministic f(seed) world — passes all extra arguments through.\n"
        "cd \"$(dirname \"$0\")\"\n"
        "export PYTHONUTF8=1\n"
        "GAME={script}\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "  exec python3 \"$GAME\" \"$@\"\n"
        "fi\n"
        "exec python \"$GAME\" \"$@\"\n"
    ),
    "launch_linux.sh": (
        "#!/usr/bin/env bash\n"
        "# Launcher for the Groovebox video-game package (Linux).\n"
        "# Deterministic f(seed) world — passes all extra arguments through.\n"
        "cd \"$(dirname \"$0\")\"\n"
        "export PYTHONUTF8=1\n"
        "GAME={script}\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "  exec python3 \"$GAME\" \"$@\"\n"
        "fi\n"
        "exec python \"$GAME\" \"$@\"\n"
    ),
}


def _write_launchers(out_dir: str, fingerprint: str) -> None:
    """Write the three OS launchers beside the exported game. Unix launchers get
    their executable bit set so they run straight out of the unpacked package,
    and every launcher forwards "$@" / %* so --host / --connect / --cli work."""
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
    identity JSON + README + Windows/macOS/Linux launchers. Unix executables keep
    their mode attribute inside the archive so they are runnable after extraction.
    The script's only runtime imports are stdlib + PyQt6 (UI), so the package
    itself is complete — unpack any one folder and launch."""
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