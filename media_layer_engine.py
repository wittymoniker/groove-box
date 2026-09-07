#!/usr/bin/env python3
"""Deterministic layered Draw/Record/Sample reconstruction for Groovebox."""
from __future__ import annotations
import ast, math, os, subprocess, wave
from groovebox_media_tools import resolve_local_tool
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import numpy as np
MEUM=1.1975807343
PHI=(1+math.sqrt(5.0))/2.0

# Decoding is orders of magnitude more expensive than mixing. Keep a small,
# bounded cache keyed by immutable file metadata + target shape. The higher-level
# LayeredSignalLab result cache is sCode-routed; this lower cache avoids duplicate
# ffmpeg work across distinct layer arrangements that reuse the same source.
_DECODE_CACHE=OrderedDict()
_DECODE_CACHE_MAX=4
_DECODE_CACHE_MAX_SAMPLES=2_000_000

def _decode(path:str, sr:int, n:int)->np.ndarray:
    path=os.path.abspath(path)
    try:
        st=os.stat(path); key=(path,int(st.st_mtime_ns),int(st.st_size),int(sr),int(n))
    except Exception:
        key=(path,0,0,int(sr),int(n))
    hit=_DECODE_CACHE.get(key)
    if hit is not None:
        _DECODE_CACHE.move_to_end(key)
        return hit
    ff=resolve_local_tool('ffmpeg', required=False)
    if ff:
        p=subprocess.run([ff,'-v','error','-i',path,'-vn','-ac','1','-ar',str(sr),'-f','f32le','pipe:1'],capture_output=True,check=False)
        if p.returncode==0 and p.stdout:
            x=np.frombuffer(p.stdout,dtype='<f4').astype(np.float64)
        else: x=np.zeros(1,float)
    elif path.lower().endswith('.wav'):
        with wave.open(path,'rb') as w:
            raw=w.readframes(w.getnframes()); sw=w.getsampwidth(); ch=w.getnchannels(); src=w.getframerate()
        if sw==2: x=np.frombuffer(raw,dtype='<i2').astype(float)/32768.0
        else: x=np.zeros(1,float)
        if ch>1: x=x[:(len(x)//ch)*ch].reshape(-1,ch).mean(axis=1)
        if src!=sr and len(x)>1: x=np.interp(np.linspace(0,1,max(2,int(len(x)*sr/src)),endpoint=False),np.linspace(0,1,len(x),endpoint=False),x)
    else: x=np.zeros(1,float)
    if len(x)<2:
        out=np.zeros(n,float)
    else:
        out=np.interp(np.linspace(0,1,n,endpoint=False),np.linspace(0,1,len(x),endpoint=False),x)
    if int(n)<=_DECODE_CACHE_MAX_SAMPLES:
        out=np.asarray(out,dtype=np.float32)
        _DECODE_CACHE[key]=out
        _DECODE_CACHE.move_to_end(key)
        while len(_DECODE_CACHE)>_DECODE_CACHE_MAX:
            _DECODE_CACHE.popitem(last=False)
    return out

def curve_from_points(points:Iterable, n:int, cycles:float=1.0, phase:float=0.0)->np.ndarray:
    pts=[]
    for p in points or []:
        try: pts.append((float(p[0]),float(p[1])))
        except Exception: pass
    if not pts: pts=[(0,.5),(1,.5)]
    pts.sort(); xs=np.array([max(0,min(1,p[0])) for p in pts]); ys=np.array([1-2*max(0,min(1,p[1])) for p in pts])
    if xs[0]>0: xs=np.r_[0.,xs]; ys=np.r_[ys[0],ys]
    if xs[-1]<1: xs=np.r_[xs,1.]; ys=np.r_[ys,ys[-1]]
    u=np.mod(np.linspace(0,1,n,endpoint=False)*max(.000001,float(cycles))+float(phase),1.0)
    return np.interp(u,xs,ys)

def layer_wave(layer:Dict[str,Any], sr:int, n:int)->np.ndarray:
    kind=str(layer.get('kind','draw'))
    if kind in {'audio','record','sample'} and layer.get('path') and os.path.isfile(str(layer['path'])):
        x=_decode(str(layer['path']),sr,n)
    else:
        x=curve_from_points(layer.get('points',[]),n,float(layer.get('cycles',1.0) or 1.0),float(layer.get('phase',0.0) or 0.0))
    gain=float(layer.get('gain',1.0) or 0.0)
    return np.asarray(x,float)*gain

def _alpha(u:np.ndarray, mode:str, expr:str='')->np.ndarray:
    u=np.clip(np.asarray(u,float),0,1)
    m=(mode or 'Linear').lower()
    if 'nearest' in m: return (u>=.5).astype(float)
    if 'equal' in m: return np.sin(u*math.pi/2.0)**2
    if 'smooth' in m: return u*u*(3-2*u)
    if 'co-fractal' in m or 'cofractal' in m:
        # bounded deterministic perturbation, endpoints preserved
        wob=np.sin(math.tau*(u*MEUM + (u*u)/PHI))*u*(1-u)*0.22
        return np.clip(u+wob,0,1)
    if 'parametric' in m and expr.strip():
        allowed={'u':u,'t':u,'MEUM':MEUM,'PHI':PHI,'pi':math.pi,'sin':np.sin,'cos':np.cos,'sqrt':np.sqrt,'abs':np.abs,'minimum':np.minimum,'maximum':np.maximum}
        node=ast.parse(expr,mode='eval')
        ok=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.UnaryOp,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod,ast.USub,ast.UAdd)
        for q in ast.walk(node):
            if not isinstance(q,ok): raise ValueError('unsupported parametric alpha syntax')
            if isinstance(q,ast.Call) and (not isinstance(q.func,ast.Name) or q.func.id not in allowed): raise ValueError('unsupported parametric function')
        out=eval(compile(node,'<layer-alpha>','eval'),{'__builtins__':{}},allowed)
        return np.clip(np.asarray(out,float),0,1)
    return u

def render_layers(state:Dict[str,Any])->Tuple[np.ndarray,int]:
    """Render reusable Draw/Record/Sample layers into one deterministic wavetable.

    ``Morph`` interprets relative time scalars as the durations of transitions
    between successive layer instances. ``Pooled Overlay`` resamples every layer
    across the entire requested duration and combines them using the same
    heuristic/parametric alpha family as deterministic per-layer weights.
    """
    sr=max(8000,min(192000,int(state.get('sample_rate',48000))))
    duration=max(.02,min(3600.0,float(state.get('duration',2.0))))
    n=max(2,int(round(sr*duration)))
    layers=[x for x in (state.get('layers') or []) if isinstance(x,dict)]
    if not layers: return np.zeros(n,dtype=np.float32),sr
    waves=[layer_wave(l,sr,n) for l in layers]
    if len(waves)==1: return np.clip(waves[0],-1,1).astype(np.float32),sr
    mode=str(state.get('heuristic','Linear')); expr=str(state.get('parametric',''))
    blend=str(state.get('blend_mode','Morph Between Layers') or 'Morph Between Layers').lower()
    if 'overlay' in blend or 'pool' in blend or 'layer' in blend and 'morph' not in blend:
        raw=np.array([max(1e-9,float(l.get('time_scalar',1.0) or 1.0)) for l in layers],float)
        raw=raw/max(float(np.sum(raw)),1e-15)
        # Give the heuristic a deterministic normalized layer coordinate. The
        # resulting scalar is a weighting curve, not a time-varying RNG branch.
        coord=np.linspace(0.0,1.0,len(layers),endpoint=True)
        shaped=_alpha(coord,mode,expr)
        shaped=np.maximum(1e-12,np.asarray(shaped,float)+1e-12)
        weights=raw*shaped
        weights=weights/max(float(np.sum(weights)),1e-15)
        out=np.zeros(n,float)
        for w,x in zip(weights,waves): out += float(w)*x
    else:
        # N layers imply N-1 transition intervals. The scalar attached to each
        # preceding layer defines that interval's share of the requested total.
        weights=[max(1e-9,float(l.get('time_scalar',1.0) or 1.0)) for l in layers[:-1]]
        total=sum(weights); bounds=[0.0]; acc=0.0
        for w in weights: acc+=w/total; bounds.append(acc)
        bounds[-1]=1.0
        pos=np.linspace(0,1,n,endpoint=False); out=np.empty(n,float)
        for i in range(len(waves)-1):
            a,b=bounds[i],bounds[i+1]; mask=(pos>=a)&((pos<b) if i<len(waves)-2 else (pos<=b))
            if not np.any(mask): continue
            u=(pos[mask]-a)/max(1e-15,b-a); al=_alpha(u,mode,expr)
            out[mask]=waves[i][mask]*(1-al)+waves[i+1][mask]*al
    finite=np.isfinite(out); out=np.where(finite,out,0.0)
    peak=float(np.max(np.abs(out))) if out.size else 0.0
    if peak>1.0: out=out/peak
    return out.astype(np.float32),sr

def write_wav(path:str,x:np.ndarray,sr:int)->str:
    path=os.path.abspath(path); os.makedirs(os.path.dirname(path) or '.',exist_ok=True)
    y=np.clip(np.asarray(x,float),-1,1); pcm=np.rint(y*32767).astype('<i2')
    with wave.open(path,'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(sr)); w.writeframes(pcm.tobytes())
    return path

def spectrum_peaks(x:np.ndarray,sr:int,count:int=8):
    x=np.asarray(x,float); n=len(x)
    if n<8:return []
    m=min(n,131072); y=x[:m]-float(np.mean(x[:m])); win=np.hanning(m); mag=np.abs(np.fft.rfft(y*win)); hz=np.fft.rfftfreq(m,1.0/sr)
    if len(mag): mag[0]=0
    idx=np.argpartition(mag,-min(count,len(mag)))[-min(count,len(mag)):]
    idx=idx[np.argsort(mag[idx])[::-1]]
    top=float(mag[idx[0]]) if len(idx) and mag[idx[0]]>0 else 1.0
    return [(float(hz[i]),float(mag[i]/top)) for i in idx]
