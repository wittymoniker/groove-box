#!/usr/bin/env python3
"""Deterministic heuristic reverse engineering for Mathematician's Groovebox.

The solver intentionally reports approximation/error and never claims a unique
inverse unless the tested candidate set has a single minimum within tolerance.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json, math, wave
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

@dataclass
class SignalDescriptor:
    sample_rate: int
    samples: int
    duration_s: float
    rms: float
    peak: float
    dc: float
    fundamental_hz: float
    centroid_hz: float
    spread_hz: float
    rolloff_hz: float
    zcr: float
    transient_density: float
    loop_error: float
    self_similarity: float

@dataclass
class ReconstructionCandidate:
    instruments: int
    similarity: float
    waveform_similarity: float
    spectral_similarity: float
    complexity: float
    loopability: float
    self_similarity: float
    t_independence: float
    cpu_cost: float
    score: float
    fundamental_hz: float
    partials: List[Dict[str, float]]
    recipe: Dict[str, Any]

    def to_dict(self): return asdict(self)

def load_wav_mono(path: str):
    with wave.open(str(path), 'rb') as w:
        sr=w.getframerate(); n=w.getnframes(); ch=w.getnchannels(); sw=w.getsampwidth(); raw=w.readframes(n)
    if sw==1: x=(np.frombuffer(raw,np.uint8).astype(np.float64)-128)/128
    elif sw==2: x=np.frombuffer(raw,'<i2').astype(np.float64)/32768
    elif sw==3:
        b=np.frombuffer(raw,np.uint8).reshape(-1,3); v=b[:,0].astype(np.int32)|(b[:,1].astype(np.int32)<<8)|(b[:,2].astype(np.int32)<<16); v=np.where(v&0x800000,v|~0xffffff,v); x=v.astype(np.float64)/(1<<23)
    elif sw==4: x=np.frombuffer(raw,'<i4').astype(np.float64)/(1<<31)
    else: raise ValueError(f'unsupported WAV sample width {sw}')
    if ch>1: x=x.reshape(-1,ch).mean(axis=1)
    return x.astype(np.float64), int(sr)

def _pitch(x,sr):
    if len(x)<64: return 0.0
    y=x[:min(len(x),sr*4)].astype(float); y-=y.mean(); y*=np.hanning(len(y))
    n=1<<(2*len(y)-1).bit_length(); ac=np.fft.irfft(np.abs(np.fft.rfft(y,n))**2,n)[:len(y)]
    lo=max(2,int(sr/2000)); hi=min(len(ac)-2,int(sr/20))
    if hi<=lo:return 0.0
    seg=ac[lo:hi+1]; mx=float(np.max(seg))
    peaks=np.where((seg[1:-1]>seg[:-2])&(seg[1:-1]>=seg[2:]))[0]+1
    strong=[p for p in peaks if seg[p]>=0.72*mx]
    lag=(strong[0] if strong else int(np.argmax(seg)))+lo
    return float(sr/lag) if lag else 0.0

def describe(x,sr):
    x=np.asarray(x,float); n=len(x); rms=float(np.sqrt(np.mean(x*x))) if n else 0.; peak=float(np.max(np.abs(x))) if n else 0.; dc=float(np.mean(x)) if n else 0.
    if n:
        w=x*np.hanning(n); sp=np.abs(np.fft.rfft(w)); f=np.fft.rfftfreq(n,1/sr); s=float(sp.sum())+1e-15
        cen=float((f*sp).sum()/s); spr=float(np.sqrt((((f-cen)**2)*sp).sum()/s)); cs=np.cumsum(sp); roll=float(f[min(len(f)-1,int(np.searchsorted(cs,.85*cs[-1])))]) if len(f) else 0
        zcr=float(np.mean(np.signbit(x[1:])!=np.signbit(x[:-1]))) if n>1 else 0
        dx=np.abs(np.diff(x)); thr=float(np.mean(dx)+2*np.std(dx)); trans=float(np.mean(dx>thr)) if len(dx) else 0
        edge=max(1,min(n//8,int(sr*.05))); le=float(np.sqrt(np.mean((x[:edge]-x[-edge:])**2))/(rms+1e-12))
        # multi-lag normalized autocorrelation maximum excluding tiny lags
        y=x-x.mean(); den=float(np.dot(y,y))+1e-12; lags=np.linspace(max(1,n//128),max(2,n//2),64,dtype=int); cor=[float(np.dot(y[:-l],y[l:])/den) for l in lags if l<n]; ss=max([0.0]+cor)
    else: cen=spr=roll=zcr=trans=le=ss=0.
    return SignalDescriptor(sr,n,n/sr if sr else 0,rms,peak,dc,_pitch(x,sr),cen,spr,roll,zcr,trans,le,float(max(0,min(1,ss))))

def _partials(x,sr,k=24):
    if not len(x): return []
    n=len(x); sp=np.abs(np.fft.rfft(x*np.hanning(n))); f=np.fft.rfftfreq(n,1/sr)
    if len(sp)<3:return []
    inds=np.where((sp[1:-1]>sp[:-2])&(sp[1:-1]>=sp[2:]))[0]+1
    inds=inds[np.argsort(sp[inds])[-k:]][::-1]
    mx=float(np.max(sp))+1e-15
    return [{"hz":float(f[i]),"amplitude":float(sp[i]/mx)} for i in inds]

def analyze(path: str, max_instruments: int=16, simplicity_weight: float=.35, loop_weight: float=.15, self_similarity_weight: float=.15, t_independence_weight: float=.15):
    x,sr=load_wav_mono(path); d=describe(x,sr); pts=_partials(x,sr,max(24,max_instruments*3))
    # Candidate reconstruction uses strongest partial groups as the simplest realizable additive explanation.
    nfft=len(x); target=np.abs(np.fft.rfft(x*np.hanning(len(x)))) if len(x) else np.array([0.])
    target=target/(np.linalg.norm(target)+1e-15)
    cands=[]
    for ninst in range(1,max(1,max_instruments)+1):
        chosen=pts[:max(1,ninst*2)]; synth=np.zeros_like(target)
        freqs=np.fft.rfftfreq(len(x),1/sr) if len(x) else np.array([0.])
        for p in chosen:
            idx=int(np.argmin(np.abs(freqs-p['hz']))); width=max(1,int(len(freqs)*0.0006)); lo=max(0,idx-width); hi=min(len(synth),idx+width+1); synth[lo:hi]+=p['amplitude']
        synth=synth/(np.linalg.norm(synth)+1e-15)
        specsim=float(max(0,min(1,np.dot(target,synth))))
        wavsim=max(0.0, specsim*(1.0-min(1.0,d.loop_error*.08)))
        complexity=min(1.0,(ninst/max(max_instruments,1))*.72 + len(chosen)/(max_instruments*3)*.28)
        loopability=1/(1+d.loop_error)
        tind=max(0.0,min(1.0,.70*d.self_similarity+.30*loopability))
        sim=.65*specsim+.35*wavsim
        cost=min(1.0,ninst/max(max_instruments,1))
        score=sim - simplicity_weight*complexity + loop_weight*loopability + self_similarity_weight*d.self_similarity + t_independence_weight*tind
        recipe={"kind":"derived_reverse_engineering","userdata":False,"instrument_count":ninst,"base_frequency_hz":d.fundamental_hz or 432.0,"partials":chosen,"loop":True,"loop_unit":"auto","source":str(Path(path).resolve())}
        cands.append(ReconstructionCandidate(ninst,sim,wavsim,specsim,complexity,loopability,d.self_similarity,tind,cost,score,d.fundamental_hz,chosen,recipe))
    cands.sort(key=lambda c:(-c.score,c.instruments))
    unique=False
    if cands:
        unique=len(cands)==1 or (cands[0].score-cands[1].score)>1e-4
    return {"descriptor":asdict(d),"candidates":[c.to_dict() for c in cands],"best":cands[0].to_dict() if cands else None,"effectively_unique_in_tested_space":unique}

def save_analysis(result,path):
    Path(path).write_text(json.dumps(result,indent=2),encoding='utf-8'); return str(Path(path).resolve())
