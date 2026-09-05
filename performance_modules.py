#!/usr/bin/env python3
"""Portable .mgbmpf Performance module/effect patches."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, math, time
from typing import Any, Dict, List

FORMAT='MathematiciansGrooveboxModulePatchFile'
VERSION=1

@dataclass
class ModulePatch:
    name:str
    kind:str='module'
    macro:float=1.0
    gate:bool=True
    canonical_blanket:Dict[str,float]=None
    routing:Dict[str,Any]=None
    payload:Dict[str,Any]=None
    def to_dict(self):
        d=asdict(self); d.update({'format':FORMAT,'version':VERSION}); return d

def canonical_blanket(active: Dict[str,float]):
    """Scale active canonicals into one nonnegative collinearity blanket.
    The blanket is deterministic and normalized; it is a modulation routing model,
    not a claim that arbitrary canonical signals are mathematically collinear.
    """
    a={str(k):max(0.0,float(v)) for k,v in (active or {}).items() if float(v)!=0.0}
    norm=math.sqrt(sum(v*v for v in a.values())) or 1.0
    return {k:v/norm for k,v in a.items()}

def save_patch(path, patch:ModulePatch):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(patch.to_dict(),indent=2),encoding='utf-8'); return str(p.resolve())

def load_patch(path):
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if d.get('format')!=FORMAT: raise ValueError('Not a .mgbmpf MathematiciansGrooveboxModulePatchFile')
    return d

def capture_host_module(host,name='Performance Module'):
    active={}
    for key,attr in [('goava','goava_active'),('randomizer','randomizer_active'),('phase_lock','phase_lock_active'),('fractallizer','fractallizer_active'),('pkp','pkp_active')]:
        if bool(getattr(host,attr,False)): active[key]=1.0
    # Fall back to visible strengths where boolean names differ among builds.
    for key,attr in [('goava','slider_goava'),('randomizer','slider_randomizer'),('phase_lock','slider_phase_lock'),('fractallizer','slider_fractalizer'),('pkp','slider_pkp_envelope')]:
        w=getattr(host,attr,None)
        if w is not None:
            try:
                val=float(w.value()); active[key]=max(active.get(key,0.0),val/(200.0 if val>100 else 100.0))
            except Exception: pass
    payload={'seed':str(host._seed_text()) if hasattr(host,'_seed_text') else '', 'created_unix':time.time()}
    return ModulePatch(name=name,kind='module',canonical_blanket=canonical_blanket(active),routing={'macro':'simple_knob','gate':'trigger'},payload=payload)

def capture_track_effect(host,name='Track Canonical Effect'):
    p=capture_host_module(host,name); p.kind='effect'; p.routing={'scope':'selected_track','macro':'simple_knob','gate':'trigger','live_switch':True}; return p

def apply_macro(host,patch,amount:float,gate:bool=True):
    amount=max(0.0,min(1.0,float(amount))); blanket=patch.get('canonical_blanket') or {}
    setattr(host,'_performance_effect_patch',patch); setattr(host,'_performance_effect_macro',amount); setattr(host,'_performance_effect_gate',bool(gate))
    # Prefer existing public-ish sliders; this makes the module immediately audible without mutating userdata.
    mapping={'goava':'slider_goava','randomizer':'slider_randomizer','phase_lock':'slider_phase_lock','fractallizer':'slider_fractalizer','pkp':'slider_pkp_envelope'}
    if gate:
        for k,w in blanket.items():
            obj=getattr(host,mapping.get(k,''),None)
            if obj is not None:
                try:
                    mx=obj.maximum(); obj.setValue(type(obj.value())(min(mx,amount*float(w)*mx)))
                except Exception: pass
    if hasattr(host,'_on_live_source_changed'):
        try: host._on_live_source_changed()
        except Exception: pass
    return blanket
