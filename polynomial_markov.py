"""Deterministic polynomial-weighted Markov sampling with auditable event provenance.
No ambient RNG is used. Every transition stores its complete inputs and decision trace.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import hashlib, json, math

@dataclass(frozen=True)
class Polynomial:
    polynomial_id: str
    coefficients: tuple[float, ...]  # ascending powers: c0 + c1*x + ...
    domain: tuple[float, float] = (0.0, 1.0)
    clamp: tuple[float, float] = (0.0, 1.0)
    def evaluate(self, x: float) -> float:
        lo, hi = self.domain
        if not math.isfinite(x) or hi <= lo: raise ValueError('invalid polynomial input/domain')
        z=(x-lo)/(hi-lo); y=0.0
        for c in reversed(self.coefficients): y=y*z+float(c)
        return min(self.clamp[1], max(self.clamp[0], y))
    def fingerprint(self) -> str:
        raw=json.dumps(asdict(self),sort_keys=True,separators=(',',':'))
        return hashlib.sha256(raw.encode()).hexdigest()
    def expression(self) -> str:
        terms=[]
        for i,c in enumerate(self.coefficients):
            if c == 0: continue
            terms.append(f'{c:g}' if i==0 else (f'{c:g}*x' if i==1 else f'{c:g}*x^{i}'))
        return ' + '.join(terms) or '0'

@dataclass
class PolynomialMarkovModel:
    model_id: str
    states: tuple[str, ...]
    transition: dict[str, dict[str, float]]
    weights: dict[str, Polynomial]
    model_version: str = '1'
    def validate(self):
        if not self.states or len(set(self.states)) != len(self.states): raise ValueError('states must be unique and nonempty')
        for src in self.states:
            row=self.transition.get(src,{})
            if set(row)-set(self.states): raise ValueError(f'unknown destination from {src}')
            if any(not math.isfinite(float(v)) or float(v)<0 for v in row.values()): raise ValueError('transition weights must be finite and nonnegative')
            if not any(float(v)>0 for v in row.values()): raise ValueError(f'empty transition row: {src}')
        if set(self.weights)-set(self.states): raise ValueError('weight polynomial key must be a destination state')
    def _coordinate(self, seed: str|int, event_id: str, explicit: float|None) -> float:
        if explicit is not None:
            u=float(explicit)
            if not 0 <= u < 1: raise ValueError('sample_coordinate must be in [0,1)')
            return u
        # Stable deterministic coordinate, not a call to random()/secrets.
        b=f'{seed}\0{event_id}\0{self.model_id}\0{self.model_version}'.encode()
        n=int.from_bytes(hashlib.sha256(b).digest()[:8],'big')
        return n / 2**64
    def step(self, current: str, input_value: float, *, seed: str|int, event_id: str,
             sample_coordinate: float|None=None, trigger_id: str|None=None,
             _prepared: dict|None=None) -> dict[str,Any]:
        # GROOVEBOX_R123_MARKOV_PREPARED_RUN_20261119: rearrange() validates and fingerprints the model
        # once per run (it was O(N^2) work on every step, cubic overall: 128 rows ~3.4 s, 512 rows minutes).
        # The trace content is unchanged.
        prep=_prepared if _prepared is not None else self._prepare()
        if current not in self.states: raise ValueError(f'unknown current state: {current}')
        row=self.transition[current]
        candidates=[]; total=0.0
        for dst in self.states:
            base=float(row.get(dst,0.0))
            if base <= 0: continue
            poly=self.weights.get(dst)
            pv=poly.evaluate(float(input_value)) if poly else 1.0
            score=base*pv
            if score>0:
                pinfo=prep['poly'].get(dst) or (None,'1',None)
                candidates.append({'state':dst,'base_weight':base,'polynomial_id':pinfo[0],
                    'polynomial':pinfo[1],'polynomial_fingerprint':pinfo[2],
                    'input_value':float(input_value),'polynomial_value':pv,'score':score})
                total += score
        if total<=0: raise ValueError('all polynomial-weighted transition scores are zero')
        cumulative=0.0
        for c in candidates:
            c['probability']=c['score']/total
            cumulative += c['probability']; c['cumulative']=cumulative
        u=self._coordinate(seed,event_id,sample_coordinate)
        chosen=next((c for c in candidates if u < c['cumulative']),candidates[-1])
        chosen['cumulative'] # explicit recorded decision boundary
        trace={'seed':str(seed),'trigger_id':trigger_id,'event_id':str(event_id),'event_index':None,
            'model_id':self.model_id,'model_version':self.model_version,'model_fingerprint':prep['fingerprint'],
            'source_state':current,'input_value':float(input_value),'transition_candidates':candidates,
            'sample_coordinate':u,'selection_rule':'first cumulative probability strictly greater than coordinate',
            'selected_state':chosen['state'],'deterministic':True}
        trace['attribution']=(f"{chosen['polynomial_id'] or 'identity'}: {chosen['polynomial']} at x={input_value:g} "
            f"→ {chosen['polynomial_value']:g}; weighted transition probability={chosen['probability']:.9g}; "
            f"u={u:.17g} → {chosen['state']}")
        return trace
    def _prepare(self) -> dict:
        self.validate()
        return {'fingerprint': self.fingerprint(),
                'poly': {k: (v.polynomial_id, v.expression(), v.fingerprint()) for k, v in self.weights.items()}}
    def fingerprint(self):
        payload={'model_id':self.model_id,'model_version':self.model_version,'states':self.states,
          'transition':self.transition,'weights':{k:asdict(v) for k,v in self.weights.items()}}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def rearrange(self, events: Iterable[dict], *, seed: str|int, initial_state: str,
                  input_key: str='value', sample_coordinates: dict[str,float]|None=None) -> list[dict]:
        state=initial_state; out=[]; prep=self._prepare()
        for i,event in enumerate(events):
            eid=str(event.get('event_id',i)); trace=self.step(state,float(event[input_key]),seed=seed,event_id=eid,
              trigger_id=event.get('trigger_id'),sample_coordinate=(sample_coordinates or {}).get(eid),_prepared=prep)
            trace['event_index']=i; trace['source_event']=dict(event); out.append(trace); state=trace['selected_state']
        return out

def replay_trace(model: PolynomialMarkovModel, trace: dict) -> bool:
    if trace.get('model_fingerprint') != model.fingerprint(): return False
    rebuilt=model.step(trace['source_state'],trace['input_value'],seed=trace['seed'],event_id=trace['event_id'],
        trigger_id=trace.get('trigger_id'),sample_coordinate=trace['sample_coordinate'])
    return rebuilt['selected_state']==trace['selected_state'] and rebuilt['transition_candidates']==trace['transition_candidates']
