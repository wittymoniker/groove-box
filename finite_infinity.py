"""Finite-Infinity (FI) exact-jump utilities.

This module deliberately does *not* pretend divergent sequences have ordinary
limits. FI acceleration is used only when a finite certificate proves that a
large/infinite-looking traversal can be represented exactly (cycle, affine
power, modular orbit) or when the caller explicitly requests bounded search.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass(frozen=True)
class FIResult:
    value: Any
    mode: str              # exact_jump | exact_cycle | bounded_search | must_iterate
    steps_evaluated: int
    logical_steps: int
    certificate: dict


def affine_jump(x, a, b, n: int) -> FIResult:
    """Exact O(log n) jump for x <- a*x+b using exponentiation by squaring."""
    n=int(n)
    if n < 0: raise ValueError('n must be nonnegative')
    # Compose affine transforms (m,c): x -> m*x+c.
    rm, rc = 1, 0
    bm, bc = a, b
    k=n; ops=0
    while k:
        if k & 1:
            rm, rc = bm*rm, bm*rc + bc
            ops += 1
        bm, bc = bm*bm, bm*bc + bc
        ops += 1
        k >>= 1
    return FIResult(rm*x+rc, 'exact_jump', ops, n,
                    {'transform':'affine','multiplier':rm,'offset':rc,'proof':'binary affine composition'})


def modular_jump(x: int, step: int, n: int, modulus: int) -> FIResult:
    modulus=int(modulus); n=int(n)
    if modulus <= 0 or n < 0: raise ValueError('invalid modulus/step count')
    v=(int(x) + (n % modulus) * int(step)) % modulus
    return FIResult(v,'exact_jump',1,n,
                    {'transform':'modular_add','modulus':modulus,'proof':'modular periodicity'})


def cycle_jump(step_fn: Callable[[Any],Any], start: Any, n: int, *, max_probe: int=1_000_000) -> FIResult:
    """Detect a repeated hashable state and jump exactly to step n.

    If no cycle is certified within max_probe, returns must_iterate rather than
    inventing a shortcut.
    """
    n=int(n)
    if n < 0: raise ValueError('n must be nonnegative')
    seen={}; values=[]; x=start
    for i in range(min(n+1, int(max_probe)+1)):
        try: key=x
        except Exception: key=repr(x)
        try: hash(key)
        except Exception: key=repr(x)
        if key in seen:
            mu=seen[key]; period=i-mu
            idx = n if n < i else mu + ((n-mu) % period)
            return FIResult(values[idx], 'exact_cycle', i, n,
                            {'preperiod':mu,'period':period,'proof':'repeated deterministic state'})
        seen[key]=i; values.append(x)
        if i == n:
            return FIResult(x,'bounded_search',i,n,{'proof':'direct evaluation reached target'})
        x=step_fn(x)
    return FIResult(x,'must_iterate',min(n,max_probe),n,
                    {'reason':'no certified cycle within probe horizon'})


def graph_bfs(predicate: Callable[[Any],bool], neighbors: Callable[[Any],list], start: Any,
              *, max_states: int=100_000) -> FIResult:
    """Canonical finite graph search with exact duplicate-state collapse."""
    from collections import deque
    q=deque([(start,0)]); seen={start}; examined=0
    while q and examined < max_states:
        node,depth=q.popleft(); examined+=1
        if predicate(node):
            return FIResult(node,'bounded_search',examined,depth,
                            {'unique_states':len(seen),'proof':'BFS over canonical distinct states'})
        for nxt in neighbors(node):
            if nxt not in seen:
                seen.add(nxt); q.append((nxt,depth+1))
    return FIResult(None,'must_iterate',examined,examined,
                    {'unique_states':len(seen),'reason':'solution not certified within finite state budget'})


def transition_jump(transition: dict, start: Any, n: int) -> FIResult:
    """Exact jump over a finite deterministic transition graph via orbit decomposition."""
    n=int(n)
    if n < 0: raise ValueError("n must be nonnegative")
    if n == 0: return FIResult(start,"exact_jump",0,0,{"proof":"identity"})
    seen={}; vals=[]; x=start; probes=0
    while x not in seen:
        seen[x]=len(vals); vals.append(x); probes+=1
        if x not in transition:
            return FIResult(x,"must_iterate",probes,n,{"reason":"transition table incomplete"})
        x=transition[x]
    mu=seen[x]; period=len(vals)-mu
    idx=n if n < len(vals) else mu+((n-mu)%period)
    return FIResult(vals[idx],"exact_jump",probes,n,
        {"transform":"finite_transition_jump","preperiod":mu,"period":period,
         "proof":"finite deterministic orbit decomposition"})
