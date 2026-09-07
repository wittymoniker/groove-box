#!/usr/bin/env python3
"""Offline Parametric Remix renderer using the same deterministic LiveDJ processor.

Audio is decoded once, processed in control-rate blocks, and written as a WAV.
For video containers the processed audio is muxed back over the original picture
stream; the original video is preserved and output duration follows the processed
audio (video PTS is uniformly conformed when required). Images are copied.
"""
from __future__ import annotations
import ast, math, os, random, shutil, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from dj_effects import LiveDJEffects

AUDIO_EXT={'.wav','.flac','.mp3','.ogg','.opus','.aiff','.aif','.caf'}
VIDEO_EXT={'.mp4','.webm','.avi','.mov','.mkv'}
IMAGE_EXT={'.png','.jpg','.jpeg','.webp','.bmp','.gif','.tif','.tiff'}

def _safe(expr, env):
    node=ast.parse(expr,mode='eval')
    ok=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Mod,ast.Pow,ast.USub,ast.UAdd,ast.And,ast.Or,ast.Not,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE)
    for n in ast.walk(node):
        if not isinstance(n,ok): raise ValueError('unsupported remix syntax: '+type(n).__name__)
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in env): raise ValueError('unsupported remix function')
    return eval(compile(node,'<parametric-remix>','eval'),{'__builtins__':{}},env)

def _script_values(script,t,step,rng):
    env={'t':t,'step':step,'pi':math.pi,'e':math.e,'sin':math.sin,'cos':math.cos,'tan':math.tan,'sqrt':math.sqrt,'abs':abs,'min':min,'max':max,'rand':rng.random}
    out={}
    for raw in (script or '').splitlines():
        line=raw.split('#',1)[0].strip()
        if not line or '=' not in line: continue
        k,e=line.split('=',1); k=k.strip().lower()
        if k in {'goava','rand','boost','speed'}: out[k]=_safe(e.strip(),env)
    return out

def _decode(path,sr=48000):
    ff=shutil.which('ffmpeg')
    if not ff: raise RuntimeError('ffmpeg is required for Parametric Remix file rendering')
    p=subprocess.run([ff,'-v','error','-i',path,'-vn','-ac','1','-ar',str(sr),'-f','f32le','pipe:1'],capture_output=True,check=False)
    if p.returncode!=0 or not p.stdout: raise RuntimeError((p.stderr or b'ffmpeg decode failed').decode('utf-8','replace')[-1500:])
    return np.frombuffer(p.stdout,dtype='<f4').astype(np.float32),sr

def _write_wav(path,x,sr):
    y=np.asarray(x,dtype=np.float32); finite=np.isfinite(y); y=np.where(finite,y,0.0); peak=float(np.max(np.abs(y))) if y.size else 0.0
    if peak>1.0: y=y/peak
    pcm=np.rint(np.clip(y,-1,1)*32767).astype('<i2')
    with wave.open(path,'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

def _process_audio(x,sr,script,seed,pair,bpm,control_hz):
    block=max(64,int(round(sr/max(1,control_hz)))); rng=random.Random(int(seed)); eng=LiveDJEffects(sample_rate=sr); eng.set_context(seed=float(seed),pair=pair,sample_rate=sr)
    pieces=[]; start=0; step=0
    while start<len(x):
        chunk=x[start:min(len(x),start+block)].copy(); t=start/sr; v=_script_values(script,t,step,rng)
        go=max(0,min(1,float(v.get('goava',0))/100.0)); ra=max(0,min(1,float(v.get('rand',0))/100.0)); bo=max(0,min(1,float(v.get('boost',0))/100.0)); speed=max(.25,min(4.0,float(v.get('speed',1.0))))
        eng.amount_goava=go; eng.amount_random=ra; eng.set_boost(max(1,int(sr*2.0)),0.0,bo)
        wet=eng.process(chunk,start_sample=start,goava_scalar=1.1975807343,bpm=bpm)
        if abs(speed-1.0)>1e-6 and len(wet)>2:
            n=max(2,int(round(len(wet)/speed)))
            wet=np.interp(np.linspace(0,len(wet)-1,n),np.arange(len(wet)),wet).astype(np.float32)
        pieces.append(wet); start+=len(chunk); step+=1
    return np.concatenate(pieces) if pieces else np.zeros(1,np.float32)

def render_parametric_file(src,out,script,seed,pair=(0,1),bpm=120.0,control_hz=20):
    src=os.path.abspath(src); out=os.path.abspath(out); ext=Path(src).suffix.lower(); os.makedirs(os.path.dirname(out) or '.',exist_ok=True)
    if ext in IMAGE_EXT:
        shutil.copy2(src,out); return out
    x,sr=_decode(src); y=_process_audio(x,sr,script,seed,pair,float(bpm),int(control_hz))
    if ext in AUDIO_EXT or Path(out).suffix.lower()=='.wav':
        if Path(out).suffix.lower()!='.wav': out=str(Path(out).with_suffix('.wav'))
        _write_wav(out,y,sr); return out
    if ext in VIDEO_EXT:
        ff=shutil.which('ffmpeg'); td=tempfile.mkdtemp(prefix='gb_parametric_'); wav=os.path.join(td,'remix.wav'); _write_wav(wav,y,sr)
        # Preserve original picture stream; processed audio is the authoritative edit.
        cmd=[ff,'-y','-v','error','-i',src,'-i',wav,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-shortest',out]
        p=subprocess.run(cmd,capture_output=True,text=True,check=False)
        shutil.rmtree(td,ignore_errors=True)
        if p.returncode!=0: raise RuntimeError((p.stderr or 'ffmpeg mux failed')[-1500:])
        return out
    raise RuntimeError('Unsupported Parametric Remix input: '+ext)
