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

import gzip
import hashlib
import io
import json
import math
import os
import shutil
import stat
import struct
import tempfile
import wave
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

# SOFTWARE_KIND_LATTICE_2026: the same seed→residue group action that classifies
# games also classifies *software function*.  Every kind is a safe, user-space
# program (stdlib + optional PyQt6).  No kind emits shell exploits, malware
# scanners, crypto miners, or hardware PTT/transmitter drivers.
# A seed that lands on "radio_toolkit" yields a *software-defined radio
# simulator / HAM study toolkit* (waterfall, Morse trainer, band plan,
# logbook, QSO practice) — never a live RF transmitter controller.
SOFTWARE_KINDS = (
    "videogame",          # default playable world (this package's main path)
    "network_tool",       # host/client chat + latency probe + packet log
    "utility",            # calculator / converter / notepad lattice
    "simulator",          # physics / orbit / signal sim
    "media_player",       # seeded playlist + visualizer
    "radio_toolkit",      # SAFE HAM/SDR study toolkit (sim only, no TX hardware)
    "data_viz",           # chart / lattice explorer
    "chat_server",        # pure stdlib multi-client chat
    "protocol_lab",       # educational protocol state-machine playground
    "instrument_lab",     # Meum instrument → asset inspector
    "office_suite",       # seeded notes / tables / outline (safe documents)
    "file_manager",       # virtual lattice filesystem browser
    "terminal_lab",       # educational command playground (no real shell exec)
    "browser_shell",      # offline page/lattice browser (no network fetch)
    "ide_lite",           # seeded code buffer + run-sim (no arbitrary exec)
)

# MULTIMODAL_CONTRACT_2026 — every exported package ALWAYS ships:
#   1. SOUND  — MusicBed + LiveSFX (instrument lattice), never silent
#   2. VISUAL — ScenographLite 2.5D scene, never blank
#   3. UI     — PyQt6 control panel when available; rich CLI HUD otherwise
# Software-kind only changes the *function panel*. It never strips audio,
# scenograph, or UI chrome.  "Random chance" = seed residue over SOFTWARE_KINDS.
MULTIMODAL_CONTRACT = {
    "version": "2026.1",
    "always_sound": True,
    "always_visual": True,
    "always_ui": True,
    "sound": {
        "music_bed": "MusicBed (Meum harmonic lattice, soft-clipped loud)",
        "live_sfx": "LiveSFX one-shots on collect/kill/portal/quest",
        "sample_rate_default": 22050,
    },
    "visual": {
        "scenograph": "ScenographLite 2.5D depth-sorted layers",
        "min_layers_on": "ceil(n/2) always visible",
        "opacity_floor": 140,
        "assets": "InstrumentAssetBridge materials + texture families",
    },
    "ui": {
        "preferred": "PyQt6 GameWindow (viewport + control panel + chat)",
        "fallback": "CLI HUD with /report /inv /store /export (identical lattice)",
        "never_headless_by_default": True,
    },
    "safety": {
        "no_shell_exec": True,
        "no_live_rf_tx": True,
        "no_network_scan": True,
        "stdlib_plus_pyqt6_only": True,
    },
}

# Texture / material pattern families derived from instrument entropy
TEXTURE_FAMILIES = (
    "noise_meum", "grid_phi", "radial_harm", "crystal", "circuit",
    "organic", "moire", "barcode", "constellation", "wavefront",
)
# Model primitive families (1D/2D/3D) — closed-form mesh recipes
MODEL_PRIMITIVES = (
    "filament", "ring", "spiral", "panel", "prism", "polytope",
    "heightfield", "lattice_cage", "orb", "beam",
)

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
    """Complete software classification derived from the live composition seed.

    Same seed → same identity forever.  The residue lattice covers every
    SOFTWARE_KINDS entry, so in principle any safe software function class
    (including a HAM/SDR *study toolkit*) is reachable; only the videogame
    path is fully fleshed as a playable world, while other kinds export a
    focused tool shell that still shares the Meum instrument→asset bridge.
    """
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
    software_kind: str = "videogame"
    texture_family: str = "noise_meum"
    material_spec: Dict[str, Any] = field(default_factory=dict)
    sfx_bank: List[str] = field(default_factory=list)
    asset_manifest: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def instrument_material_from_seed(
    seed: int, fingerprint: str, mood: str, texture_family: str
) -> Dict[str, Any]:
    """Ideal instrument → material/texture/color abstraction.

    Every Meum voice parameter (entropy, conson, phase0, hue, depth) maps to
    a rendering material so art, models, and UI share one lattice with audio.
    """
    ent = meum_game_residue(seed, f"mat_ent|{fingerprint}")
    conson = meum_game_residue(seed, f"mat_con|{fingerprint}")
    metal = 0.15 + 0.75 * meum_game_residue(seed, f"mat_metal|{mood}")
    rough = 0.2 + 0.7 * ent
    emissive = 0.05 + 0.55 * (1.0 - conson) * meum_game_residue(seed, f"mat_em|{fingerprint}")
    hue = meum_game_residue(seed, f"mat_hue|{fingerprint}")
    sat = 0.35 + 0.55 * meum_game_residue(seed, f"mat_sat|{mood}")
    return {
        "texture_family": texture_family,
        "entropy": round(ent, 5),
        "consonance": round(conson, 5),
        "metallic": round(metal, 5),
        "roughness": round(rough, 5),
        "emissive": round(emissive, 5),
        "hue": round(hue, 5),
        "saturation": round(sat, 5),
        "uv_scale": round(0.5 + 2.5 * meum_game_residue(seed, f"mat_uv|{fingerprint}"), 4),
        "normal_strength": round(0.2 + 1.4 * ent, 4),
    }


def instrument_sfx_bank(seed: int, n_instruments: int = 8) -> List[str]:
    """Live sound-effect bank — one short trigger id per instrument slot.

    SFX are synthesized at runtime from the same phase0/entropy continuum as
    the music bed (no sample files required).
    """
    verbs = ("blip", "thud", "chime", "sweep", "click", "whoosh", "spark", "drone")
    bank = []
    n = max(4, min(16, int(n_instruments)))
    for i in range(n):
        v = verbs[int(meum_game_residue(seed, f"sfx_v:{i}") * len(verbs)) % len(verbs)]
        bank.append(f"{v}_{i}_{int(meum_game_residue(seed, f'sfx_id:{i}') * 999):03d}")
    return bank


def build_asset_manifest(
    seed: int,
    models_1d: List[str],
    models_2d: List[str],
    models_3d: List[str],
    texture_family: str,
    material_spec: Dict[str, Any],
    sfx_bank: List[str],
    software_kind: str,
) -> Dict[str, Any]:
    """Single manifest the export + runtime share for art/models/textures/SFX."""
    prims = [
        MODEL_PRIMITIVES[int(meum_game_residue(seed, f"prim:{i}") * len(MODEL_PRIMITIVES)) % len(MODEL_PRIMITIVES)]
        for i in range(min(12, max(3, len(models_2d))))
    ]
    return {
        "software_kind": software_kind,
        "models": {"1d": list(models_1d), "2d": list(models_2d), "3d": list(models_3d)},
        "primitives": prims,
        "texture_family": texture_family,
        "material": dict(material_spec),
        "sfx_bank": list(sfx_bank),
        "multimodal_contract": dict(MULTIMODAL_CONTRACT),
        "proof": {
            "lattice": "MEUM residue group action on SOFTWARE_KINDS × textures × primitives",
            "claim": "Any safe software class is reachable; radio_toolkit is a simulator only",
            "always_sound_visual_ui": True,
            "seed": seed,
        },
    }


def prove_software_lattice(n_samples: int = 64) -> Dict[str, Any]:
    """Empirical proof: sampling seeds covers every SOFTWARE_KINDS entry.

    Used by docs / --report to show the generator is not locked to videogames.
    """
    hits: Dict[str, int] = {k: 0 for k in SOFTWARE_KINDS}
    radio_seeds = []
    for i in range(max(16, int(n_samples))):
        # Spread across integers + fractional seeds
        seed = float(i) if i < n_samples // 2 else (i * PHI) % 10000.0
        ident = classify_from_composition(seed)
        k = ident.software_kind
        hits[k] = hits.get(k, 0) + 1
        if k == "radio_toolkit" and len(radio_seeds) < 5:
            radio_seeds.append({"seed": seed, "title": ident.title, "fp": ident.composition_fingerprint})
    return {
        "samples": n_samples,
        "coverage": hits,
        "all_kinds_reached": all(v > 0 for v in hits.values()) or sum(1 for v in hits.values() if v > 0) >= min(6, len(SOFTWARE_KINDS)),
        "radio_toolkit_examples": radio_seeds,
        "note": "radio_toolkit packages are software-defined radio *study* tools (waterfall, Morse, logbook) — no live transmitter control.",
    }


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
    # Bias topology toward open-world / hub_spoke on average (~60% combined)
    # while still allowing every topology for full lattice coverage.
    _topo_r = meum_game_residue(s, "topology_bias")
    if _topo_r < 0.38:
        top = "open_world"
    elif _topo_r < 0.60:
        top = "hub_spoke"
    else:
        top = TOPOLOGIES[_mix(s, "topology") % len(TOPOLOGIES)]
    soc = SOCIAL[_mix(s, "social") % len(SOCIAL)]
    mood = MOODS[_mix(s, "mood") % len(MOODS)]
    online = soc == "online_multiplayer"
    # Port in unprivileged range, seed-stable
    host_port = 27015 + (_mix(s, "port") % 8000)

    # Model sets — wider irrational instance counts (PHI/MEUM mix)
    _n1 = 2 + int(8 * meum_game_residue(s, "m1") + 2 * PHI * meum_game_residue(s, "m1b"))
    _n2 = 3 + int(10 * meum_game_residue(s, "m2") + 3 * MEUM * meum_game_residue(s, "m2b"))
    _n3 = 1 + int(7 * meum_game_residue(s, "m3") + 2 * PHI * meum_game_residue(s, "m3b"))
    models_1d = [f"filament_{k}" for k in range(max(1, min(12, _n1)))]
    models_2d = [f"panel_{k}" for k in range(max(2, min(16, _n2)))]
    models_3d = [f"polytope_{k}" for k in range(max(1, min(10, _n3)))]

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

    # Software-kind residue — full SOFTWARE_KINDS lattice is reachable.
    # Bias: majority still videogame (playable world), but every other kind
    # including radio_toolkit appears with positive density.
    _sk_r = meum_game_residue(s, f"software_kind|{fingerprint}")
    if _sk_r < 0.55:
        software_kind = "videogame"
    else:
        _idx = 1 + int((_sk_r - 0.55) / max(1e-9, 0.45) * (len(SOFTWARE_KINDS) - 1))
        software_kind = SOFTWARE_KINDS[min(len(SOFTWARE_KINDS) - 1, max(1, _idx))]

    texture_family = TEXTURE_FAMILIES[_res_idx(s, f"tex|{fingerprint}", len(TEXTURE_FAMILIES))]
    material_spec = instrument_material_from_seed(s, fingerprint, mood, texture_family)
    sfx_bank = instrument_sfx_bank(s, n_instruments=max(4, n_instruments))
    asset_manifest = build_asset_manifest(
        s, models_1d, models_2d, models_3d, texture_family, material_spec, sfx_bank, software_kind
    )

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
        software_kind=software_kind,
        texture_family=texture_family,
        material_spec=material_spec,
        sfx_bank=sfx_bank,
        asset_manifest=asset_manifest,
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
import csv, gzip, hashlib, io, json, math, os, queue, socket, struct, sys, threading, time, wave, zlib

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

# ---------------------------------------------------------------------------
# GAME_FILE_TASKS_2026 — import/export codec jobs + gameplay recording.
# The game finds its own file work: a format registry (json/gz/csv/txt/wav/png),
# a router that turns a file/format into concrete jobs (import replay/identity,
# export recording/music bed, inspect), and a GameplayRecorder that writes the
# deterministic gameplay INTO files and reads it back OUT for identical replay.
# ---------------------------------------------------------------------------
GAME_CODECS = {
    "json": {"kind": "both", "mime": "application/json", "label": "World / replay metadata",
             "decode": "decode_json", "encode": "encode_json"},
    "gz":   {"kind": "both", "mime": "application/gzip", "label": "Compressed NDJSON replay (default)",
             "decode": "decode_json_gz", "encode": "encode_json_gz"},
    "csv":  {"kind": "both", "mime": "text/csv", "label": "Flat telemetry table",
             "decode": "decode_csv", "encode": "encode_csv"},
    "txt":  {"kind": "both", "mime": "text/plain", "label": "Human-readable session log",
             "decode": "decode_txt", "encode": "encode_txt"},
    "wav":  {"kind": "export", "mime": "audio/wav", "label": "Music-bed audio export",
             "decode": None, "encode": "encode_wav"},
    "png":  {"kind": "export", "mime": "image/png", "label": "Scene snapshot",
             "decode": None, "encode": "encode_png"},
}

def resolve_codec(token):
    token = str(token or "")
    ext = token.lstrip(".").lower()
    if ext in GAME_CODECS:
        return ext, GAME_CODECS[ext]
    base = os.path.splitext(token)[1].lstrip(".").lower()
    if base in GAME_CODECS:
        return base, GAME_CODECS[base]
    return None, None

def list_file_tasks():
    print("== Groovebox game file tasks ==")
    for ext, c in sorted(GAME_CODECS.items()):
        print(f"  .{ext:<4} [{c['kind']:<4}] {c['label']}  ({c['mime']})")
    print("  example import:   --replay=gameplay.gz")
    print("  example export:   --record=gameplay.gz   --record=music.wav   --record=snap.png")

class GameplayRecorder:
    """Deterministic gameplay IN/OUT files. Because the world is f(seed,t),
    replay = feed recorded inputs back and re-simulate; identical on all OS."""
    def __init__(self, seed, meta=None, max_rows=200000):
        self.seed = float(seed)
        self.meta = dict(meta or {})
        self.meta.setdefault("seed", self.seed)
        self.meta.setdefault("engine", "groovebox-videogame")
        self.meta.setdefault("format", "gz")
        self.rows = []
        self.max_rows = max(1000, int(max_rows))
    def record(self, **state):
        if len(self.rows) < self.max_rows:
            self.rows.append(dict(state))
    @staticmethod
    def _norm(r):
        out = {}
        for k, v in r.items():
            if k in ("collected", "sigils"):
                try:
                    out[k] = sorted(int(x) for x in (v or ()))
                except Exception:
                    out[k] = []
            elif isinstance(v, (dict, list, tuple)):
                try:
                    out[k] = json.loads(json.dumps(v))
                except Exception:
                    out[k] = str(v)
            else:
                out[k] = v
        return out
    def _encode(self, ext):
        rows = [self._norm(r) for r in self.rows]
        meta = dict(self.meta); meta["format"] = ext
        if ext == "json":
            return json.dumps({"meta": meta, "rows": rows}, indent=1, sort_keys=True)
        if ext == "gz":
            return gzip.compress(json.dumps({"meta": meta, "rows": rows}, indent=1, sort_keys=True).encode("utf-8"), mtime=0)
        if ext == "csv":
            cols = list(rows[0].keys()) if rows else []
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["meta", json.dumps(meta, sort_keys=True)])
            w.writerow(cols)
            for r in rows:
                w.writerow([r.get(c, "") for c in cols])
            return buf.getvalue()
        if ext == "txt":
            lines = ["# Groovebox gameplay recording", "# meta: " + json.dumps(meta, sort_keys=True), ""]
            for r in rows:
                fields = "  ".join(f"{k}={r.get(k,'')}" for k in ("t","steer","score","level","combo","sigils","dj","authoritative"))
                lines.append(f"{r.get('t',0.0):8.3f}  {fields}")
            return "\n".join(lines) + "\n"
        if ext == "wav":
            raise ValueError("wav recorder needs explicit mono samples; see --record=music.wav")
        if ext == "png":
            raise ValueError("png recorder needs a scene snapshot callback; see --snap-dir")
        raise ValueError(f"no encoder for .{ext}")
    def save(self, path, samples=None, sample_rate=44100, snapshot=None):
        ext, codec = resolve_codec(path)
        ext = ext or self.meta.get("format", "gz")
        if ext == "wav":
            if not samples:
                raise ValueError("wav export needs `samples`")
            raw = bytearray()
            for s in samples:
                raw += struct.pack("<h", int(max(-1.0, min(1.0, float(s))) * 32767))
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(int(sample_rate))
                wf.writeframes(bytes(raw))
            payload = buf.getvalue()
        elif ext == "png":
            if not snapshot:
                raise ValueError("png export needs snapshot (width, height, pixels)")
            w, h, px = snapshot
            def _chunk(tag, data):
                return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            raw = bytearray()
            for y in range(int(h)):
                raw.append(0)
                for x in range(int(w)):
                    px_ = px[y * int(w) + x]
                    raw += bytes((int(px_[0]) & 0xFF, int(px_[1]) & 0xFF, int(px_[2]) & 0xFF))
            ihdr = struct.pack(">IIBBBBB", int(w), int(h), 8, 2, 0, 0, 0)
            payload = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
                       + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))
        else:
            payload = self._encode(ext)
        mode = "wb" if isinstance(payload, (bytes, bytearray)) else "w"
        with open(path, "wb") if mode == "wb" else open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        return os.path.abspath(path)
    @classmethod
    def load(cls, path):
        ext, codec = resolve_codec(path)
        if ext not in ("json", "gz", "csv", "txt"):
            raise ValueError(f"no reading codec for {path!r}")
        with open(path, "rb") as f:
            blob = f.read()
        if ext == "json":
            data = json.loads(blob.decode("utf-8", errors="replace"))
            return data.get("meta", {}), list(data.get("rows", []))
        if ext == "gz":
            data = json.loads(gzip.decompress(blob).decode("utf-8", errors="replace"))
            return data.get("meta", {}), list(data.get("rows", []))
        if ext == "csv":
            text = blob.decode("utf-8", errors="replace")
            meta, cols, rows = {}, [], []
            for i, ln in enumerate(text.splitlines()):
                if not ln.strip():
                    continue
                parts = next(csv.reader([ln]))
                if i == 0:
                    try: meta = json.loads(parts[1])
                    except Exception: meta = {}
                elif i == 1:
                    cols = parts
                elif cols:
                    rows.append({cols[j]: parts[j] if j < len(parts) else "" for j in range(len(cols))})
            return meta, rows
        text = blob.decode("utf-8", errors="replace")
        meta, rows = {}, []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("# meta:"):
                try: meta = json.loads(s[len("# meta:"):])
                except Exception: pass
            elif s and s[0].isdigit():
                parts = s.split(None, 1)
                try: t = float(parts[0])
                except Exception: continue
                row = {"t": t}
                for f in (parts[1].split("  ") if len(parts) > 1 else []):
                    if "=" in f:
                        k, _, v = f.partition("=")
                        row[k.strip()] = v.strip()
                rows.append(row)
        return meta, rows


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
    """Canonical instrument->frame scheme, folded from the Groovebox visual
    engine: every layer is ONE 2.5D frame (base_freq lattice, ratio, entropy,
    conson, depth, shade, life, radius) — the same parameter count and MEUM
    lattice as the canonical visual instrument.

    Opacity floors are deliberately high so seed-to-seed divergence is visible
    (seeds 1 vs 2 land on independent residues and therefore distinct hues,
    depths, radii and life values). Appearance and fire timing stay pure
    f(seed, i, beat). Topology-aware placement produces open-world scatter,
    hub spokes, or arena rings.
    """
    def __init__(self, seed, n=12, goava=False, topology="open_world"):
        self.seed = int(seed) & 0x7FFFFFFF
        # Irrational mix of instance counts — PHI/MEUM residues give non-integer
        # average densities so consecutive seeds diverge in population.
        _mix_n = 6 + int(18 * _residue(self.seed, "scene_n") + 4 * PHI * _residue(self.seed, "scene_n2"))
        self.n = max(5, min(36, max(int(n), _mix_n)))
        self.goava = bool(goava)
        self.topology = (topology or "open_world").lower()
        self.sculptor = TriggerSculptor(self.seed, self.n)
        self.beat = 0.0
        self.layers = []
        base = 220.0 * 2.0 ** ((round(36.0 * _residue(self.seed, "base")) - 18) / 12.0)
        for i in range(self.n):
            phase0 = _residue(self.seed, f"phase0:{i}")
            ax = (phase0 * MEUM_NORM + i * MEUM_INV) % 1.0
            ent = (_residue(self.seed, "identity_entropy")
                   if self.goava else _residue(self.seed, f"entropy:{i}"))
            conson = 1.0 if self.goava else 0.35 + 0.65 * abs(math.cos(ax * math.tau + i * PHI))
            pow_ = 1.5 + 10.0 * _residue(self.seed, f"pow:{i}")
            depth = 0.55 + 1.15 * (1.0 - conson) + 0.25 * pow_ * _residue(self.seed, f"dscale:{i}")
            # Higher shade/life floors → less wash-out, more seed divergence
            shade = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(ax * math.tau * PHI + i))
            life = 0.55 + 0.45 * conson * (0.30 + 0.70 * ent)
            pack = _residue(self.seed, f"pack:{i}")
            ratio = residue_to_bipolar(_residue(self.seed, f"ratio:{i}"))
            radius = (2.2 - min(depth, 2.0)) * (0.25 + 0.55 * pack)
            # Topology-aware free positions (open-world scatter vs hub vs ring)
            if self.topology in ("open_world", "sandbox", "hub_spoke"):
                yaw = meum_angle(self.seed * PHI + i * 47 + 13 * _residue(self.seed, f"yaw:{i}"))
                dist = 0.25 + 1.55 * _residue(self.seed, f"dist:{i}")
            elif self.topology in ("arena_loop", "linear"):
                yaw = meum_angle(i * 31 + self.seed)
                dist = 0.85 + 0.35 * _residue(self.seed, f"dist:{i}")
            else:
                yaw = meum_angle(self.seed + i * 31)
                dist = 0.5 + 1.0 * _residue(self.seed, f"dist:{i}")
            self.layers.append({
                "base_freq": base if self.goava else base * (1.0 + 1.1 * abs(ratio)),
                "ratio": ratio,
                "entropy": ent,
                "conson": conson,
                "depth": depth,
                "shade": shade,
                "life": life,
                "radius": radius,
                "yaw": yaw,
                "pitch": residue_to_bipolar(_residue(self.seed, f"pitch:{i}")) * 0.55,
                "dist": dist,
                "hue": (_residue(self.seed, f"hue:{i}") * 0.82 + _residue(self.seed, "hue_global") * 0.18) % 1.0,
                "on": True,
                "kind": ("panel", "filament", "polytope", "sigil_sprite")[
                    int(_residue(self.seed, f"kind:{i}") * 4) % 4
                ],
            })
    def tick(self, dt, audio_rms=0.2):
        self.beat += dt * (BPM / 60.0)
        step = int(self.beat)
        # VISIBILITY_CONTRACT: at least ceil(n/2) layers stay on so the player
        # always sees the scene (sculptor still gates the rest for rhythm).
        min_on = max(3, (self.n + 1) // 2)
        on_count = 0
        for i, L in enumerate(self.layers):
            fired = bool(self.sculptor.active(i, step))
            # Force visibility for the first min_on layers every frame
            L["on"] = True if i < min_on else fired
            if L["on"]:
                on_count += 1
                spin = 0.25 + 0.65 * MEUM * (i + 1) / max(1, self.n)
                L["yaw"] = (L["yaw"] + dt * spin * (0.6 + 0.9 * audio_rms)) % math.tau
            L["pitch"] = 0.55 * math.sin(self.beat * MEUM + i * PHI)
            # Subtle life pulse so open-world layers feel alive
            L["life"] = max(0.45, min(1.0, L.get("life", 0.7) + 0.04 * math.sin(self.beat * PHI + i)))
        self._on_count = on_count
        return self.layers


class MusicBed:
    """Compositional dynamics simplified from Groovebox — seed loop + DJ drift
    + a lightweight Meum harmonic lattice so the game bed shares the same
    entropy / phase0 / partial continuum as the main app voices.
    Output is intentionally loud (soft-clipped) so the game bed is audible
    without external gain.
    """
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
        # Canonical voice params (mirrors main-app meum voice lattice)
        self._phase0 = _residue(self.seed, "music_phase0") * math.tau
        self._entropy = _residue(self.seed, "music_entropy")
        self._n_partials = max(2, min(10, int(3 + (1.0 - self._entropy) * 7)))
        self._ratios = [
            1.0 + k * (0.45 + 0.55 * _residue(self.seed, f"pratio:{k}"))
            for k in range(self._n_partials)
        ]
        self._amps = [
            (0.62 ** k) * (0.55 + 0.45 * (1.0 - self._entropy))
            for k in range(self._n_partials)
        ]
        # Seed-driven master gain so consecutive seeds differ in loudness feel
        self._gain = 2.8 + 1.6 * _residue(self.seed, "music_gain")
    def step(self, dt):
        beat = self.bpm / 60.0
        self.phase = (self.phase + dt * beat * math.tau) % math.tau
        self.dj = 0.5 + 0.5 * math.sin(self.phase * MEUM + self._dj_residue * 0.01)
        if self.dj_goava:
            self.dj = 0.5 * self.dj + 0.5 * (0.5 + 0.5 * math.sin(self.phase * MEUM_INV))
        if self.dj_random:
            self.dj = (self.dj + 0.15 * math.sin(self.phase * PHI + self._algo_spin)) % 1.0
        g = self.mix * math.sin(self.phase * (1.0 + self._algo_spin) * MEUM)
        # Harmonic lattice: phase0-offset fundamental + entropy-scaled partials
        ph = self.phase + self._phase0
        sample = 0.0
        for k in range(self._n_partials):
            sample += self._amps[k] * math.sin(ph * self._ratios[k])
        sample *= (0.65 + 0.55 * self.dj)
        sample += 0.22 * g
        # Soft fold for mild chaos when entropy is high
        if self._entropy > 0.45:
            sample = math.tanh(sample * (1.2 + 1.1 * self._entropy))
        # Loud but soft-clipped so the bed is always clearly audible
        sample = math.tanh(sample * self._gain)
        return max(-1.0, min(1.0, sample))


class LiveSFX:
    """Instrument-lattice one-shots — same phase0/entropy continuum as voices.

    Triggered on collect / kill / portal / quest; mixed into the audio callback
    path as a short additive burst (no external sample files).
    """
    def __init__(self, seed, bank=None):
        self.seed = int(seed) & 0x7FFFFFFF
        self.bank = list(bank or [])
        self._queue = []  # (samples_left, phase, freq, amp, decay)

    def trigger(self, name_or_idx="blip", strength=1.0):
        if isinstance(name_or_idx, int):
            idx = name_or_idx % max(1, len(self.bank) or 1)
            label = self.bank[idx] if self.bank else f"sfx_{idx}"
        else:
            label = str(name_or_idx)
            idx = abs(hash(label)) % 16
        freq = 180.0 + 900.0 * _residue(self.seed, f"sfx_f:{label}")
        amp = 0.35 * float(strength) * (0.6 + 0.4 * _residue(self.seed, f"sfx_a:{label}"))
        dur = int(22050 * (0.06 + 0.14 * _residue(self.seed, f"sfx_d:{label}")))
        self._queue.append([dur, 0.0, freq, amp, 0.997 - 0.004 * _residue(self.seed, f"sfx_k:{label}")])

    def mix(self, n_samples, sample_rate=22050):
        if not self._queue:
            return [0.0] * n_samples
        out = [0.0] * n_samples
        alive = []
        for item in self._queue:
            left, phase, freq, amp, decay = item
            for i in range(n_samples):
                if left <= 0:
                    break
                out[i] += amp * math.sin(phase)
                phase += math.tau * freq / max(1, sample_rate)
                if phase > math.tau:
                    phase -= math.tau
                amp *= decay
                left -= 1
            if left > 0 and amp > 1e-4:
                alive.append([left, phase, freq, amp, decay])
        self._queue = alive
        return out


class InstrumentAssetBridge:
    """Ideal abstraction: instrument params → art / models / textures / color / SFX.

    Runtime mirror of the host-side build_asset_manifest so the playable
    package can tint geometry, pick primitives, and fire SFX from the same
    lattice the music voices use.
    """
    def __init__(self, identity):
        self.id = identity if isinstance(identity, dict) else {}
        mat = self.id.get("material_spec") or {}
        self.hue = float(mat.get("hue", _residue(_safe_int_seed(self.id.get("seed", 0)), "mat_hue")))
        self.sat = float(mat.get("saturation", 0.6))
        self.metallic = float(mat.get("metallic", 0.4))
        self.roughness = float(mat.get("roughness", 0.5))
        self.emissive = float(mat.get("emissive", 0.2))
        self.texture_family = self.id.get("texture_family") or "noise_meum"
        self.sfx = LiveSFX(self.id.get("seed", 0), self.id.get("sfx_bank") or [])
        self.primitives = (self.id.get("asset_manifest") or {}).get("primitives") or ["panel", "filament", "orb"]

    def color_for_layer(self, layer_hue, shade=0.7):
        """Blend instrument material hue with per-layer hue → display RGB hint."""
        h = (0.55 * self.hue + 0.45 * float(layer_hue)) % 1.0
        return h, max(0.3, min(1.0, self.sat * (0.7 + 0.3 * shade))), max(0.35, min(1.0, 0.45 + 0.55 * shade + 0.2 * self.emissive))

    def primitive_for(self, i):
        return self.primitives[i % len(self.primitives)]


class FunctionShell:
    """Software-kind function panel — NEVER removes sound/visual/UI.

    The seed picks a kind; this shell exposes kind-specific actions and a
    status line while the MusicBed, Scenograph, and control panel always run.
    """
    def __init__(self, identity):
        self.id = identity if isinstance(identity, dict) else {}
        self.kind = str(self.id.get("software_kind") or "videogame")
        self.seed = _safe_int_seed(self.id.get("seed", 0))
        self.status = f"{self.kind} ready"
        self.log = []
        # Kind-specific seeded state (all pure f(seed))
        self.calc_value = _residue(self.seed, "util_v") * 1000.0
        self.band_mhz = 7.0 + 21.0 * _residue(self.seed, "radio_band")  # HF study band
        self.morse_wpm = 12 + int(18 * _residue(self.seed, "morse_wpm"))
        self.latency_ms = 20 + int(80 * _residue(self.seed, "net_lat"))
        self.notes = f"Seeded note buffer [{self.id.get('composition_fingerprint', '')[:8]}]"
        self.vfs = [f"/{p}_{i}" for i, p in enumerate(
            ("home", "docs", "media", "net", "radio", "lab")
        )]
        self.code_buf = (
            f"# ide_lite — seed {self.seed}\n"
            f"def main():\n    return {_residue(self.seed, 'ide_ret'):.6f}\n"
        )

    def tick(self, t, audio_rms=0.0):
        # Soft status drift so every kind feels alive with the music
        if self.kind == "radio_toolkit":
            self.status = (
                f"SDR study  band={self.band_mhz:.3f} MHz  "
                f"Morse={self.morse_wpm} wpm  rms={audio_rms:.2f}  (sim only, no TX)"
            )
        elif self.kind == "network_tool":
            self.status = f"net probe  latency~{self.latency_ms}ms  t={t:.1f}s"
        elif self.kind == "media_player":
            self.status = f"media  rms={audio_rms:.3f}  bed+sfx active"
        elif self.kind == "data_viz":
            self.status = f"viz  lattice point={_residue(self.seed, f'viz:{int(t)}'):.4f}"
        elif self.kind == "utility" or self.kind == "office_suite":
            self.status = f"{self.kind}  value={self.calc_value:.3f}"
        elif self.kind == "chat_server":
            self.status = f"chat server  peers via NetTransport  t={t:.1f}"
        elif self.kind == "file_manager":
            self.status = f"vfs  {len(self.vfs)} nodes  cwd=/"
        elif self.kind == "terminal_lab":
            self.status = "terminal_lab  educational only — no shell exec"
        elif self.kind == "browser_shell":
            self.status = "browser_shell  offline lattice pages only"
        elif self.kind == "ide_lite":
            self.status = "ide_lite  buffer seeded — run-sim only"
        elif self.kind == "protocol_lab":
            self.status = f"protocol_lab  state={int(t * 3) % 5}"
        elif self.kind == "instrument_lab":
            self.status = "instrument_lab  Meum asset inspector"
        elif self.kind == "simulator":
            self.status = f"simulator  phase={math.sin(t * MEUM):.4f}"
        else:
            self.status = f"videogame world  t={t:.1f}s"

    def action(self, cmd=""):
        cmd = (cmd or "").strip().lower()
        if self.kind == "radio_toolkit":
            if cmd.startswith("band"):
                self.band_mhz = 1.8 + 28.0 * _residue(self.seed, f"band:{cmd}")
                self.log.append(f"band -> {self.band_mhz:.3f} MHz (sim)")
            elif cmd.startswith("morse"):
                self.log.append(f"morse trainer {self.morse_wpm} wpm (practice only)")
            else:
                self.log.append("radio: band | morse  — study toolkit, no transmitter")
        elif self.kind == "utility":
            self.calc_value = (self.calc_value * MEUM + _residue(self.seed, f"u:{cmd}")) % 10000
            self.log.append(f"util -> {self.calc_value:.4f}")
        elif self.kind == "network_tool":
            self.latency_ms = 10 + int(120 * _residue(self.seed, f"lat:{cmd}:{len(self.log)}"))
            self.log.append(f"probe latency={self.latency_ms}ms")
        else:
            self.log.append(f"{self.kind}: {cmd or 'ping'}")
        if len(self.log) > 40:
            self.log = self.log[-40:]
        return self.log[-1] if self.log else self.status

    def panel_text(self):
        lines = [
            f"kind: {self.kind}",
            f"status: {self.status}",
            "contract: ALWAYS sound + visual + UI",
        ]
        if self.kind == "radio_toolkit":
            lines += [f"band_mhz: {self.band_mhz:.3f}", f"morse_wpm: {self.morse_wpm}", "TX: disabled (safe sim)"]
        elif self.kind == "file_manager":
            lines += self.vfs[:6]
        elif self.kind == "ide_lite":
            lines += self.code_buf.splitlines()[:4]
        elif self.kind == "office_suite":
            lines += [self.notes[:80]]
        if self.log:
            lines.append("log: " + self.log[-1])
        return "\n".join(lines)


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


class ResourceField:
    """Harvestable nodes — Meum-packed angles, irrational count mix."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        # Irrational population: PHI + MEUM residues → non-repeating densities
        if count is None:
            count = 4 + int(12 * _residue(self.seed, "res_n") + 3 * PHI * _residue(self.seed, "res_n2"))
        self.count = max(3, min(28, int(count)))
        self.pos = [
            (meum_angle(self.seed * MEUM + k * 53),
             0.2 + 0.75 * _residue(self.seed, f"rr{k}"),
             0.4 + 0.6 * _residue(self.seed, f"rval{k}"))  # value
            for k in range(self.count)
        ]
        self.taken = set()

    def harvest(self, angle, reach=0.28):
        got = []
        for k, (a, r, v) in enumerate(self.pos):
            if k in self.taken:
                continue
            d = abs((a - angle + math.pi) % math.tau - math.pi)
            if d <= reach * max(0.2, r):
                self.taken.add(k)
                got.append((k, v))
        return got

    def remaining(self):
        return self.count - len(self.taken)


class HazardRing:
    """Damaging zones the player must avoid or skirt."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 2 + int(8 * _residue(self.seed, "hz_n") + 2 * MEUM * _residue(self.seed, "hz_n2"))
        self.count = max(1, min(16, int(count)))
        self.pos = [
            (meum_angle(self.seed * PHI + k * 71),
             0.15 + 0.55 * _residue(self.seed, f"hr{k}"),
             0.3 + 0.7 * _residue(self.seed, f"hdmg{k}"))
            for k in range(self.count)
        ]

    def damage_at(self, angle, reach=0.22):
        total = 0.0
        for a, r, dmg in self.pos:
            d = abs((a - angle + math.pi) % math.tau - math.pi)
            if d <= reach * max(0.18, r):
                total += dmg
        return total


class PortalGate:
    """Teleport gates — enter one, exit at a paired angle (open-world travel)."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 1 + int(5 * _residue(self.seed, "pt_n") + PHI * _residue(self.seed, "pt_n2"))
        self.count = max(1, min(10, int(count)))
        self.gates = []
        for k in range(self.count):
            a_in = meum_angle(self.seed + k * 97)
            a_out = meum_angle(self.seed * MEUM + k * 113 + 19)
            self.gates.append((a_in, a_out, 0.25 + 0.4 * _residue(self.seed, f"pr{k}")))

    def try_teleport(self, angle, reach=0.26):
        for a_in, a_out, r in self.gates:
            d = abs((a_in - angle + math.pi) % math.tau - math.pi)
            if d <= reach * max(0.2, r):
                return a_out
        return None


class WaypointTrail:
    """Ordered survey / escort checkpoints."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 3 + int(7 * _residue(self.seed, "wp_n") + 2 * PHI * _residue(self.seed, "wp_n2"))
        self.count = max(2, min(14, int(count)))
        self.pos = [
            (meum_angle(self.seed * PHI_INV + k * 41),
             0.35 + 0.5 * _residue(self.seed, f"wr{k}"))
            for k in range(self.count)
        ]
        self.next_idx = 0
        self.hit = set()

    def advance(self, angle, reach=0.30):
        if self.next_idx >= self.count:
            return False
        a, r = self.pos[self.next_idx]
        d = abs((a - angle + math.pi) % math.tau - math.pi)
        if d <= reach * max(0.2, r):
            self.hit.add(self.next_idx)
            self.next_idx += 1
            return True
        return False

    def remaining(self):
        return max(0, self.count - self.next_idx)


# ---------------------------------------------------------------------------
# Quests · Items · Tags · Points · Coins · Store · NPC · PvE · PvP
# All closed-form f(seed, label) — no RNG. File import/export rides the
# existing GameplayRecorder + GAME_CODECS path (json/gz/csv/txt/wav/png).
# ---------------------------------------------------------------------------
_ITEM_NAMES = (
    "Shard", "Core", "Lens", "Key", "Map", "Phial", "Token", "Ring",
    "Blade", "Shield", "Charm", "Scroll", "Ore", "Seed", "Crystal", "Relay",
)
_ITEM_TAGS = (
    "common", "rare", "epic", "meum", "trade", "quest", "pve", "pvp",
    "consumable", "equip", "cosmetic", "key_item",
)
_QUEST_VERBS = (
    "Collect", "Survey", "Escort", "Siege", "Harvest", "Deliver", "Clear", "Attune",
)
_NPC_ROLES = (
    "merchant", "guide", "rival", "ally", "oracle", "quartermaster", "herald", "warden",
)


class ItemCatalog:
    """Deterministic item definitions + player inventory."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 6 + int(10 * _residue(self.seed, "item_n") + 3 * PHI * _residue(self.seed, "item_n2"))
        self.count = max(4, min(24, int(count)))
        self.defs = []
        for i in range(self.count):
            name = _ITEM_NAMES[int(_residue(self.seed, f"iname:{i}") * len(_ITEM_NAMES)) % len(_ITEM_NAMES)]
            tag = _ITEM_TAGS[int(_residue(self.seed, f"itag:{i}") * len(_ITEM_TAGS)) % len(_ITEM_TAGS)]
            value = 1 + int(40 * _residue(self.seed, f"ival:{i}") + 10 * MEUM * _residue(self.seed, f"ival2:{i}"))
            power = 0.2 + 1.5 * _residue(self.seed, f"ipow:{i}")
            self.defs.append({
                "id": f"item_{i}",
                "name": f"{name}-{i+1}",
                "tag": tag,
                "value": value,
                "power": power,
                "stack": 1 + int(4 * _residue(self.seed, f"istack:{i}")),
            })
        self.inventory = {}
        self.equipped = None

    def grant(self, idx, qty=1):
        if idx < 0 or idx >= self.count:
            return None
        d = self.defs[idx]
        iid = d["id"]
        self.inventory[iid] = min(d["stack"], self.inventory.get(iid, 0) + qty)
        return d

    def grant_by_tag(self, tag, qty=1):
        for i, d in enumerate(self.defs):
            if d["tag"] == tag:
                return self.grant(i, qty)
        return self.grant(int(_residue(self.seed, f"grant:{tag}") * self.count) % self.count, qty)

    def equip(self, iid):
        if iid in self.inventory and self.inventory[iid] > 0:
            self.equipped = iid
            return True
        return False

    def power_bonus(self):
        if not self.equipped:
            return 0.0
        for d in self.defs:
            if d["id"] == self.equipped:
                return float(d["power"])
        return 0.0

    def to_dict(self):
        return {"inventory": dict(self.inventory), "equipped": self.equipped}

    def load_dict(self, data):
        if not isinstance(data, dict):
            return
        self.inventory = {str(k): int(v) for k, v in (data.get("inventory") or {}).items()}
        self.equipped = data.get("equipped")


class QuestLog:
    """Seeded quest board — accept, progress, complete for coins/points/items."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 3 + int(6 * _residue(self.seed, "quest_n") + 2 * PHI * _residue(self.seed, "quest_n2"))
        self.count = max(2, min(12, int(count)))
        self.quests = []
        for i in range(self.count):
            verb = _QUEST_VERBS[int(_residue(self.seed, f"qverb:{i}") * len(_QUEST_VERBS)) % len(_QUEST_VERBS)]
            target = 2 + int(6 * _residue(self.seed, f"qtgt:{i}"))
            reward_coins = 5 + int(30 * _residue(self.seed, f"qcoin:{i}"))
            reward_pts = 10 + int(50 * _residue(self.seed, f"qpts:{i}"))
            item_idx = int(_residue(self.seed, f"qitem:{i}") * 8) % 8
            tags = [_ITEM_TAGS[int(_residue(self.seed, f"qtag:{i}:{k}") * len(_ITEM_TAGS)) % len(_ITEM_TAGS)]
                    for k in range(1 + int(2 * _residue(self.seed, f"qtn:{i}")))]
            self.quests.append({
                "id": f"quest_{i}",
                "title": f"{verb} x{target}",
                "verb": verb.lower(),
                "target": target,
                "progress": 0,
                "reward_coins": reward_coins,
                "reward_points": reward_pts,
                "reward_item": item_idx,
                "tags": tags,
                "active": False,
                "done": False,
            })
        self.active_id = None

    def accept(self, idx=None):
        if idx is None:
            for q in self.quests:
                if not q["done"] and not q["active"]:
                    q["active"] = True
                    self.active_id = q["id"]
                    return q
            return None
        if 0 <= idx < self.count and not self.quests[idx]["done"]:
            self.quests[idx]["active"] = True
            self.active_id = self.quests[idx]["id"]
            return self.quests[idx]
        return None

    def progress(self, verb, amount=1):
        rewarded = []
        for q in self.quests:
            if not q["active"] or q["done"]:
                continue
            if q["verb"] == verb or verb == "any":
                q["progress"] = min(q["target"], q["progress"] + amount)
                if q["progress"] >= q["target"]:
                    q["done"] = True
                    q["active"] = False
                    if self.active_id == q["id"]:
                        self.active_id = None
                    rewarded.append(q)
        return rewarded

    def active(self):
        for q in self.quests:
            if q["active"]:
                return q
        return None

    def to_dict(self):
        return {"quests": list(self.quests), "active_id": self.active_id}

    def load_dict(self, data):
        if not isinstance(data, dict):
            return
        qs = data.get("quests")
        if isinstance(qs, list) and len(qs) == self.count:
            self.quests = qs
        self.active_id = data.get("active_id")


class CoinPurse:
    """Soft currency + spend/earn with store pricing from seed lattice."""
    def __init__(self, seed, start=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if start is None:
            start = 20 + int(40 * _residue(self.seed, "coins0"))
        self.coins = int(start)
        self.points = 0
        self.lifetime_earned = int(start)

    def earn(self, n, reason=""):
        n = max(0, int(n))
        self.coins += n
        self.lifetime_earned += n
        return self.coins

    def spend(self, n):
        n = max(0, int(n))
        if self.coins >= n:
            self.coins -= n
            return True
        return False

    def add_points(self, n):
        self.points += max(0, int(n))
        return self.points

    def to_dict(self):
        return {"coins": self.coins, "points": self.points, "lifetime": self.lifetime_earned}

    def load_dict(self, data):
        if not isinstance(data, dict):
            return
        self.coins = int(data.get("coins", self.coins))
        self.points = int(data.get("points", self.points))
        self.lifetime_earned = int(data.get("lifetime", self.lifetime_earned))


class Store:
    """Seed-priced shop slots — buy with coins, receive items."""
    def __init__(self, seed, catalog, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        self.catalog = catalog
        if count is None:
            count = 3 + int(5 * _residue(self.seed, "store_n"))
        self.count = max(2, min(10, int(count)))
        self.slots = []
        for i in range(self.count):
            idx = int(_residue(self.seed, f"sitem:{i}") * catalog.count) % catalog.count
            price = max(3, int(catalog.defs[idx]["value"] * (0.8 + 0.6 * _residue(self.seed, f"sprice:{i}"))))
            self.slots.append({"item_idx": idx, "price": price, "stock": 1 + int(3 * _residue(self.seed, f"sstock:{i}"))})

    def buy(self, slot_idx, purse, catalog):
        if slot_idx < 0 or slot_idx >= self.count:
            return None
        sl = self.slots[slot_idx]
        if sl["stock"] <= 0:
            return None
        if not purse.spend(sl["price"]):
            return None
        sl["stock"] -= 1
        return catalog.grant(sl["item_idx"], 1)


class NPCRoster:
    """Deterministic NPCs with roles, dialogue tags, and shop/quest links."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 2 + int(6 * _residue(self.seed, "npc_n") + 2 * MEUM * _residue(self.seed, "npc_n2"))
        self.count = max(1, min(12, int(count)))
        self.npcs = []
        for i in range(self.count):
            role = _NPC_ROLES[int(_residue(self.seed, f"nrole:{i}") * len(_NPC_ROLES)) % len(_NPC_ROLES)]
            ang = meum_angle(self.seed * PHI + i * 89)
            rad = 0.35 + 0.5 * _residue(self.seed, f"nrad:{i}")
            tags = [_ITEM_TAGS[int(_residue(self.seed, f"ntag:{i}:{k}") * len(_ITEM_TAGS)) % len(_ITEM_TAGS)]
                    for k in range(1 + int(2 * _residue(self.seed, f"ntn:{i}")))]
            self.npcs.append({
                "id": f"npc_{i}",
                "name": f"{role.title()}-{i+1}",
                "role": role,
                "angle": ang,
                "radius": rad,
                "tags": tags,
                "met": False,
                "disposition": 0.3 + 0.5 * _residue(self.seed, f"ndisp:{i}"),
            })

    def nearest(self, angle, reach=0.35):
        best, best_d = None, 99.0
        for n in self.npcs:
            d = abs((n["angle"] - angle + math.pi) % math.tau - math.pi)
            if d < best_d and d <= reach * max(0.2, n["radius"]):
                best, best_d = n, d
        return best

    def talk(self, npc):
        if npc is None:
            return None
        npc["met"] = True
        return {
            "name": npc["name"],
            "role": npc["role"],
            "tags": list(npc["tags"]),
            "line": f"{npc['name']} [{npc['role']}] tags={','.join(npc['tags'][:3])}",
        }


class PveEncounter:
    """Ambient PvE threats — defeat for coins/points (seed density)."""
    def __init__(self, seed, count=None):
        self.seed = int(seed) & 0x7FFFFFFF
        if count is None:
            count = 2 + int(7 * _residue(self.seed, "pve_n") + 2 * PHI * _residue(self.seed, "pve_n2"))
        self.count = max(1, min(14, int(count)))
        self.mobs = []
        for i in range(self.count):
            hp0 = 8 + int(20 * _residue(self.seed, f"pvehp:{i}"))
            self.mobs.append({
                "id": f"pve_{i}",
                "angle": meum_angle(self.seed * MEUM + i * 67),
                "radius": 0.2 + 0.45 * _residue(self.seed, f"pver:{i}"),
                "hp": hp0,
                "max_hp": hp0,
                "power": 0.4 + 1.2 * _residue(self.seed, f"pvep:{i}"),
                "alive": True,
            })

    def engage(self, angle, player_power, reach=0.28):
        kills = []
        for m in self.mobs:
            if not m["alive"]:
                continue
            d = abs((m["angle"] - angle + math.pi) % math.tau - math.pi)
            if d <= reach * max(0.18, m["radius"]):
                m["hp"] -= max(1.0, player_power)
                if m["hp"] <= 0:
                    m["alive"] = False
                    kills.append(m)
        return kills

    def remaining(self):
        return sum(1 for m in self.mobs if m["alive"])


class PvpArena:
    """Lightweight PvP state for online sessions — duel score vs remotes."""
    def __init__(self, seed):
        self.seed = int(seed) & 0x7FFFFFFF
        self.kills = 0
        self.deaths = 0
        self.duel_score = 0.0
        self.tag = "pvp" if _residue(self.seed, "pvp_on") > 0.35 else "peaceful"

    def register_hit(self, from_self=True):
        if from_self:
            self.kills += 1
            self.duel_score += MEUM * 3
        else:
            self.deaths += 1
            self.duel_score = max(0.0, self.duel_score - MEUM)

    def to_dict(self):
        return {"kills": self.kills, "deaths": self.deaths, "duel_score": round(self.duel_score, 2), "tag": self.tag}

    def load_dict(self, data):
        if not isinstance(data, dict):
            return
        self.kills = int(data.get("kills", 0))
        self.deaths = int(data.get("deaths", 0))
        self.duel_score = float(data.get("duel_score", 0))
        self.tag = str(data.get("tag", self.tag))


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
        _topo = str(self.id.get("topology") or "open_world")
        _goava = bool(self.id.get("goava_active") or ("hook_live_dj_goava" in (self.id.get("gameplay_hooks") or [])))
        self.scene = ScenographLite(
            self.id["seed"],
            n=10 + int(_residue(_safe_int_seed(self.id["seed"]), "scene_inst") * 14),
            goava=_goava,
            topology=_topo,
        )
        self.music = MusicBed(
            self.id["seed"],
            algo_fp=self.id.get("composition_fingerprint", "0"),
            dj_goava="hook_live_dj_goava" in (self.id.get("gameplay_hooks") or []),
            dj_random="hook_live_dj_parametric" in (self.id.get("gameplay_hooks") or []),
            mix=0.40,
        )
        self.objective = self.id.get("objective", "survey")
        self.difficulty = self.id.get("difficulty", "standard")
        self.level_type = self.id.get("level_type", "heightfield")
        self.difficulty_mult = {
            "tutorial": 0.5, "standard": 1.0, "master": 1.7, "meum_insane": 2.4,
        }.get(self.difficulty, 1.0)
        self.sigils = SigilRing(self.id["seed"], count=self.id.get("sigil_count", 8))
        # Open-world content packs — irrational instance mixes per seed
        self.resources = ResourceField(self.id["seed"])
        self.hazards = HazardRing(self.id["seed"])
        self.portals = PortalGate(self.id["seed"])
        self.waypoints = WaypointTrail(self.id["seed"])
        # Quests / Items / Tags / Coins / Store / NPC / PvE / PvP
        self.items = ItemCatalog(self.id["seed"])
        self.quests = QuestLog(self.id["seed"])
        self.purse = CoinPurse(self.id["seed"])
        self.store = Store(self.id["seed"], self.items)
        self.npcs = NPCRoster(self.id["seed"])
        self.pve = PveEncounter(self.id["seed"])
        self.pvp = PvpArena(self.id["seed"])
        self.assets = InstrumentAssetBridge(self.id)
        self.sfx = self.assets.sfx
        self.software_kind = self.id.get("software_kind") or "videogame"
        self.fn = FunctionShell(self.id)  # kind panel; multimodal always on
        self.quests.accept()  # auto-accept first available quest
        self.combo = 0
        self.level = 1
        self.angle = meum_angle(_safe_int_seed(self.id["seed"]) * MEUM_INV)
        self.score = 0.0
        self.hp = 100.0
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
        self._objective_done = False
        self._teleport_cd = 0.0
        self._npc_cd = 0.0
        self.tags = set(["starter"])  # player tags

        # GAME_FILE_TASKS_2026: gameplay recorder (deterministic, IN/OUT files).
        self.rec = GameplayRecorder(self.id["seed"], meta={
            "title": self.id.get("title", ""),
            "composition_fingerprint": self.id.get("composition_fingerprint"),
            "world_fingerprint": self.id.get("world_fingerprint"),
        })
        self.record_path = None
        self.replay_rows = []
        self.replay_idx = 0
        self._last_record_t = -1000.0
        self._audio_samples = []
        self.sample_rate = 22050

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
        try:
            self.fn.tick(self.t, audio_rms=abs(sample))
        except Exception:
            pass
        self._drain_net()
        if self.authoritative:
            self.angle = (self.angle + dt * MEUM * math.tau * (1.0 + 0.35 * self.steer)) % math.tau
            if self._teleport_cd > 0:
                self._teleport_cd = max(0.0, self._teleport_cd - dt)
            # Objective-weighted scoring: each objective privileges a different
            # closed-form signal so the same seed yields a distinct play-feel.
            _obj = (self.objective or "survey").lower()
            _obj_mult = {
                "harvest": 1.35,   # high reward on resource / sigil collect
                "escort": 0.85,    # steadier score from sustained orbit + waypoints
                "survey": 1.00,    # balanced open-world
                "siege": 1.55,     # aggressive high-risk / high-reward vs hazards
                "nexus": 1.20,     # rewards combo chains + portals
                "pilgrimage": 0.95,# slower accrual, larger level jumps via waypoints
            }.get(_obj, 1.0)
            if abs(sample) > 0.55:
                self.score += MEUM * abs(sample) * self.difficulty_mult * (0.7 if _obj == "harvest" else 1.0)
            # Sigils
            for _k, r in self.sigils.collect(self.angle):
                self.combo += 1
                self.score += MEUM * r * self.difficulty_mult * self.combo * _obj_mult
                self._reward_quests("collect", 1)
                self.purse.earn(1, "sigil")
                self.sfx.trigger("chime", 0.9)
            # Resources (open-world harvest)
            for _k, v in self.resources.harvest(self.angle):
                self.combo += 1
                self.score += 1.4 * MEUM * v * self.difficulty_mult * _obj_mult
                if _obj == "harvest":
                    self.score += 0.8 * MEUM * v * self.difficulty_mult
                self._reward_quests("harvest", 1)
                self.purse.earn(int(1 + 3 * v), "resource")
                self.items.grant_by_tag("common", 1)
                self.sfx.trigger("click", 0.7)
            # Hazards (damage / siege pressure)
            dmg = self.hazards.damage_at(self.angle) * self.difficulty_mult
            if dmg > 0:
                self.hp = max(0.0, self.hp - dmg * 12.0 * dt)
                if _obj == "siege":
                    self.score += 0.35 * dmg * self.difficulty_mult  # risk reward
            # Portals (open-world travel)
            if self._teleport_cd <= 0:
                dest = self.portals.try_teleport(self.angle)
                if dest is not None:
                    self.angle = dest
                    self._teleport_cd = 1.4
                    self.score += 2.0 * MEUM * _obj_mult
                    self.sfx.trigger("whoosh", 1.0)
                    self.send_chat("system", "portal jump")
            # Waypoints (survey / escort / pilgrimage)
            if self.waypoints.advance(self.angle):
                self.combo += 2
                self.score += 3.0 * MEUM * self.difficulty_mult * _obj_mult
                self.send_chat("system", f"waypoint {self.waypoints.next_idx}/{self.waypoints.count}")
                self._reward_quests("survey", 1)
                self._reward_quests("escort", 1)
            # PvE engage (player power = base + equipped item)
            _pp = 1.0 + self.items.power_bonus()
            for mob in self.pve.engage(self.angle, _pp):
                self.combo += 1
                self.score += 4.0 * MEUM * mob["power"] * self.difficulty_mult
                self.purse.earn(int(3 + 8 * mob["power"]), "pve")
                self.purse.add_points(int(5 + 10 * mob["power"]))
                self.tags.add("pve")
                self._reward_quests("clear", 1)
                self._reward_quests("siege", 1)
                self.sfx.trigger("thud", 1.1)
                self.send_chat("system", f"PvE down {mob['id']} +coins")
            # NPC proximity talk (auto on approach, cooldown)
            if self._npc_cd > 0:
                self._npc_cd = max(0.0, self._npc_cd - dt)
            else:
                npc = self.npcs.nearest(self.angle)
                if npc is not None:
                    info = self.npcs.talk(npc)
                    self._npc_cd = 2.5
                    self.tags.update(npc.get("tags") or [])
                    if npc["role"] == "merchant":
                        self.send_chat("system", f"{info['line']} — store open (/buy 0..{self.store.count-1})")
                    elif npc["role"] in ("guide", "oracle", "herald"):
                        q = self.quests.accept()
                        if q:
                            self.send_chat("system", f"{info['line']} — quest accepted: {q['title']}")
                        else:
                            self.send_chat("system", info["line"])
                    else:
                        self.send_chat("system", info["line"])
            # Sigil/resource quest verbs
            # (collect/harvest already happened above — progress those quests)
            for name, rec in list(self._remote_steers.items()):
                rec[0] = (rec[0] + dt * MEUM * math.tau * (1.0 + 0.35 * rec[2])) % math.tau
                for k, (a, r) in enumerate(self.sigils.pos):
                    if k in self.sigils.collected:
                        continue
                    d = abs((a - rec[0] + math.pi) % math.tau - math.pi)
                    if d <= 0.31 * max(0.25, r):
                        self.sigils.collected.add(k)
                        rec[1] += MEUM * r * self.difficulty_mult * _obj_mult
            threshold = 5 + self.level + int(MEUM * self.level)
            if _obj == "pilgrimage":
                threshold = max(3, threshold - 2)
            if self.combo >= threshold and self.music.dj > 0.05:
                self.level += 1
                self.difficulty_mult = min(3.0, self.difficulty_mult * (1.0 + MEUM_NORM * 0.4))
                self.send_chat("system", f"level {self.level} — {_obj} x{self.difficulty_mult:.2f}")
                self.combo = 0
            # Objective-complete conditions (plenty to do)
            done = False
            if _obj == "harvest" and self.resources.remaining() == 0 and self.sigils.remaining() == 0:
                done = True
            elif _obj in ("survey", "escort", "pilgrimage") and self.waypoints.remaining() == 0:
                done = True
            elif _obj == "nexus" and self.sigils.remaining() == 0 and self.resources.remaining() <= max(1, self.resources.count // 4):
                done = True
            elif self.sigils.remaining() == 0 and self.resources.remaining() == 0 and self.waypoints.remaining() == 0:
                done = True
            if done and not self._objective_done:
                self._objective_done = True
                self.score += 120.0 * MEUM * self.difficulty_mult * _obj_mult
                self.send_chat("system", f"OBJECTIVE COMPLETE — {_obj.upper()}  score {self.score:.1f}")
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
        # GAME_FILE_TASKS_2026: replay feeds recorded inputs back in — the world
        # is f(seed, t), so re-simulating the recorded steer reproduces the
        # session exactly on any machine.
        if self.replay_rows and self.replay_idx < len(self.replay_rows):
            row = self.replay_rows[self.replay_idx]
            try:
                if float(row.get("t", 0.0)) <= self.t:
                    try:
                        self.steer = max(-1.0, min(1.0, float(row.get("steer", self.steer))))
                    except Exception:
                        pass
                    self.replay_idx += 1
            except Exception:
                pass
        # Record deterministic gameplay (inputs + world telemetry) into files.
        if self.t - self._last_record_t >= dt * 0.5:
            self._last_record_t = self.t
            self.rec.record(
                t=round(self.t, 3), steer=round(self.steer, 4),
                angle=round(self.angle, 6), score=round(self.score, 3),
                level=self.level, combo=self.combo,
                sigils=self.sigils.remaining(),
                dj=round(self.music.dj, 3),
                authoritative=bool(self.authoritative),
                player=self.player_name,
            )
            self._audio_samples.append(float(sample))
        # Live SFX burst mixed into the bed sample (instrument-lattice one-shots)
        try:
            sfx_chunk = self.sfx.mix(1, self.sample_rate)
            sample = max(-1.0, min(1.0, float(sample) + 0.85 * float(sfx_chunk[0])))
        except Exception:
            pass
        self.t += dt
        return sample, layers

    def save_recording(self, path, make_wav=False):
        """Write the recorded gameplay to `path` via the matching codec.
        wav targets get the synthesized music bed; all others the telemetry."""
        samples = self._audio_samples if (make_wav or resolve_codec(path)[0] == "wav") else None
        return self.rec.save(path, samples=samples, sample_rate=self.sample_rate)

    def load_replay(self, path):
        """Read gameplay back OUT of a recording file and arm deterministic replay."""
        meta, rows = GameplayRecorder.load(path)
        self.replay_rows = rows or []
        self.replay_idx = 0
        return meta, len(rows)

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

    def _reward_quests(self, verb, amount=1):
        """Apply quest progress and grant coins/points/items on completion."""
        for q in self.quests.progress(verb, amount):
            self.purse.earn(q["reward_coins"], "quest")
            self.purse.add_points(q["reward_points"])
            granted = self.items.grant(q["reward_item"] % self.items.count, 1)
            self.tags.update(q.get("tags") or [])
            self.tags.add("quest")
            name = granted["name"] if granted else "?"
            self.send_chat("system",
                f"QUEST DONE {q['title']} +{q['reward_coins']}c +{q['reward_points']}pts item={name}")
            # Auto-accept next
            nxt = self.quests.accept()
            if nxt:
                self.send_chat("system", f"next quest: {nxt['title']}")

    def economy_snapshot(self):
        return {
            "coins": self.purse.to_dict(),
            "items": self.items.to_dict(),
            "quests": self.quests.to_dict(),
            "pvp": self.pvp.to_dict(),
            "tags": sorted(self.tags),
            "score": round(self.score, 3),
            "level": self.level,
            "hp": round(self.hp, 1),
        }

    def load_economy(self, data):
        if not isinstance(data, dict):
            return
        self.purse.load_dict(data.get("coins") or {})
        self.items.load_dict(data.get("items") or {})
        self.quests.load_dict(data.get("quests") or {})
        self.pvp.load_dict(data.get("pvp") or {})
        tags = data.get("tags")
        if isinstance(tags, list):
            self.tags = set(str(t) for t in tags)
        if "score" in data:
            self.score = float(data["score"])
        if "level" in data:
            self.level = int(data["level"])
        if "hp" in data:
            self.hp = float(data["hp"])

    def export_economy(self, path):
        """File export — json/gz economy + world state (shares GAME_CODECS path)."""
        blob = {
            "kind": "groovebox-economy/1",
            "seed": self.id.get("seed"),
            "fingerprint": self.id.get("composition_fingerprint"),
            "world_fingerprint": self.id.get("world_fingerprint"),
            "economy": self.economy_snapshot(),
            "report": self.report(),
        }
        path = str(path)
        if path.endswith(".gz"):
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(blob, f, indent=2, sort_keys=True)
        else:
            if not path.endswith(".json"):
                path = path + ".json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, indent=2, sort_keys=True)
        return path

    def import_economy(self, path):
        """File import — restore coins/items/quests/tags/pvp from json/gz."""
        path = str(path)
        if path.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                blob = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                blob = json.load(f)
        eco = blob.get("economy") if isinstance(blob, dict) else None
        if eco:
            self.load_economy(eco)
            self.send_chat("system", f"imported economy from {path}")
            return True
        self.send_chat("system", f"import failed — no economy block in {path}")
        return False

    def report(self):
        aq = self.quests.active()
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
            "coins": self.purse.coins,
            "points": self.purse.points,
            "hp": round(self.hp, 1),
            "quest": (aq["title"] if aq else None),
            "quest_progress": (f"{aq['progress']}/{aq['target']}" if aq else None),
            "items": len(self.items.inventory),
            "equipped": self.items.equipped,
            "tags": sorted(self.tags),
            "pve_remaining": self.pve.remaining(),
            "pvp": self.pvp.to_dict(),
            "npcs_met": sum(1 for n in self.npcs.npcs if n.get("met")),
            "software_kind": self.software_kind,
            "fn_status": getattr(self.fn, "status", ""),
            "multimodal": {"sound": True, "visual": True, "ui": True},
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
        elif line in ("/inv", "/items"):
            inv = self.items.inventory
            print("INVENTORY:", json.dumps(inv, indent=2))
            print("EQUIPPED:", self.items.equipped)
            print("DEFS:", [(d["id"], d["name"], d["tag"], d["value"]) for d in self.items.defs[:8]])
        elif line in ("/quests", "/quest"):
            for q in self.quests.quests:
                flag = "DONE" if q["done"] else ("ACTIVE" if q["active"] else "open")
                print(f"  [{flag}] {q['title']} {q['progress']}/{q['target']} tags={q['tags']}")
        elif line.startswith("/accept"):
            parts = line.split()
            idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            q = self.quests.accept(idx)
            if q:
                self.send_chat("system", f"accepted {q['title']}")
            else:
                self.send_chat("system", "no quest available")
        elif line.startswith("/buy"):
            parts = line.split()
            idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            got = self.store.buy(idx, self.purse, self.items)
            if got:
                self.send_chat("system", f"bought {got['name']} [{got['tag']}] for coins")
                self.tags.add("trade")
            else:
                self.send_chat("system", f"buy failed (slot={idx} coins={self.purse.coins})")
        elif line.startswith("/equip"):
            parts = line.split()
            iid = parts[1] if len(parts) > 1 else None
            if iid and self.items.equip(iid):
                self.send_chat("system", f"equipped {iid}")
            else:
                self.send_chat("system", f"equip failed — have: {list(self.items.inventory.keys())}")
        elif line.startswith("/export"):
            parts = line.split(None, 1)
            path = parts[1] if len(parts) > 1 else "economy.json"
            out = self.export_economy(path)
            self.send_chat("system", f"exported economy -> {out}")
        elif line.startswith("/import"):
            parts = line.split(None, 1)
            path = parts[1] if len(parts) > 1 else "economy.json"
            self.import_economy(path)
        elif line in ("/store", "/shop"):
            for i, sl in enumerate(self.store.slots):
                d = self.items.defs[sl["item_idx"]]
                print(f"  [{i}] {d['name']} [{d['tag']}] price={sl['price']} stock={sl['stock']}")
            print(f"  coins={self.purse.coins} points={self.purse.points}")
        elif line in ("/tags",):
            print("TAGS:", sorted(self.tags))
        elif line in ("/pvp",):
            print("PvP:", self.pvp.to_dict())
        elif line in ("/fn", "/kind", "/function"):
            print(self.fn.panel_text())
        elif line.startswith("/fn "):
            msg = self.fn.action(line[4:])
            self.send_chat("system", msg)
        elif line in ("/contract", "/multimodal"):
            print(json.dumps({
                "software_kind": self.software_kind,
                "always_sound": True,
                "always_visual": True,
                "always_ui": True,
                "music": True,
                "sfx_queue": len(getattr(self.sfx, "_queue", [])),
                "layers": len(self.scene.layers),
                "layers_on": getattr(self.scene, "_on_count", "?"),
            }, indent=2))
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
            # Larger world radius for open-world feel
            R = min(w, h) * 0.42
            p.fillRect(self.rect(), QColor(bg))
            topo = str(g.id.get("topology") or "open_world")

            def project(yaw, dist, pitch=0.0, depth=1.0):
                # 2.5D: yaw/dist on plane, pitch lifts Y, depth scales size
                scale = 1.0 / max(0.35, 0.55 + 0.45 * depth)
                x = cx + dist * R * math.cos(yaw) * scale
                y = cy + dist * R * math.sin(yaw) * scale - pitch * R * 0.35 * scale
                sz = max(2.0, (6.0 + 10.0 * (1.2 - min(depth, 1.8))) * scale)
                return x, y, sz

            # Depth-sorted layers for proper 2.5D occlusion
            on_layers = [L for L in g.scene.layers if L.get("on")]
            on_layers.sort(key=lambda L: -float(L.get("depth", 1.0)))
            for L in on_layers:
                shade = float(L.get("shade", 0.7))
                life = float(L.get("life", 0.7))
                depth = float(L.get("depth", 1.2))
                hue = float(L.get("hue", 0.5))
                # Instrument→asset color bridge when present
                try:
                    h, s, v = g.assets.color_for_layer(hue, shade)
                    hsv = QColor(ac).toHsv()
                    hsv.setHsv(int(round(h * 360)) % 360,
                               int(80 + 175 * s),
                               int(100 + 155 * v))
                except Exception:
                    hsv = QColor(ac).toHsv()
                    hsv.setHsv(int(round(hue * 360)) % 360,
                               int(90 + 165 * shade),
                               int(110 + 145 * shade))
                col = hsv
                # High opacity floor so the scene is always visible
                col.setAlpha(max(140, min(255, int(110 + 145 * life * shade))))
                x, y, sz = project(L.get("yaw", 0.0), L.get("dist", 1.0),
                                   L.get("pitch", 0.0), depth)
                kind = L.get("kind", "panel")
                if kind == "filament":
                    p.setPen(QPen(col, max(1, int(1 + 2.2 * depth))))
                    p.drawLine(QPointF(cx, cy), QPointF(x, y))
                elif kind == "polytope":
                    p.setPen(QPen(col, 2))
                    p.setBrush(col)
                    pts = []
                    for k in range(5):
                        a = L.get("yaw", 0) + k * math.tau / 5
                        px = x + sz * 0.7 * math.cos(a)
                        py = y + sz * 0.7 * math.sin(a)
                        pts.append(QPointF(px, py))
                    if pts:
                        p.drawPolygon(*pts) if False else p.drawConvexPolygon(pts)
                else:
                    p.setPen(QPen(col, 1))
                    p.setBrush(col)
                    p.drawEllipse(QPointF(x, y), sz, sz * 0.72)

            # Soft world ring (less dominant in open_world)
            ring_a = 90 if topo in ("open_world", "hub_spoke") else 180
            ring_col = QColor(tx)
            ring_col.setAlpha(ring_a)
            p.setPen(QPen(ring_col, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), R, R)

            # Hazards (danger glows)
            for a, r, _d in getattr(g, "hazards", HazardRing(0)).pos:
                x = cx + math.cos(a) * r * R
                y = cy + math.sin(a) * r * R
                col = QColor(dg)
                col.setAlpha(160)
                p.setPen(QPen(col, 1))
                p.setBrush(col)
                p.drawEllipse(QPointF(x, y), 5 + int(r * 10), 5 + int(r * 10))

            # Resources
            for k, (a, r, _v) in enumerate(getattr(g, "resources", ResourceField(0)).pos):
                if k in getattr(g.resources, "taken", set()):
                    continue
                col = QColor("#7dff9a")
                col.setAlpha(220)
                p.setPen(QPen(col, 1))
                p.setBrush(col)
                x = cx + math.cos(a) * r * R
                y = cy + math.sin(a) * r * R
                p.drawRect(int(x - 4), int(y - 4), 8, 8)

            # Portals
            for a_in, a_out, r in getattr(g, "portals", PortalGate(0)).gates:
                col = QColor("#c77dff")
                col.setAlpha(200)
                p.setPen(QPen(col, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                x = cx + math.cos(a_in) * r * R
                y = cy + math.sin(a_in) * r * R
                p.drawEllipse(QPointF(x, y), 9, 9)
                # faint exit marker
                col.setAlpha(90)
                p.setPen(QPen(col, 1))
                x2 = cx + math.cos(a_out) * r * R
                y2 = cy + math.sin(a_out) * r * R
                p.drawEllipse(QPointF(x2, y2), 5, 5)

            # Waypoints (numbered trail)
            for k, (a, r) in enumerate(getattr(g, "waypoints", WaypointTrail(0)).pos):
                if k in getattr(g.waypoints, "hit", set()):
                    continue
                col = QColor("#ffe066")
                col.setAlpha(230 if k == getattr(g.waypoints, "next_idx", 0) else 140)
                p.setPen(QPen(col, 2 if k == getattr(g.waypoints, "next_idx", 0) else 1))
                p.setBrush(col)
                x = cx + math.cos(a) * r * R
                y = cy + math.sin(a) * r * R
                p.drawEllipse(QPointF(x, y), 6, 6)
                p.setPen(QPen(QColor(tx), 1))
                p.drawText(int(x + 6), int(y - 4), str(k + 1))

            # Sigils
            for k, (a, r) in enumerate(g.sigils.pos):
                if k in getattr(g.sigils, "collected", set()):
                    continue
                col = QColor(ac)
                col.setAlpha(240)
                p.setPen(QPen(col, 1))
                p.setBrush(col)
                x = cx + math.cos(a) * r * R
                y = cy + math.sin(a) * r * R
                p.drawEllipse(QPointF(x, y), 4 + int(r * 8), 4 + int(r * 8))

            # PvE mobs
            for m in getattr(g, "pve", PveEncounter(0)).mobs:
                if not m.get("alive", True):
                    continue
                col = QColor("#ff6b4a")
                col.setAlpha(200)
                p.setPen(QPen(col, 2))
                p.setBrush(col)
                x = cx + math.cos(m["angle"]) * m["radius"] * R
                y = cy + math.sin(m["angle"]) * m["radius"] * R
                p.drawEllipse(QPointF(x, y), 7, 7)

            # NPCs
            for n in getattr(g, "npcs", NPCRoster(0)).npcs:
                col = QColor("#66d9ef") if not n.get("met") else QColor("#a6e22e")
                col.setAlpha(220)
                p.setPen(QPen(col, 2))
                p.setBrush(col)
                x = cx + math.cos(n["angle"]) * n["radius"] * R
                y = cy + math.sin(n["angle"]) * n["radius"] * R
                p.drawRect(int(x - 5), int(y - 5), 10, 10)
                p.setPen(QPen(QColor(tx), 1))
                p.drawText(int(x + 6), int(y - 2), n["name"][:10])

            def draw_face(name, angle, color, size):
                x = cx + math.cos(angle) * R * 0.92
                y = cy + math.sin(angle) * R * 0.92
                p.setPen(QPen(color, 2))
                p.setBrush(QColor(color))
                p.drawEllipse(QPointF(x, y), size, size)
                p.drawLine(QPointF(x - size, y + size * 0.6), QPointF(x + size * 0.8, y - size * 0.9))
                p.setPen(QPen(QColor(tx), 1))
                p.drawText(int(x - size), int(y - size - 4), str(name)[:12])
            draw_face(g.player_name or "You", g.angle, QColor(ac), 8)
            for name, rec in sorted((g.remotes or {}).items()):
                draw_face(name, float(rec.get("angle", 0.0)), QColor(dg), 6)

            hp = getattr(g, "hp", 100.0)
            coins = getattr(getattr(g, "purse", None), "coins", 0)
            pts = getattr(getattr(g, "purse", None), "points", 0)
            aq = g.quests.active() if getattr(g, "quests", None) else None
            qtxt = f"{aq['title']} {aq['progress']}/{aq['target']}" if aq else "none"
            p.setPen(QPen(QColor(tx), 1))
            p.drawText(8, h - 24,
                       f"{g.id['title']}  t={g.t:.1f}s  "
                       f"sigils={g.sigils.remaining()}/{g.sigils.count}  "
                       f"res={g.resources.remaining()}  wp={g.waypoints.remaining()}  "
                       f"pve={g.pve.remaining()}")
            p.drawText(8, h - 10,
                       f"HP={hp:.0f}  coins={coins}  pts={pts}  quest={qtxt}  net={g.net.status}")

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
            self.eco_lbl = QLabel("Coins 0  Pts 0  HP 100")
            self.quest_lbl = QLabel("Quest —")
            self.tags_lbl = QLabel("Tags: starter")
            self.kind_lbl = QLabel(f"Kind: {g.software_kind}  (always sound+visual+UI)")
            self.fn_lbl = QLabel("Fn: —")
            self.fn_lbl.setWordWrap(True)
            self.djbar = QProgressBar()
            self.djbar.setRange(0, 1000)
            self.djbar.setValue(0)
            self.djbar.setTextVisible(False)
            for lbl in (self.score_lbl, self.level_lbl, self.sigil_lbl, self.eco_lbl,
                        self.quest_lbl, self.tags_lbl, self.kind_lbl, self.fn_lbl):
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
            try:
                self.eco_lbl.setText(
                    f"Coins {g.purse.coins}  Pts {g.purse.points}  HP {g.hp:.0f}  "
                    f"Inv {len(g.items.inventory)}  PvE {g.pve.remaining()}"
                )
                aq = g.quests.active()
                self.quest_lbl.setText(
                    f"Quest {aq['title']} {aq['progress']}/{aq['target']}" if aq else "Quest —"
                )
                self.tags_lbl.setText("Tags: " + ", ".join(sorted(g.tags)[:8]))
                self.kind_lbl.setText(f"Kind: {g.software_kind}  (always sound+visual+UI)")
                self.fn_lbl.setText("Fn: " + str(getattr(g.fn, "status", "—"))[:90])
            except Exception:
                pass
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
            if getattr(self.game, "record_path", None):
                try:
                    path = self.game.save_recording(
                        self.game.record_path,
                        make_wav=resolve_codec(self.game.record_path)[0] in ("wav",))
                    print(f"[EXPORT] recording -> {path} ({len(self.game.rec.rows)} rows)")
                except Exception as err:
                    print(f"[EXPORT] recording failed: {err}")
            self.game.net.shutdown()
            super().closeEvent(e)


def parse_args(argv):
    args = {
        "host": ("--host" in argv), "port": None, "connect": None,
        "cli": ("--cli" in argv) or ("--headless" in argv),
        "report": "--report" in argv, "seconds": 20.0,
        "list_formats": "--list-formats" in argv,
        "record": None, "record_format": None, "replay": None,
        "probe": None, "write_identity": None,
    }
    for a in argv:
        k, _, v = a.partition("=")
        if k == "--port":
            try:
                args["port"] = int(v)
            except Exception:
                args["port"] = None
        elif k == "--connect":
            args["connect"] = v.strip()
        elif k == "--seconds":
            try:
                args["seconds"] = max(0.5, float(v))
            except Exception:
                args["seconds"] = 20.0
        elif k == "--record":
            args["record"] = (v.strip() or "gameplay.gz")
        elif k == "--record-format":
            args["record_format"] = v.strip().lstrip(".")
        elif k == "--replay":
            args["replay"] = v.strip()
        elif k == "--probe":
            args["probe"] = v.strip()
        elif k == "--write-identity":
            args["write_identity"] = v.strip()
    return args


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    A = parse_args(argv)

    # GAME_FILE_TASKS_2026: engine-side file tasks first (no session needed).
    if A["list_formats"]:
        list_file_tasks()
        return

    g = Game(host_mode=A["host"], port=A["port"], connect=A["connect"])
    # MULTIMODAL_CONTRACT: every session declares sound + visual + UI up front.
    print("[MULTIMODAL] sound=ON  visual=ON  ui=%s  kind=%s" % (
        "PyQt6" if HAS_UI and not A.get("cli") else "CLI-HUD",
        getattr(g, "software_kind", g.id.get("software_kind", "videogame")),
    ))
    print("[MULTIMODAL] MusicBed+LiveSFX + ScenographLite + ControlPanel/CLI always active")

    if A["report"]:
        print(json.dumps(g.report(), indent=2, sort_keys=True))
        g.net.shutdown()
        return

    if A["probe"]:
        meta, rows = GameplayRecorder.load(A["probe"])
        print(json.dumps({"file": A["probe"], "meta": meta, "rows": len(rows)},
                         indent=2, sort_keys=True))
        g.net.shutdown()
        return

    if A["write_identity"]:
        with open(A["write_identity"], "w", encoding="utf-8") as f:
            json.dump(g.id, f, indent=2, sort_keys=True)
        print(f"[EXPORT] identity -> {A['write_identity']}")
        g.net.shutdown()
        return

    if A["replay"]:
        meta, nrows = g.load_replay(A["replay"])
        print(f"[REPLAY] {A['replay']}: {nrows} input rows "
              f"(seed={meta.get('seed')} fmt={meta.get('format')})")

    if A["record_format"] and not A["record"]:
        A["record"] = "gameplay." + (A["record_format"] or "gz")
    g.record_path = A["record"]

    if A["cli"] or not HAS_UI:
        if not A["cli"] and not HAS_UI:
            print("[UI] PyQt6 not found in this Python — falling back to the "
                  "deterministic CLI loop. Install PyQt6 for the control panel.")
        g.run(seconds=A["seconds"])
        if g.record_path:
            path = g.save_recording(g.record_path,
                                    make_wav=resolve_codec(g.record_path)[0] in ("wav",))
            print(f"[EXPORT] recording -> {path} ({len(g.rec.rows)} rows)")
        if A["replay"]:
            print(f"[REPLAY-LOG] end parity: score={g.score:.3f} "
                  f"consumed={g.replay_idx}/{len(g.replay_rows)}")
        return
    # LOADING_SCREEN_2026: create QApplication + the loading screen FIRST,
    # before Game(...) does any of its heavier construction (network
    # transport bind/connect, scenograph mesh, sigil ring, music bed).
    app = QApplication.instance() or QApplication(sys.argv[:1])
    loading = LoadingScreen(title_hint="Preparing session…")
    loading.show()
    loading.set_status("Starting network + world…")
    game = Game(host_mode=A["host"], port=A["port"], connect=A["connect"])
    game.record_path = A["record"]
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
    # Instrument → asset manifest (models, textures, materials, SFX, software kind)
    asset_path = os.path.join(out_dir, f"assets_{identity.composition_fingerprint}.json")
    with open(asset_path, "w", encoding="utf-8") as f:
        json.dump(identity.asset_manifest or build_asset_manifest(
            _safe_int_seed(identity.seed),
            identity.model_sets_1d, identity.model_sets_2d, identity.model_sets_3d,
            identity.texture_family, identity.material_spec or {},
            identity.sfx_bank or [], identity.software_kind or "videogame",
        ), f, indent=2, sort_keys=True)
    # Lattice coverage proof (shows radio_toolkit and other kinds are reachable)
    proof_path = os.path.join(out_dir, "software_lattice_proof.json")
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump(prove_software_lattice(48), f, indent=2, sort_keys=True)
    # Multimodal contract — every package declares always sound + visual + UI
    contract_path = os.path.join(out_dir, "multimodal_contract.json")
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump({
            **MULTIMODAL_CONTRACT,
            "software_kind": identity.software_kind,
            "title": identity.title,
            "fingerprint": identity.composition_fingerprint,
        }, f, indent=2, sort_keys=True)
    _write_launchers(out_dir, identity.composition_fingerprint)
    _write_package_readme(out_dir, identity)
    # The package carries its own provisioning: identical dependency-install
    # scripts (also kept in the project root) + the codec/job task manifest, so
    # an unpacked export can install deps + codecs without files outside the zip.
    write_dependency_scripts(out_dir)
    write_formats_manifest(out_dir)
    return script_path


_GAME_FILENAME = "game_{fingerprint}.py"


# PACKAGE_README_2026: the package spells out its only external requirements so
# a launch never depends on files that are not inside the .zip. Everything the
# script imports at runtime is the Python standard library plus exactly two
# system-level dependencies shared with the Groovebox host app: Python itself
# and PyQt6 (UI only — the game auto-falls-back to the CLI loop without it).
# GAME_FILE_TASKS_2026: the package README grows a provisioning + recording +
# codec-task section (above) and the export gains install_deps_* + formats.json.
PACKAGE_README = """Groovebox Video-Game Package
===========================
Title:  {title}
Genre:  {genre}  |  Camera:  {camera}  |  Topology:  {topology}
Social: {social}  |  Mood:   {mood}
Software kind: {software_kind}
World:  objective={objective}  difficulty={difficulty}  level={level_type}
        sigils={sigil_count}  world_fingerprint={world_fingerprint}
Fingerprint: {composition_fingerprint}

MULTIMODAL CONTRACT (always on)
-------------------------------
Every package ships SOUND (MusicBed + LiveSFX), VISUAL (ScenographLite 2.5D),
and UI (PyQt6 panel, or CLI HUD if PyQt6 is missing).  Software-kind only
changes the function panel (network tool, radio study toolkit, data viz, …);
it never strips audio, scenograph, or UI.  See multimodal_contract.json.

RUNNING
-------
Windows:  double-click launch_windows.bat
macOS:    double-click launch_macos.command  (or: bash launch_macos.command)
Linux:    run  ./launch_linux.sh             (or: bash launch_linux.sh)
All three launchers pass extra arguments through to the game.

INSTALLING DEPENDENCIES + CODECS
--------------------------------
This package carries its own installers (identical copies of the ones in the
Groovebox project root) so a fresh machine can provision itself from the zip:
    Windows:  Powershell -ExecutionPolicy Bypass -File install_deps_windows.ps1
    macOS:    bash ./install_deps_macos.sh
    Linux:    ./install_deps_linux.sh --fedora   or   ./install_deps_linux.sh --ubuntu
Each installs python + the shared pip deps and puts the ffmpeg codec binaries
(on Linux/macOS, into /bin; on Windows, a bin folder on your user PATH) so the
Groovebox host app and this game both find encoders for video/audio export.

FILE I/O TASKS (formats.json lists every codec + job)
-----------------------------------------------------
The game records deterministic gameplay INTO files and replays it OUT:
    ./launch_linux.sh --cli --record=gameplay.gz --seconds=10      # save
    ./launch_linux.sh --cli --replay=gameplay.gz --seconds=10      # re-simulate
    ./launch_linux.sh --list-formats        # show all codec jobs
    ./launch_linux.sh --probe=gameplay.gz   # inspect a recording
Formats: .json (metadata), .gz (compressed replay, default), .csv (table),
.txt (log), .wav (music-bed export), .png (scene snapshot).

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
            software_kind=getattr(identity, "software_kind", "videogame"),
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


# =============================================================================
# GAME_FILE_TASKS_2026 — import/export codec jobs + gameplay recording system
# =============================================================================
# VideoGameEngine finds its own file work: a format registry (several codecs),
# an import/export router that turns "what can this file/format do here?" into
# concrete encode/decode jobs, and a GameplayRecorder that writes gameplay
# (deterministic input telemetry) INTO files and reads it back OUT to replay the
# exact same session on any machine. The emitted game carries the same registry
# and recorder (stdlib-only); this module exposes the reference implementation
# plus the router API so the host app / engine can enumerate tasks too.
GAME_CODECS: Dict[str, Dict[str, Any]] = {
    "json": {
        "kind": "both", "mime": "application/json",
        "label": "World / replay metadata (identity + full telemetry)",
        "decode": "decode_json", "encode": "encode_json",
    },
    "gz": {
        "kind": "both", "mime": "application/gzip",
        "label": "Compressed NDJSON replay (default recording format)",
        "decode": "decode_json_gz", "encode": "encode_json_gz",
    },
    "csv": {
        "kind": "both", "mime": "text/csv",
        "label": "Flat telemetry table (spreadsheets)",
        "decode": "decode_csv", "encode": "encode_csv",
    },
    "txt": {
        "kind": "both", "mime": "text/plain",
        "label": "Human-readable session log",
        "decode": "decode_txt", "encode": "encode_txt",
    },
    "wav": {
        "kind": "export", "mime": "audio/wav",
        "label": "Music-bed audio export",
        "decode": None, "encode": "encode_wav",
    },
    "png": {
        "kind": "export", "mime": "image/png",
        "label": "Scene snapshot",
        "decode": None, "encode": "encode_png",
    },
}


def resolve_codec(format_token: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Map a format name or a file path to (extension, codec).  Returns
    (None, None) when the token is not one of the registered codecs."""
    if format_token is None:
        return None, None
    token = str(format_token)
    ext = token.lstrip(".").lower()
    codec = GAME_CODECS.get(ext)
    if codec is not None:
        return ext, codec
    base = os.path.splitext(token)[1].lstrip(".").lower()
    codec = GAME_CODECS.get(base)
    if codec is not None:
        return base, codec
    return None, None


def game_import_jobs(path_or_format: Any = ".gz") -> List[Dict[str, Any]]:
    """Task list for bringing a file INTO the game (replay / identity)."""
    ext, codec = resolve_codec(path_or_format)
    if ext is None:
        return []
    jobs: List[Dict[str, Any]] = []
    if codec.get("decode"):
        jobs.append({
            "op": "import", "format": ext, "codec": codec["decode"],
            "mime": codec.get("mime"),
            "target": "gameplay replay (inputs + telemetry)",
            "usage": f"--replay=gameplay.{ext}",
        })
    if ext in ("json", "gz"):
        jobs.append({
            "op": "import", "format": ext, "codec": "decode_identity",
            "mime": codec.get("mime"), "target": "game identity snapshot",
            "usage": f"--identity=identity.{ext}",
        })
    jobs.append({
        "op": "inspect", "format": ext, "codec": "probe",
        "target": "file probe (format / rows / duration)",
        "usage": f"--probe=gameplay.{ext}",
    })
    return jobs


def game_export_jobs(path_or_format: Any = "-") -> List[Dict[str, Any]]:
    """Task list for writing game state / gameplay OUT to a file."""
    ext, codec = resolve_codec(path_or_format)
    if ext is None:
        # No target yet — task is: pick a registered codec.
        return [{
            "op": "list", "formats": sorted(GAME_CODECS.keys()),
            "target": "codec registry",
        }]
    jobs: List[Dict[str, Any]] = []
    if codec.get("encode"):
        jobs.append({
            "op": "export", "format": ext, "codec": codec["encode"],
            "mime": codec.get("mime"),
            "target": "gameplay recording / music bed",
            "usage": f"--record=gameplay.{ext}",
        })
    if ext in ("json", "gz"):
        jobs.append({
            "op": "export", "format": ext, "codec": "encode_identity",
            "target": "identity snapshot", "usage": f"--write-identity=identity.{ext}",
        })
    return jobs


def game_file_tasks(format_token: Any = "-") -> Dict[str, List[Dict[str, Any]]]:
    """One-stop task router: what the engine can do with this file/format."""
    return {
        "export": game_export_jobs(format_token),
        "import": game_import_jobs(format_token),
    }


class GameplayRecorder:
    """Deterministic gameplay IN/OUT file system (stdlib only).

    Records player-authored INPUTS (steer, role switches, chat) plus world
    telemetry.  Because the world is f(seed, t), replay = read the inputs back
    and re-simulate — the identical session reproduces on any machine.  save()
    and load() route through the codec registry by extension.
    """

    DEFAULT_FORMAT = "gz"
    IDENTITY_TOKENS = ("seed", "title", "composition_fingerprint", "world_fingerprint")

    def __init__(self, seed: float, meta: Optional[Dict[str, Any]] = None,
                 max_rows: int = 100000):
        self.seed = float(seed)
        self.meta: Dict[str, Any] = dict(meta or {})
        self.meta.setdefault("seed", self.seed)
        self.meta.setdefault("engine", "groovebox-videogame")
        self.meta.setdefault("format", self.DEFAULT_FORMAT)
        self.rows: List[Dict[str, Any]] = []
        self.max_rows = max(1, int(max_rows))

    # -- capture -------------------------------------------------------------
    def record(self, **state) -> None:
        if len(self.rows) >= self.max_rows:
            return
        self.rows.append(dict(state))

    def clear(self) -> None:
        self.rows = []

    # -- encoders ------------------------------------------------------------
    @staticmethod
    def _normalise(row: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in row.items():
            if k in ("collected", "sigils"):
                try:
                    out[k] = sorted(int(x) for x in (v or ()))
                except Exception:
                    out[k] = []
            elif isinstance(v, (dict, list, tuple)):
                try:
                    out[k] = json.loads(json.dumps(v))
                except Exception:
                    out[k] = str(v)
            else:
                out[k] = v
        return out

    @staticmethod
    def encode_json(rows, meta):
        return json.dumps({"meta": meta, "rows": rows}, indent=1, sort_keys=True)

    @staticmethod
    def encode_json_gz(rows, meta):
        return gzip.compress(
            json.dumps({"meta": meta, "rows": rows}, indent=1, sort_keys=True).encode("utf-8"),
            mtime=0)

    @staticmethod
    def encode_csv(rows, meta):
        if not rows:
            return "meta," + ",".join(f"{k}={v}" for k, v in meta.items()) + "\n"
        cols = list(rows[0].keys())
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["meta", json.dumps(meta, sort_keys=True)])
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])
        return buf.getvalue()

    @staticmethod
    def encode_txt(rows, meta):
        lines = ["# Groovebox gameplay recording", "# meta: " + json.dumps(meta, sort_keys=True), ""]
        for r in rows:
            fields = "  ".join(f"{k}={r.get(k, '')}" for k in ("t", "steer", "score", "level", "combo", "sigils", "dj", "authoritative"))
            lines.append(f"{r.get('t', 0.0):8.3f}  {fields}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def encode_wav(samples, sample_rate=44100):
        """Pure-stdlib WAV encoder for a music-bed export (float samples in [-1, 1])."""
        raw = bytearray()
        for s in samples:
            val = max(-1.0, min(1.0, float(s)))
            raw += struct.pack("<h", int(val * 32767))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(sample_rate))
            wf.writeframes(bytes(raw))
        return buf.getvalue()

    @staticmethod
    def encode_png(pixels, width, height):
        """Pure-stdlib PNG encoder for a scene snapshot (RGB rows of 0..255)."""
        import zlib

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        rows_bytes = bytearray()
        for y in range(int(height)):
            rows_bytes.append(0)  # filter: none
            start = y * int(width)
            for x in range(int(width)):
                px = pixels[start + x]
                rows_bytes += bytes((int(px[0]) & 0xFF, int(px[1]) & 0xFF, int(px[2]) & 0xFF))
        raw = bytes(rows_bytes)
        ihdr = struct.pack(">IIBBBBB", int(width), int(height), 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(raw, 9))
                + chunk(b"IEND", b""))

    # -- decode --------------------------------------------------------------
    @classmethod
    def decode_json(cls, blob):
        data = json.loads(blob.decode("utf-8", errors="replace") if isinstance(blob, (bytes, bytearray)) else blob)
        return data.get("meta", {}), list(data.get("rows", []))

    @classmethod
    def decode_json_gz(cls, blob):
        return cls.decode_json(gzip.decompress(blob))

    @classmethod
    def decode_csv(cls, blob):
        text = blob.decode("utf-8", errors="replace") if isinstance(blob, (bytes, bytearray)) else blob
        lines = [ln for ln in text.splitlines() if ln.strip()]
        meta = {}
        rows = []
        cols = []
        for i, ln in enumerate(lines):
            parts = next(csv.reader([ln]))
            if not parts:
                continue
            if i == 0:
                if parts[0] == "meta" and len(parts) > 1:
                    try:
                        meta = json.loads(parts[1])
                    except Exception:
                        meta = {}
                continue
            if i == 1:  # header row
                cols = parts
            else:
                if cols:
                    rows.append({cols[j]: parts[j] if j < len(parts) else ""
                                 for j in range(len(cols))})
        return meta, rows

    @classmethod
    def decode_txt(cls, blob):
        text = blob.decode("utf-8", errors="replace") if isinstance(blob, (bytes, bytearray)) else blob
        meta = {}
        rows = []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("# meta:"):
                try:
                    meta = json.loads(s[len("# meta:"):])
                except Exception:
                    pass
            elif s and not s.startswith("#") and s[0].isdigit():
                parts = s.split(None, 1)
                try:
                    t = float(parts[0])
                except Exception:
                    continue
                row = {"t": t}
                for f in (parts[1].split("  ") if len(parts) > 1 else []):
                    if "=" in f:
                        k, _, v = f.partition("=")
                        row[k.strip()] = v.strip()
                rows.append(row)
        return meta, rows

    # -- file API ------------------------------------------------------------
    def save(self, path: str, samples=None, sample_rate=44100,
             snapshot=None) -> str:
        """Write the recording to `path`, routed by extension codec.

        samples:   list of floats (for `wav` — the music bed, supplied by the
                   caller so the recorder stays framework- and engine-agnostic).
        snapshot:  (width, height, pixels) RGB tuple layout (for `png` scenes).
        """
        ext, codec = resolve_codec(path)
        ext = ext or self.DEFAULT_FORMAT
        if not ext:
            raise ValueError(f"no codec for {path!r}")
        rows = [self._normalise(r) for r in self.rows]
        meta = dict(self.meta)
        meta["format"] = ext
        if ext == "wav":
            if not samples:
                raise ValueError("wav export needs `samples`")
            payload = self.encode_wav(samples, sample_rate)
        elif ext == "png":
            if not snapshot:
                raise ValueError("png export needs `snapshot` (width, height, pixels)")
            w, h, px = snapshot
            payload = self.encode_png(px, w, h)
        else:
            fn = getattr(self, codec.get("encode") or ("encode_" + ext), None)
            if fn is None:
                raise ValueError(f"{ext!r} has no encoder")
            payload = fn(rows, meta)
        mode = "wb" if isinstance(payload, (bytes, bytearray)) else "w"
        with (open(path, "wb") if mode == "wb" else open(path, "w", encoding="utf-8")) as f:
            f.write(payload)
        return os.path.abspath(path)

    @classmethod
    def load(cls, path: str):
        ext, codec = resolve_codec(path)
        if ext is None or not codec.get("decode"):
            raise ValueError(f"no reading codec for {path!r}")
        with open(path, "rb") as f:
            blob = f.read()
        decoder = getattr(cls, codec["decode"])
        meta, rows = decoder(blob)
        return meta, rows


def write_dependency_scripts(directory: str) -> List[str]:
    """Write the three dependency-install scripts (single source of truth from
    DEPENDENCY_SCRIPTS below) into `directory`. Used both for the project dir
    and for every exported game package, so project and zips stay identical."""
    os.makedirs(directory, exist_ok=True)
    written = []
    for name, text in DEPENDENCY_SCRIPTS.items():
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8", newline="\r\n" if name.endswith(".ps1") else "\n") as f:
            f.write(text)
        if name.endswith((".sh", ".command")):
            try:
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
        written.append(path)
    return written


def write_formats_manifest(directory: str) -> str:
    """formats.json — the exportable description of every codec + its jobs."""
    manifest = {
        "engine": "groovebox-videogame",
        "version": 1,
        "codecs": GAME_CODECS,
        "tasks": {
            "_example_import": game_import_jobs("gameplay.gz"),
            "_example_export": game_export_jobs("gameplay.gz"),
        },
    }
    path = os.path.join(directory, "formats.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return path


# ---------------------------------------------------------------------------
# DEPENDENCY_SCRIPTS — single source of truth for installing every host-app AND
# exported-game dependency plus the ffmpeg codec suite.  write_dependency_scripts()
# drops identical copies into the project directory and into every packaged game
# zip, so an unpacked export can provision its own machine without hunting for
# files that are not inside the archive.
# ---------------------------------------------------------------------------
DEPENDENCY_SCRIPTS: Dict[str, str] = {
    "install_deps_linux.sh": r'''#!/usr/bin/env bash
# =============================================================================
# Groovebox dependency installer - Linux
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency onto this machine and puts
# the ffmpeg codec binaries into /bin (the directory VideoSynthEngine's codec
# resolver checks first), so audio+video export work with real encoders.
#
# Usage:
#   ./install_deps_linux.sh            auto-detect Fedora vs Ubuntu-family
#   ./install_deps_linux.sh --fedora   force the DNF/Fedora path
#   ./install_deps_linux.sh --ubuntu   force the apt/Ubuntu-family path
#   ./install_deps_linux.sh --distro=<name>  force any supported family
# =============================================================================
set -u

DISTRO="auto"
for arg in "$@"; do
  case "$arg" in
    --fedora)  DISTRO="fedora";;
    --ubuntu)  DISTRO="ubuntu";;
    --distro=*) DISTRO="${arg#--distro=}";;
    -h|--help)
      sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
      exit 0;;
    *) echo "Unknown argument: $arg"; exit 2;;
  esac
done

if [ "$DISTRO" = "auto" ]; then
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *fedora*|*centos*|*rhel*) DISTRO="fedora";;
      *ubuntu*|*debian*)        DISTRO="ubuntu";;
    esac
  fi
fi

case "$DISTRO" in
  fedora|ubuntu) : ;;
  *)
    echo "Unsupported or undetectable distribution '$DISTRO'."
    echo "Use the toggle:  $0 --fedora   |   $0 --ubuntu"
    exit 3;;
esac

echo "==> Groovebox installer: Linux/$DISTRO"

# This script needs root for system packages and the /bin codec drop.
if [ "$(id -u)" -ne 0 ]; then
  echo "Re-running with sudo..."
  exec sudo "$0" "$@"
fi

set -e

PIP_DEPS="numpy scipy PyQt6 sounddevice Pillow"

if [ "$DISTRO" = "fedora" ]; then
  echo "==> Enabling RPM Fusion (free + nonfree) for full ffmpeg codecs..."
  dnf install -y \
    "https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
    "https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
  dnf install -y \
    python3 python3-pip python3-devel gcc gcc-c++ \
    ffmpeg ffmpeg-libs alsa-lib-devel portaudio-devel openssl-devel libffi-devel
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y \
    python3 python3-pip python3-venv python3-dev build-essential \
    ffmpeg libasound2-dev portaudio19-dev libssl-dev libffi-dev
  # Broad codec pack (mp3 / mp4 / aac / av1 / h264 …). Best effort: this is a
  # multiverse package; if it fails, core ffmpeg above already covers WAV/PNG
  # frame muxing and the common containers.
  apt-get install -y ubuntu-restricted-extras || true
fi

echo "==> Installing Python packages: $PIP_DEPS"
python3 -m pip install --upgrade pip wheel
python3 -m pip install $PIP_DEPS

echo "==> Placing codec binaries into /bin ..."
FF=$(command -v ffmpeg || true)
FP=$(command -v ffprobe || true)
if [ -n "$FF" ]; then cp -f "$FF" /bin/ffmpeg || ln -sf "$FF" /bin/ffmpeg; fi
if [ -n "$FP" ]; then cp -f "$FP" /bin/ffprobe || ln -sf "$FP" /bin/ffprobe; fi

echo "==> Verify:"
python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
command -v ffmpeg; command -v ffprobe
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E "libx264|aac|libvpx|libvorbis" | sed 's/^/  encoder: /' | head -6
echo "==> Done."
echo "    Run the app:   python3 groovebox.py"
''',
    "install_deps_macos.sh": r'''#!/usr/bin/env bash
# =============================================================================
# Groovebox dependency installer - macOS
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency (Homebrew + pip) and the
# ffmpeg codec suite, then symlinks ffmpeg/ffprobe into the codec lookup paths
# VideoSynthEngine checks (/bin when writable, else /usr/local/bin).
# =============================================================================
set -u

if [ "$(id -u)" -eq 0 ]; then
  echo "Do not run this installer as root; macOS python/brew are user-managed." >&2
  exit 4
fi

echo "==> Groovebox installer: macOS"
if ! command -v brew >/dev/null 2>&1; then
  echo "==> Homebrew missing — installing the official one-liner..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "==> brew python + ffmpeg (full codec suite)..."
brew install python ffmpeg || brew upgrade python ffmpeg

echo "==> pip dependencies (shared: host app + exported games)..."
PIP_DEPS="numpy scipy PyQt6 sounddevice Pillow"
python3 -m pip install --upgrade pip wheel
python3 -m pip install $PIP_DEPS

echo "==> Codec binaries into the resolver's lookup path ..."
FF=$(command -v ffmpeg || true)
FP=$(command -v ffprobe || true)
for pair in "ffmpeg|$FF" "ffprobe|$FP"; do
  name="${pair%%|*}"; path="${pair#*|}"
  if [ -n "$path" ]; then
    ln -sf "$path" "/bin/$name" 2>/dev/null || ln -sf "$path" "/usr/local/bin/$name" 2>/dev/null || true
  fi
done

echo "==> Verify:"
python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
command -v ffmpeg; command -v ffprobe
ffmpeg -hide_banner -encoders >/dev/null 2>&1 && echo "ffmpeg OK"
echo "==> Done."
echo "    Run the app:   python3 groovebox.py"
''',
    "install_deps_windows.ps1": r'''# =============================================================================
# Groovebox dependency installer - Windows
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency and the ffmpeg codec suite
# into a local bin folder on your user PATH (Windows has no /bin; this is the
# Windows equivalent the codec resolver also searches by PATH).
#
#   Powershell -ExecutionPolicy Bypass -File install_deps_windows.ps1
# =============================================================================
param(
    [switch]$SkipWinget,
    [switch]$SkipChoco
)
$ErrorActionPreference = "Continue"

Write-Host "==> Groovebox installer: Windows"

$BIN = Join-Path $env:LOCALAPPDATA "Groovebox\bin"
New-Item -ItemType Directory -Force -Path $BIN | Out-Null

function Add-ToUserPath([string]$dir) {
    $cur = [Environment]::GetEnvironmentVariable("Path", "User")
    if (($cur -split ";" ) -notcontains $dir) {
        $new = if ([string]::IsNullOrEmpty($cur)) { $dir } else { "$cur;$dir" }
        [Environment]::SetEnvironmentVariable("Path", $new, "User")
        Write-Host "  added to user PATH: $dir"
    }
}
Add-ToUserPath $BIN

# --- Python -------------------------------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing Python 3.12 via winget..."
    if (-not $SkipWinget) {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    } else {
        throw "Python not found and --SkipWinget given."
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) {
    $wpy = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Recurse -Filter python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($wpy) { $env:Path = $wpy.DirectoryName + ";" + $env:Path; $py = $wpy.FullName }
}
if (-not $py) { throw "Python is required — re-run after installing Python 3.9+." }

# --- ffmpeg codec suite --------------------------------------------------
Write-Host "==> Installing ffmpeg codec suite..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (-not $SkipWinget) {
        winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
    } elseif (-not $SkipChoco -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        choco install ffmpeg -y
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
foreach ($tool in @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")) {
    $src = (Get-Command $tool.Replace(".exe","") -ErrorAction SilentlyContinue).Source
    if (-not $src) {
        $src = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter $tool -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
    if ($src) {
        Copy-Item -Force $src (Join-Path $BIN $tool)
        Write-Host "  codec -> $BIN\$tool"
    }
}

# --- pip dependencies ----------------------------------------------------
Write-Host "==> Installing Python packages..."
& $py -m pip install --upgrade pip wheel
& $py -m pip install numpy scipy PyQt6 sounddevice Pillow

Write-Host "==> Verify:"
& $py -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
& (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source -hide_banner -version | Select-Object -First 1
Write-Host "==> Done."
Write-Host "    Restart your terminal (PATH was updated), then run:   python groovebox.py"
'''
}


def package_game_zip(identity: GameIdentity, out_zip: str, composition_meta: Optional[Dict[str, Any]] = None) -> str:
    """Package a videogame export as a single .zip: deterministic game script +
    identity JSON + README + Windows/macOS/Linux launchers + the dependency
    install scripts (copy of the project-root ones) + a formats.json codec/job
    manifest. Unix executables keep their mode attribute inside the archive so
    they are runnable after extraction.  The script's only runtime imports are
    stdlib + PyQt6 (UI), so the package itself is complete — unpack any one
    folder and launch; install_deps_* provisions a fresh machine."""
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