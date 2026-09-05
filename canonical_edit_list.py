"""Portable canonical edit-list representation shared by Performance, Groovebox and games."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List
import json, hashlib

@dataclass(frozen=True)
class CanonicalMediaEvent:
    event_index: int
    source_id: str
    source_time_s: float
    duration_s: float
    phase: float
    pitch_semitones: float = 0.0
    rate: float = 1.0
    gain: float = 1.0
    pan: float = 0.0
    reverse: bool = False
    resample_mode: str = "phase-locked"
    video_mix: float = 1.0
    game_coupling: float = 1.0

class CanonicalEditList:
    def __init__(self, seed:int, bpm:float, events:Iterable[CanonicalMediaEvent], version:int=1):
        self.seed, self.bpm, self.events, self.version = int(seed), float(bpm), list(events), int(version)
    def to_dict(self)->Dict[str,Any]:
        return {"type":"GrooveboxCanonicalEditList","version":self.version,"seed":self.seed,"bpm":self.bpm,"events":[asdict(e) for e in self.events]}
    def fingerprint(self)->str:
        raw=json.dumps(self.to_dict(),sort_keys=True,separators=(",",":")).encode(); return hashlib.sha256(raw).hexdigest()
    def save(self,path:str):
        d=self.to_dict(); d["fingerprint"]=self.fingerprint()
        with open(path,"w",encoding="utf-8") as f: json.dump(d,f,indent=2)
