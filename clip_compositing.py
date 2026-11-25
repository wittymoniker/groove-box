"""Non-destructive clip layers, chroma key, masks, and transform descriptors."""
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class ChromaKey:
    enabled: bool=False; color: tuple[int,int,int]=(0,255,0); tolerance: float=0.22
    softness: float=0.08; spill_suppression: float=0.35; edge_shrink: float=0.0
    def validate(self):
        if len(self.color)!=3 or any(not 0<=int(c)<=255 for c in self.color): raise ValueError('key color must be RGB 0..255')
        for k in ('tolerance','softness','spill_suppression'):
            v=float(getattr(self,k))
            if not 0<=v<=1: raise ValueError(f'{k} must be in [0,1]')
        if not 0<=self.edge_shrink<=32: raise ValueError('edge_shrink must be 0..32 pixels')
@dataclass
class Transform:
    kind: str; parameters: dict[str,Any]=field(default_factory=dict); enabled: bool=True
@dataclass
class ClipLayer:
    layer_id: str; source: str; order: int=0; visible: bool=True; opacity: float=1.0
    blend_mode: str='normal'; transforms: list[Transform]=field(default_factory=list)
    key: ChromaKey=field(default_factory=ChromaKey); mask_source: str|None=None
    def validate(self):
        if not 0<=self.opacity<=1: raise ValueError('opacity must be in [0,1]')
        if self.blend_mode not in {'normal','add','multiply','screen','overlay','difference','darken','lighten'}: raise ValueError('unsupported blend mode')
        self.key.validate()
        allowed={'translate','scale','rotate','crop','skew','perspective','blur','sharpen','mirror','color_matrix','mask'}
        if any(t.kind not in allowed for t in self.transforms): raise ValueError('unsupported transform')
@dataclass
class ClipComposition:
    layers: list[ClipLayer]=field(default_factory=list)
    def add(self,layer): layer.validate(); self.layers.append(layer); self.layers.sort(key=lambda x:x.order)
    def remove(self,layer_id): self.layers=[x for x in self.layers if x.layer_id!=layer_id]
    def manifest(self):
        for l in self.layers: l.validate()
        return {'pipeline':'non-destructive-alpha-preserving','layers':[asdict(x) for x in sorted(self.layers,key=lambda x:x.order)]}
