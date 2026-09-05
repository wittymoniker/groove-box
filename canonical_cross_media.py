"""Canonical cross-media composition contract.

One composition document feeds music, video and videogame generation.  The
waveform analysis is deliberately compact and deterministic so exports can
carry enough information to reconstruct the cross-media relationship.
"""
from __future__ import annotations
import hashlib, json, math
from typing import Any
import numpy as np

VERSION = "cross_media_v13"

def _stable(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:16]

def _finite(x, default=0.0):
    try:
        x=float(x)
        return x if math.isfinite(x) else default
    except Exception:
        return default

def analyze_waveform(waveform, sample_rate=48000, max_points=128):
    """Compact deterministic analysis of the actual rendered music wave."""
    x=np.asarray(waveform if waveform is not None else [], dtype=np.float64).ravel()
    sr=max(1,int(sample_rate or 48000))
    if x.size==0:
        return {"available":False,"sample_rate":sr,"samples":0,"rms":0.0,"peak":0.0,"zero_cross_rate":0.0,"spectral_centroid":0.0,"spectral_flatness":0.0,"energy_envelope":[],"spectrum":[],"fingerprint":_stable({"empty":True,"sr":sr})}
    if x.size > 2_000_000:
        idx=np.linspace(0,x.size-1,2_000_000).astype(np.int64); x=x[idx]
    peak=float(np.max(np.abs(x)))
    rms=float(np.sqrt(np.mean(x*x)))
    zc=float(np.mean(np.signbit(x[1:]) != np.signbit(x[:-1]))) if x.size>1 else 0.0
    nfft=min(4096,max(256,1<<max(8,int(math.log2(min(x.size,4096))))))
    seg=x[:nfft]
    win=np.hanning(len(seg)); mag=np.abs(np.fft.rfft(seg*win))
    freqs=np.fft.rfftfreq(len(seg),1.0/sr)
    sm=float(np.sum(mag))+1e-12
    centroid=float(np.sum(freqs*mag)/sm)
    gm=float(np.exp(np.mean(np.log(np.maximum(mag,1e-12)))))
    am=float(np.mean(mag)+1e-12)
    flatness=float(gm/am)
    bins=max(8,int(max_points))
    edges=np.linspace(0,x.size,bins+1).astype(np.int64)
    env=[]
    for a,b in zip(edges[:-1],edges[1:]):
        y=x[a:b]
        env.append(float(np.sqrt(np.mean(y*y))) if y.size else 0.0)
    sbins=min(bins,64)
    si=np.linspace(0,len(mag)-1,sbins).astype(np.int64)
    spectrum=[float(mag[i]/(np.max(mag)+1e-12)) for i in si]
    out={"available":True,"sample_rate":sr,"samples":int(x.size),"duration":float(x.size/sr),"rms":rms,"peak":peak,"zero_cross_rate":zc,"spectral_centroid":centroid,"spectral_flatness":flatness,"energy_envelope":env,"spectrum":spectrum}
    out["fingerprint"]=_stable(out)
    return out

def build_canonical_document(app, waveform=None, sample_rate=48000):
    """Extract only canonical, cross-media-relevant state from the main app."""
    def cp(v):
        try:
            import copy; return copy.deepcopy(v)
        except Exception: return v
    def val(name, default):
        w=getattr(app,name,None)
        try:
            return float(w.value()) if hasattr(w,"value") else default
        except Exception: return default
    seed_text=""
    try: seed_text=app._seed_text()
    except Exception: seed_text=str(getattr(getattr(app,"input_seed_val",None),"toPlainText",lambda:" ")()).strip()
    sequences={str(k):cp(v) for k,v in (getattr(app,"instrument_sequencer_memory",{}) or {}).items()}
    banks={str(k):cp(v) for k,v in (getattr(app,"instrument_sequence_banks",{}) or {}).items()}
    playlist=cp(getattr(app,"master_playlist_data",[]) or [])
    params=cp(getattr(app,"instrument_param_state",{}) or {})
    samples=cp(getattr(app,"instrument_sample_paths",{}) or {})
    patches=cp(getattr(app,"patch_connections",[]) or [])
    global_algo=cp(getattr(app,"global_algo_state",{}) or {})
    state={
        "version":VERSION,
        "seed":seed_text,
        "bpm":val("spin_bpm",120.0),
        "seq_length":int(round(val("spin_seq_length",16))),
        "playlist_rows":int(round(val("spin_playlist_length",64))),
        "base_frequency":val("spin_base_frequency",432.0),
        "global_convolve":val("spin_global_convolve",0.0),
        "sequences":sequences,
        "sequence_banks":banks,
        "selected_sequences":cp(getattr(app,"instrument_selected_sequence",{}) or {}),
        "playlist":playlist,
        "playlist_automation":cp(getattr(app,"playlist_automation",[]) or []),
        "instrument_params":params,
        "instrument_samples":samples,
        "patch_connections":patches,
        "global_algo":global_algo,
        "domain_eq":cp(getattr(getattr(app,"domain_eq_engine",None),"to_json",lambda:{})()),
        "media":{
            "wav_path":str(getattr(app,"imported_wav_path","") or ""),
            "video_path":str(getattr(app,"imported_video_path","") or ""),
            "video_mix":_finite(getattr(app,"media_video_mix",0.5),0.5),
        },
        "operator_time_offsets":cp(getattr(app,"operator_time_offsets",{}) or {}),
        "toggles":{
            k:bool(getattr(getattr(app,a,None),"isChecked",lambda:False)())
            for k,a in {"randomizer":"btn_local_randomize","phase_lock":"btn_local_phase_lock","goava":"btn_goava","euclidean":"btn_idealize_rhythm","seeded":"btn_seeded_randomize"}.items()
        },
    }
    state["composition_fingerprint"]=_stable(state)
    state["waveform"] = analyze_waveform(waveform,sample_rate) if waveform is not None else cp(getattr(app,"_last_cross_media_wave_analysis",None) or analyze_waveform(None,sample_rate))
    state["waveform_fingerprint"]=state["waveform"].get("fingerprint","")
    state["cross_media_fingerprint"]=_stable({"composition":state["composition_fingerprint"],"waveform":state["waveform_fingerprint"]})
    return state

def frame_projection(document, t=0.0):
    """Small per-frame projection shared conceptually by visual/game consumers."""
    d=document or {}; wf=d.get("waveform") or {}; env=wf.get("energy_envelope") or [0.0]
    idx=int(abs(_finite(t))*max(1,len(env)))%len(env)
    energy=_finite(env[idx])
    centroid=_finite(wf.get("spectral_centroid"),0.0)
    return {"energy":energy,"spectral_centroid":centroid,"rms":_finite(wf.get("rms")),"phase":(float(t)*_finite(d.get("bpm"),120.0)/60.0)%1.0,"composition_fingerprint":d.get("composition_fingerprint",""),"cross_media_fingerprint":d.get("cross_media_fingerprint","")}


def build_cross_media_from_canonical(document, waveform=None, sample_rate=48000):
    """Build cross-media state strictly from an already-canonical document.

    No app/widget lookup occurs here. This is the v13 boundary used by audio,
    video and game consumers.
    """
    d = document if isinstance(document, dict) else {}
    base = {
        "version": VERSION,
        "seed": d.get("seed", ""),
        "bpm": d.get("bpm", 120.0),
        "seq_length": d.get("seq_length", 16),
        "playlist_rows": d.get("playlist_rows", 64),
        "sequences": d.get("instrument_sequencer_memory", d.get("sequences", {})),
        "sequence_banks": d.get("instrument_sequence_banks", d.get("sequence_banks", {})),
        "playlist": d.get("master_playlist_data", d.get("playlist", [])),
        "instrument_params": d.get("instrument_param_state", d.get("instrument_params", {})),
        "instrument_samples": d.get("instrument_sample_paths", d.get("instrument_samples", {})),
        "patch_connections": d.get("patch_connections", []),
        "global_algo": d.get("global_algo", {}),
        "operator_time_offsets": d.get("operator_time_offsets", {}),
        "media_carrier": d.get("media_carrier", d.get("media", {})),
        "project_notes": d.get("project_notes", ""),
    }
    base["composition_fingerprint"] = _stable(base)
    prior = d.get("cross_media") if isinstance(d.get("cross_media"), dict) else {}
    if waveform is not None:
        wf = analyze_waveform(waveform, sample_rate)
    else:
        wf = prior.get("waveform") or analyze_waveform(None, sample_rate)
    base["waveform"] = wf
    base["waveform_fingerprint"] = wf.get("fingerprint", "")
    base["cross_media_fingerprint"] = _stable({
        "composition": base["composition_fingerprint"],
        "waveform": base["waveform_fingerprint"],
    })
    return base
