"""Deterministic spatial synth sources for Cellular Automata and Bouncing Ball.

Pure functions only: callers persist the returned parameters/pattern in canonical state.
"""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np

def _clamp(x, lo, hi): return max(lo, min(hi, x))

def normalize_chord_intervals(intervals, required_count: int, max_slots: int=512):
    """Clamp authored intervals and extend to a requested count without truncating extras.

    Keeping the unused tail is intentional: reducing the visible chord count must not
    destroy previously authored slot pitches, since users may increase the count later.
    """
    limit = max(1, min(512, int(max_slots)))
    needed = max(1, min(limit, int(required_count)))
    try:
        source = list(intervals) if intervals is not None else []
    except TypeError:
        source = []
    if not source:
        source = [0, 4, 7]
    source = [max(-96, min(96, int(x))) for x in source[:limit]]
    defaults = (0, 4, 7, 12, 16, 19, 24)
    while len(source) < needed:
        source.append(defaults[len(source) % len(defaults)])
    return source


def apply_chord_slot_pitch(pitch_track, step_mask, base_pitch: float, intervals, note_count: int, note_budget: int=512, fine_cents=None):
    """Apply deterministic, equal-time chord-slot semitone offsets to one step mask.

    Each slot is an equal subdivision of the active step samples. Work is vectorized
    so a large user-defined note budget does not create a Python loop in the render
    hot path. ``pitch_track`` is updated in place and returned for convenient use.
    """
    track = np.asarray(pitch_track)
    mask = np.asarray(step_mask, dtype=bool)
    if track.ndim != 1 or mask.ndim != 1 or track.size != mask.size:
        return pitch_track
    indices = np.flatnonzero(mask)
    if not indices.size:
        return pitch_track
    budget = max(1, min(512, int(note_budget)))
    count = max(1, min(budget, 512, int(note_count)))
    source = normalize_chord_intervals(intervals, count, 512)
    semitones = np.asarray(source[:count], dtype=np.float64)
    if fine_cents is not None:
        try:
            cents = np.asarray([float(v) for v in list(fine_cents)[:count]], dtype=np.float64)
            if cents.size < count:
                cents = np.pad(cents, (0, count-cents.size), mode="constant")
            semitones = semitones + np.clip(cents, -100.0, 100.0) / 100.0
        except (TypeError, ValueError):
            pass
    sample_count = int(indices.size)
    slot_ids = np.minimum(count - 1, (np.arange(sample_count, dtype=np.int64) * count) // sample_count)
    ratios = np.power(2.0, semitones[slot_ids] / 12.0)
    track[indices] = float(base_pitch) * ratios
    return pitch_track


CHORD_SLOT_FEATURE_DEFAULTS = {
    "fine_cents": 0,
    "velocity": 100,
    "gate": 100,
    "probability": 100,
    "timbre": 50,
    "attack": 0,
    "release": 0,
}


def normalize_chord_slot_features(features, required_count: int, max_slots: int = 512):
    """Return bounded per-note feature dictionaries without discarding saved tails."""
    limit=max(1,min(512,int(max_slots))); needed=max(1,min(limit,int(required_count)))
    try: source=list(features) if features is not None else []
    except TypeError: source=[]
    source=source[:limit]
    out=[]
    ranges={"fine_cents":(-100,100),"velocity":(0,127),"gate":(0,100),
            "probability":(0,100),"timbre":(0,100),"attack":(0,100),"release":(0,100)}
    for raw in source:
        raw=raw if isinstance(raw,dict) else {}
        item=dict(CHORD_SLOT_FEATURE_DEFAULTS)
        for key,(lo,hi) in ranges.items():
            try: value=int(round(float(raw.get(key,item[key]))))
            except (TypeError,ValueError,OverflowError): value=item[key]
            item[key]=max(lo,min(hi,value))
        out.append(item)
    while len(out)<needed:
        out.append(dict(CHORD_SLOT_FEATURE_DEFAULTS))
    return out


def chord_slot_feature_tracks(step_mask, features, note_count: int, *, event_seed: int = 0, note_budget: int = 512):
    """Build deterministic per-sample envelope/timbre/cents lanes for one STEP.

    Chord slots are equal-time subdivisions aligned with ``apply_chord_slot_pitch``.
    Probability is a deterministic per-event gate, not a stochastic render-time RNG;
    velocity, gate length, attack, release, fine tuning, and timbre are independent.
    """
    mask=np.asarray(step_mask,dtype=bool)
    n=int(mask.size); active=np.flatnonzero(mask)
    gain=np.zeros(n,dtype=np.float32); timbre=np.full(n,50.0,dtype=np.float32)
    cents=np.zeros(n,dtype=np.float64)
    if n==0 or not active.size:
        return {"gain":gain,"timbre":timbre,"fine_cents":cents,"slot_ids":np.full(n,-1,dtype=np.int32)}
    budget=max(1,min(512,int(note_budget))); count=max(1,min(budget,512,int(note_count)))
    normalized=normalize_chord_slot_features(features,count,512)
    slots=np.minimum(count-1,(np.arange(active.size,dtype=np.int64)*count)//active.size)
    starts=(slots*active.size+count-1)//count
    ends=((slots+1)*active.size+count-1)//count
    lengths=np.maximum(1,ends-starts)
    progress=(np.arange(active.size,dtype=np.float64)-starts)/lengths
    gain_active=np.ones(active.size,dtype=np.float64)
    timbre_active=np.full(active.size,50.0,dtype=np.float64); cents_active=np.zeros(active.size,dtype=np.float64)
    seed=int(event_seed)&0xffffffff
    for slot in range(count):
        where=(slots==slot)
        if not np.any(where): continue
        f=normalized[slot]
        gain_active[where] *= float(f["velocity"])/100.0
        gate=float(f["gate"])/100.0
        gain_active[where] *= (progress[where] < gate).astype(np.float64)
        attack=float(f["attack"])/100.0
        release=float(f["release"])/100.0
        if attack>0.0:
            gain_active[where] *= (np.clip(progress[where]/attack,0.0,1.0) if attack>0 else 1.0)   # 0 attack = instant
        if release>0.0:
            gain_active[where] *= (np.clip((gate-progress[where])/release,0.0,1.0) if release>0 else (progress[where]<gate).astype(float))
        probability=float(f["probability"])/100.0
        # Stable integer avalanche. No Python randomized hash and no global RNG state.
        x=(seed ^ (((slot+1)*0x9E3779B1)&0xffffffff))&0xffffffff
        x^=x>>16; x=(x*0x7FEB352D)&0xffffffff; x^=x>>15; x=(x*0x846CA68B)&0xffffffff; x^=x>>16
        draw=float(x)/4294967296.0
        if draw>=probability: gain_active[where]=0.0
        timbre_active[where]=float(f["timbre"])
        cents_active[where]=float(f["fine_cents"])
    gain[active]=np.clip(gain_active,0.0,1.27).astype(np.float32)
    timbre[active]=timbre_active.astype(np.float32)
    cents[active]=cents_active
    slot_track=np.full(n,-1,dtype=np.int32); slot_track[active]=slots.astype(np.int32)
    return {"gain":gain,"timbre":timbre,"fine_cents":cents,"slot_ids":slot_track}



def canonical_geometric_rhythm_plan(time_seconds, ensemble_reference=None, *, bpm=120.0, ensemble_mod_amt=0.0):
    """Deterministic, predictive geometric/ensemble modulation schedule.

    The schedule follows the beat grid while adapting to the ensemble's measured
    energy and positive envelope changes (onsets).  All lanes remain phase/time
    aligned: this is a bounded control plan, not a stochastic groove generator.
    Amounts are normalized to [0, .5], so no route can exceed the master's 50% cap.
    """
    t=np.asarray(time_seconds,dtype=np.float64).reshape(-1)
    n=t.size
    if not n:
        empty=np.zeros(0,dtype=np.float32)
        return {"rhythm_gate":empty,"transient":empty,"ensemble_norm":empty,
                "lane_schedule":{k:empty for k in ("vector","wavetable","ball","cellular")},
                "internal_mod_amt":0.0,"external_mod_amt":0.0}
    tempo=float(np.clip(float(bpm),20.0,400.0))
    amount=float(np.clip(float(ensemble_mod_amt),0.0,0.5))
    beat_phase=np.mod(t*(tempo/60.0),1.0)
    # Soft beat accent: attack around each beat decays without a hard gate/click.
    beat=np.exp(-4.5*beat_phase)
    _bptp=float(np.ptp(beat)) if beat.size else 0.0
    beat=np.clip((beat-np.min(beat))/_bptp,0.0,1.0) if _bptp>0 else np.zeros_like(beat)   # flat = no beat
    ref=np.zeros(n,dtype=np.float64)
    if ensemble_reference is not None:
        try:
            candidate=np.asarray(ensemble_reference,dtype=np.float64).reshape(-1)
            if candidate.size==n:
                candidate=np.nan_to_num(candidate,nan=0.0,posinf=0.0,neginf=0.0)
                peak=float(np.percentile(np.abs(candidate),99.0)) if candidate.size else 0.0
                if peak>1e-10:
                    ref=np.clip(candidate/peak,-1.0,1.0)
        except (TypeError,ValueError):
            pass
    energy=np.abs(ref)
    # A short prefix/cumulative smoother avoids convolution allocations for long rows.
    window=max(1,min(n,int(round(max(1.0,tempo/60.0)*n/ max(float(np.ptp(t)) if n>1 else 1.0,1e-9)*0.008))))
    if window>1:
        cs=np.concatenate(([0.0],np.cumsum(energy,dtype=np.float64)))
        smoothed=(cs[window:]-cs[:-window])/window
        energy=np.concatenate((np.full(window-1,smoothed[0] if smoothed.size else 0.0),smoothed))[:n]
    epeak=float(np.percentile(energy,95.0)) if energy.size else 0.0
    energy=np.clip(energy/epeak,0.0,1.0) if epeak>0 else np.zeros_like(energy)
    delta=np.maximum(0.0,np.diff(np.concatenate(([energy[0]],energy))))
    dpeak=float(np.percentile(delta,95.0)) if delta.size else 0.0
    transient=np.clip(delta/dpeak,0.0,1.0) if dpeak>0 else np.zeros_like(delta)
    # If no audible ensemble is present, the beat plan remains deterministic and useful.
    has_reference=bool(np.any(np.abs(ref)>1e-8))
    rhythm=np.clip(0.58*beat+0.27*energy+0.15*transient,0.0,1.0) if has_reference else beat
    lane_schedule={
        "vector":np.clip(0.62+0.38*rhythm,0.50,1.0).astype(np.float32),
        "wavetable":np.clip(0.62+0.38*(1.0-rhythm),0.50,1.0).astype(np.float32),
        "ball":np.clip(0.55+0.45*np.maximum(transient,rhythm*0.30),0.50,1.0).astype(np.float32),
        "cellular":np.clip(0.64+0.36*(1.0-0.65*rhythm),0.50,1.0).astype(np.float32),
    }
    return {"rhythm_gate":rhythm.astype(np.float32),"transient":transient.astype(np.float32),
            "ensemble_norm":ref.astype(np.float32),"lane_schedule":lane_schedule,
            "internal_mod_amt":float(amount*(0.5+0.5*float(np.mean(rhythm)))),
            "external_mod_amt":amount}


def generate_geometric_carrier_audio(time_seconds, base_frequency_hz=432.0, *, sample_rate=48000, total_duration=None,
                                    mix_state=None, vector_state=None, wavetable_state=None,
                                    ball_state=None, cellular_state=None, ensemble_reference=None,
                                    bpm=120.0, ensemble_mod_amt=None, return_modulation=False):
    """Render the four geometric engines as one deterministic global carrier bus.

    This is a pure NumPy/Python render helper; it is called once per render row and
    never touches Qt, the project model, or a device callback. Every oscillator uses
    the shared base-frequency anchor. Ball and cellular parameters modulate both
    frequency and amplitude, and the shared cross-mod amount couples the peer lanes.
    """
    t=np.asarray(time_seconds, dtype=np.float64).reshape(-1)
    if not t.size:
        zero=np.zeros(0,dtype=np.float32)
        return (zero,zero.copy()) if return_modulation else zero
    base=max(0.0,min(50000.0,float(base_frequency_hz)))
    if base <= 0.0:
        zero=np.zeros(t.size,dtype=np.float32)
        return (zero,zero.copy()) if return_modulation else zero
    sr=max(1,int(sample_rate))
    duration=max(float(total_duration or (float(t[-1])+1.0/sr)),1.0/sr)
    mix=dict(mix_state or {})
    vector=dict(vector_state or {})
    wavetable=dict(wavetable_state or {})
    ball=dict(ball_state or {})
    ca=dict(cellular_state or {})
    defaults={"vector":.80,"wavetable":.75,"ball":.65,"cellular":.70,"cross_mod":.0024,"ensemble_mod_amt":0.0}
    gains={k:float(np.clip(float(mix.get(k,v)),0.0,.02 if k=="cross_mod" else (.5 if k=="ensemble_mod_amt" else 1.0))) for k,v in defaults.items()}
    amount=gains["ensemble_mod_amt"] if ensemble_mod_amt is None else float(np.clip(float(ensemble_mod_amt),0.0,.5))
    plan=canonical_geometric_rhythm_plan(t,ensemble_reference,bpm=bpm,ensemble_mod_amt=amount)
    schedule=plan["lane_schedule"]
    ensemble_norm=np.asarray(plan["ensemble_norm"],dtype=np.float64)
    # Phase modulation is deliberately bounded at +/- pi for the full 50% setting.
    phase_mod=(2.0*np.pi*amount*ensemble_norm) if np.any(ensemble_norm) else np.zeros(t.size,dtype=np.float64)
    if max(gains[k] for k in ("vector","wavetable","ball","cellular")) <= 0.0:
        zero=np.zeros(t.size,dtype=np.float32)
        return (zero,zero.copy()) if return_modulation else zero

    # Vector lane: XYZ change the carrier ratio/phase; drive controls the output.
    x=float(np.clip(vector.get("x",0.0),-1.0,1.0)); y=float(np.clip(vector.get("y",0.0),-1.0,1.0)); z=float(np.clip(vector.get("z",0.0),-1.0,1.0))
    drive=float(np.clip(vector.get("drive",.5),0.0,1.0));
    if not bool(vector.get("enabled",True)): drive=0.0
    # Predictive canonical parameter shift: the vector carrier leans into each
    # beat/onset, while remaining a single-note oscillator at the shared base.
    vr=np.clip(1.0+.12*x+.08*y+.05*z + .035*(schedule["vector"]-.80), .25, 4.0)
    vp=2.0*np.pi*base*vr*t + (x-y+z)*np.pi + phase_mod
    vwave=(np.sin(vp)+.22*np.sin(2.0*vp+z+phase_mod)+.08*np.sin(3.0*vp+x+phase_mod))*drive*(.5+.5*float(np.clip(vector.get("canonical_share",.5),0.0,1.0)))
    vwave *= schedule["vector"]
    if bool(vector.get("guard",True)): vwave=np.tanh(vwave)

    # Wavetable lane: curvature, twist, fold and phase all shape a bright table-like wave.
    phase=float(wavetable.get("phase",0.0)); curvature=float(np.clip(wavetable.get("curvature",.5),0.0,1.0))
    twist=float(np.clip(wavetable.get("twist",.5),0.0,1.0)); fold=float(np.clip(wavetable.get("fold",.2),0.0,1.0))
    wx=float(np.clip(wavetable.get("x",.5),0.0,1.0)); wy=float(np.clip(wavetable.get("y",.5),0.0,1.0)); wz=float(np.clip(wavetable.get("z",.5),0.0,1.0))
    # Wavetable shift prefers spaces between beat accents; the table is still
    # a monophonic tone source, not an extra pitch/chord generator.
    wr=np.clip(1.0+.45*(curvature-.5)+.25*(twist-.5)+.10*(wx-.5)+.07*(wy-.5) + .025*(schedule["wavetable"]-.80),.25,4.0)
    wp=2.0*np.pi*base*wr*t+phase*np.pi*2.0+(wz-.5)*np.pi+phase_mod
    _coeffs=wavetable.get("coeffs")
    if _coeffs is not None:
        # GROOVEBOX_R23R_WAVESPACE_20261031: the table is a full point of waveform
        # space (user-drawn cycle or canonical seeded cycle), evaluated exactly and
        # band-limited below Nyquist for each harmonic copy the knobs add.
        from wavespace import fourier_wave as _fw, band_limit as _bl, nyquist_harmonics as _nh
        _a,_b=_coeffs
        def _table(ph):
            _k=_nh(ph,sr,len(_a))
            _aa,_bb=_bl(_a,_b,_k)
            return _fw(ph,_aa,_bb)
        wraw=_table(wp)+(.12+.35*curvature)*_table(2.0*wp+twist*np.pi+wx)+.12*fold*_table(3.0*wp+twist*2.0+wy)
    else:
        wraw=np.sin(wp)+(.12+.35*curvature)*np.sin(2.0*wp+twist*np.pi+wx)+.12*fold*np.sin(3.0*wp+twist*2.0+wy)
    mode=int(wavetable.get("mode",1) or 0)
    if mode%4==1: wraw=np.tanh(wraw*(1.0+4.0*fold))
    elif mode%4==2: wraw=np.sign(wraw)*np.sqrt(np.abs(wraw))   # exact (sign(0)=0 handles zero)
    elif mode%4==3: wraw=np.sin(wraw*np.pi)
    wraw=wraw*(.5+.5*float(np.clip(wavetable.get("canonical_share",.5),0.0,1.0)))
    wraw *= schedule["wavetable"]

    # Bouncing ball: deterministic physics samples shape a smooth modulator.
    steps=max(32,min(2048,int(ball.get("steps",256) or 256)))
    coeff=ball.get("gravity_coefficients",None)
    if not isinstance(coeff,(list,tuple)) or not coeff: coeff=(0.0,0.0,float(ball.get("gravity",.25)))
    bx= float(np.clip(ball.get("x",0.0),-1.0,1.0)); by=float(np.clip(ball.get("y",0.0),-1.0,1.0))
    traj=throw_ball(steps=steps,x=bx,y=by,vx=float(ball.get("vx",.7)),vy=float(ball.get("vy",-.4)),
                    gravity_coefficients=coeff,radius=float(np.clip(ball.get("radius",1.0),.01,1.0)),
                    dt=float(np.clip(ball.get("dt",.025),.0001,.25)),
                    gravity_angle_degrees=float(ball.get("gravity_angle_degrees",90.0)),
                    reverse_polarity_on_hit=bool(ball.get("reverse_polarity_on_hit",True)))
    samples=traj.get("samples",[])
    if samples:
        xp=np.asarray([q["x"] for q in samples],dtype=np.float64); yp=np.asarray([q["y"] for q in samples],dtype=np.float64)
        speed=np.asarray([q["speed"] for q in samples],dtype=np.float64); hit=np.asarray([1.0 if q["collision"] else 0.0 for q in samples],dtype=np.float64)
        u=np.clip(t/max(duration,1.0/sr),0.0,1.0)*(len(samples)-1)
        bt=np.arange(len(samples),dtype=np.float64)
        xx=np.interp(u,bt,xp); yy=np.interp(u,bt,yp); vv=np.interp(u,bt,speed); hh=np.interp(u,bt,hit)
        _sm=float(np.max(speed)) if speed.size else 0.0
        speed_norm=vv/_sm if _sm>0 else np.zeros_like(vv)
        br=np.clip(1.0+.20*xx+.12*yy + .025*(schedule["ball"]-.75),.35,2.0)
        bp=2.0*np.pi*base*br*t
        bwave=np.sin(bp)*(0.22+.30*speed_norm+.18*hh)
    else:
        bwave=np.zeros(t.size,dtype=np.float64)
    bwave *= schedule["ball"] * (.5+.5*float(np.clip(ball.get("canonical_share",.5),0.0,1.0)))

    # Cellular lane: rule/state/dimensions and manual cells determine a repeatable
    # cellular density curve. Vectorized toroidal rolls avoid millions of Python
    # cell-loop operations at the largest supported 64x64 / 256-generation setting.
    width=max(4,min(64,int(ca.get("width",16) or 16))); height=max(4,min(64,int(ca.get("height",16) or 16)))
    states=max(2,min(8,int(ca.get("cell_types",3) or 3))); generations=max(1,min(256,int(ca.get("generations",16) or 16)))
    rule=max(0,min(255,int(ca.get("rule",30) or 0))); neighborhood=str(ca.get("neighborhood","moore")).lower()
    grid=np.fromfunction(lambda yy0,xx0: (((xx0*7+yy0*13+3)%17)==0).astype(np.int16), (height,width), dtype=int)
    manual=ca.get("manual_cells",[])
    if isinstance(manual,(list,tuple)):
        for pos in manual:
            if isinstance(pos,(list,tuple)) and len(pos)>=2:
                try:
                    xx0=int(pos[0]); yy0=int(pos[1])
                    if 0<=xx0<width and 0<=yy0<height: grid[yy0,xx0]=1
                except (TypeError,ValueError,OverflowError): pass
    offsets=((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)) if neighborhood=="moore" else ((0,-1),(-1,0),(1,0),(0,1))
    density=[float(np.sum(grid,dtype=np.float64))/(width*height*(states-1))]
    for _ in range(generations):
        occupied=(grid>0).astype(np.int16,copy=False)
        neighbours=np.zeros((height,width),dtype=np.int16)
        for dx,dy in offsets:
            neighbours += np.roll(occupied,shift=(dy,dx),axis=(0,1))
        bit=(rule >> (neighbours % 8)) & 1
        grid=np.where(bit!=0,np.minimum(states-1,grid+1),np.maximum(0,grid-1)).astype(np.int16,copy=False)
        density.append(float(np.sum(grid,dtype=np.float64))/(width*height*(states-1)))
    du=np.clip(t/max(duration,1.0/sr),0.0,1.0)*(len(density)-1)
    ca_density=np.interp(du,np.arange(len(density),dtype=np.float64),np.asarray(density,dtype=np.float64))
    cr=np.clip(.65+.70*ca_density + .025*(schedule["cellular"]-.80),.30,1.50)
    cp=2.0*np.pi*base*cr*t
    cwave=np.sin(cp)*(0.18+.42*ca_density)+.12*np.sin(cp*2.0)*ca_density

    # Symmetric peer coupling; no lane is privileged as a master. Normalize lane
    # trims to prevent four full-scale generators from multiplying the output.
    lane_waves=(vwave,wraw,bwave,cwave); lane_keys=("vector","wavetable","ball","cellular")
    total_weight=sum(gains[k] for k in lane_keys)
    if total_weight <= 0: return np.zeros(t.size,dtype=np.float32)
    xdepth=float(np.clip(gains["cross_mod"] + 0.02*plan["internal_mod_amt"],0.0,0.02))
    # Full pairwise cross-modulation: each lane receives the other three as a
    # bounded modulator. Coupling is symmetric, so lane ordering grants no priority.
    if xdepth>0.0:
        coupled=[]
        for i,wave in enumerate(lane_waves):
            peers=sum(lane_waves[j] for j in range(len(lane_waves)) if j!=i)/3.0
            coupled.append(wave*(1.0+xdepth*peers))
        lane_waves=tuple(coupled)
    weight_vec=np.asarray([gains[k]/total_weight for k in lane_keys],dtype=np.float64)
    base_mix=sum(w*wave for w,wave in zip(weight_vec,lane_waves))
    # Ensemble → geometry: sound-reference amplitude also contributes at <= 50%.
    # Geometry → ensemble is provided as a separate normalized lane to callers.
    if np.any(ensemble_norm):
        base_mix = base_mix * np.clip(1.0 + amount*ensemble_norm, 0.5, 1.5)
    audio=np.clip(.12*base_mix,-.5,.5).astype(np.float32)
    if return_modulation:
        geo_mod=np.tanh(np.asarray(base_mix,dtype=np.float64)*3.0)
        return audio, np.clip(geo_mod,-1.0,1.0).astype(np.float32)
    return audio

def polynomial_gravity(t: float, coefficients: Iterable[float]=(9.81,), degree: int|None=None) -> float:
    """Evaluate ascending-order polynomial coefficients at normalized time t."""
    coeffs=tuple(float(c) for c in coefficients)
    if degree is not None: coeffs=coeffs[:max(0,int(degree))+1]
    x=float(t); out=0.0
    for c in reversed(coeffs): out=out*x+c
    return out if math.isfinite(out) else 0.0

def throw_ball(steps: int=64, x: float=0.0, y: float=0.0, vx: float=0.7, vy: float=-0.4, radius: float=1.0, gravity_coefficients=(0.0, 0.0, 0.25), restitution: float=0.98, dt: float=0.025, gravity_angle_degrees: float=90.0, reverse_polarity_on_hit: bool=True, initial_polarity: int=1):
    """Deterministic circular-ball simulation with collision-triggered gravity restarts.

    The polynomial's local phase restarts at each wall hit. When enabled, the
    gravity polarity flips on every hit (rather than using a constant-speed
    oscillator or random probability). ``gravity_angle_degrees`` rotates the
    gravity vector; adding 180 degrees reverses its direction exactly.
    """
    n=max(1,min(8192,int(steps))); r=max(0.01,min(1.0,float(radius))); e=_clamp(float(restitution),0.0,1.0)
    x=_clamp(float(x),-r,r); y=_clamp(float(y),-r,r); vx=float(vx); vy=float(vy); dt=_clamp(float(dt),0.0001,0.25)
    angle=math.radians(float(gravity_angle_degrees)%360.0); gx,gy=math.cos(angle),math.sin(angle)
    polarity=1 if int(initial_polarity)>=0 else -1
    local_phase=0.0; hit_count=0; out=[]
    coeffs=tuple(float(c) for c in gravity_coefficients)
    for i in range(n):
        magnitude=polynomial_gravity(local_phase,coeffs)
        ax,ay=polarity*magnitude*gx,polarity*magnitude*gy
        vx0,vy0=vx,vy
        vx+=ax*dt; vy+=ay*dt
        x+=vx*dt; y+=vy*dt
        local_phase+=dt
        d=math.hypot(x,y); collision=False
        if d>=r:
            collision=True
            nx,ny=(x/d,y/d) if d>1e-12 else (1.0,0.0)
            dot=vx*nx+vy*ny
            if dot>0:
                vx-= (1+e)*dot*nx; vy-=(1+e)*dot*ny
            x,y=nx*r,ny*r
            hit_count+=1
            local_phase=0.0  # restart curvature at the impact, not constant-speed cycling
            if reverse_polarity_on_hit:
                polarity=-polarity
        out.append({"x":x/r,"y":y/r,"speed":math.hypot(vx,vy),"collision":collision,"hit_count":hit_count,"gravity_phase":local_phase,"gravity_polarity":polarity,"gravity_angle_degrees":float(gravity_angle_degrees)%360.0,"step":i})
    return {"format":"groovebox-bouncing-ball","version":2,"radius":r,"gravity_coefficients":list(coeffs),"gravity_angle_degrees":float(gravity_angle_degrees)%360.0,"reverse_polarity_on_hit":bool(reverse_polarity_on_hit),"initial_polarity":1 if int(initial_polarity)>=0 else -1,"samples":out}

def cellular_automaton(width: int=16, height: int=16, cell_types: int=2, initial=None, rules=None, generations: int=16, neighborhood: str="moore"):
    """Deterministic multi-state CA. Rules map (current_state, neighbor_count, neighbor_type) to next state.
    Rule records: {"state":s,"neighbor_type":n,"count":k,"next":v}; exact counts only.
    """
    w=max(1,min(256,int(width))); h=max(1,min(256,int(height))); states=max(1,min(32,int(cell_types))); gens=max(0,min(512,int(generations)))
    grid=[[0 for _ in range(w)] for _ in range(h)]
    if initial is not None:
        for yy,row in enumerate(list(initial)[:h]):
            for xx,v in enumerate(list(row)[:w]): grid[yy][xx]=int(v)%states
    rr=[]
    for rule in (rules or []):
        try: rr.append({"state":int(rule["state"])%states,"neighbor_type":int(rule["neighbor_type"])%states,"count":max(0,int(rule["count"])),"next":int(rule["next"])%states})
        except (KeyError,TypeError,ValueError): continue
    offsets=[(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)] if neighborhood=="moore" else [(0,-1),(-1,0),(1,0),(0,1)]
    frames=[[row[:] for row in grid]]
    for _ in range(gens):
        nxt=[]
        for y in range(h):
            row=[]
            for x in range(w):
                cur=grid[y][x]; counts=[0]*states
                for dx,dy in offsets: counts[grid[(y+dy)%h][(x+dx)%w]]+=1
                value=cur
                for rule in rr:
                    if cur==rule["state"] and counts[rule["neighbor_type"]]==rule["count"]: value=rule["next"]; break
                row.append(value)
            nxt.append(row)
        grid=nxt; frames.append([row[:] for row in grid])
    events=[]
    for y,row in enumerate(grid):
        for x,v in enumerate(row):
            if v: events.append({"x":x,"y":y,"state":v,"pitch":36+((x*7+y*5+v*3)%48),"velocity":min(127,48+v*12)})
    return {"format":"groovebox-cellular-automata","version":1,"width":w,"height":h,"cell_types":states,"neighborhood":neighborhood,"rules":rr,"frames":frames,"events":events}
