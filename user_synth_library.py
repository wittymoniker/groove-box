#!/usr/bin/env python3
"""Portable user synth and synth-pack serialization helpers."""
from __future__ import annotations
import copy, json
from pathlib import Path
FORMAT_ONE='MathematiciansGrooveboxUserSynth'; FORMAT_PACK='MathematiciansGrooveboxUserSynthPack'; VERSION=1

def synth_snapshot(host,name):
    return {'stable_id':str(getattr(host,'_synth_stable_ids',{}).get(name,name)),'name':name,
            'params':copy.deepcopy(getattr(host,'instrument_param_state',{}).get(name,{})),
            'sequence':copy.deepcopy(getattr(host,'instrument_sequencer_memory',{}).get(name,{})),
            'banks':copy.deepcopy(getattr(host,'instrument_sequence_banks',{}).get(name,{})),
            'selected_sequence':copy.deepcopy(getattr(host,'instrument_selected_sequence',{}).get(name,1)),
            'script':copy.deepcopy(getattr(host,'instrument_scripts',{}).get(name,'')),
            'sample':copy.deepcopy(getattr(host,'instrument_media_samples',{}).get(name,None)),
            'user_owned':True}

def save_one(host,name,path):
    d={'format':FORMAT_ONE,'version':VERSION,'synth':synth_snapshot(host,name)}; Path(path).write_text(json.dumps(d,indent=2,default=str),encoding='utf-8'); return str(Path(path).resolve())
def save_pack(host,names,path):
    d={'format':FORMAT_PACK,'version':VERSION,'synths':[synth_snapshot(host,n) for n in names]}; Path(path).write_text(json.dumps(d,indent=2,default=str),encoding='utf-8'); return str(Path(path).resolve())
def load(path):
    d=json.loads(Path(path).read_text(encoding='utf-8')); f=d.get('format');
    if f==FORMAT_ONE:return [d['synth']]
    if f==FORMAT_PACK:return list(d.get('synths',[]))
    raise ValueError('Not a Groovebox user synth file')
