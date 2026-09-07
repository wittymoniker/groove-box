#!/usr/bin/env python3
"""Microbenchmarks for the required sCode ABI-5 acceleration layer.

These are not whole-Groovebox FPS claims. They isolate the work that ABI-5 now
actually consumes: sCode plan caching, work-claim rejection, deterministic
media result reuse, ndarray pools, and row-slice replacement for old Boolean
row masks.
"""
from __future__ import annotations
import time
import numpy as np
from scode_optimizer_bridge import require_scode_runtime
from media_layer_engine import render_layers


def ms(fn, n=1):
    t0=time.perf_counter()
    out=None
    for _ in range(n): out=fn()
    return (time.perf_counter()-t0)*1000.0/n,out

b=require_scode_runtime()
state={'seed':1.1975807343,'rows':32,'engines':['seeded','phase','goava']}
uncached,_=ms(lambda:b.optimize_sync(state,255,123,32,bypass_cache=True),8)
# Same frame bucket/key => cache path.
b.optimize_sync(state,255,124,32)
cached,_=ms(lambda:b.optimize_sync(state,255,124,32),2000)

b.invalidate_work('canonical')
claim_first,_=ms(lambda:b.claim_work('canonical',state),1)
claim_repeat,_=ms(lambda:b.claim_work('canonical',state),5000)

media_state={
 'version':3,'duration':1.0,'sample_rate':48000,'blend_mode':'Morph Between Layers',
 'heuristic':'Co-fractal Meum','parametric':'u',
 'layers':[
  {'name':'A','kind':'draw','points':[(0,.5),(0.25,.1),(0.5,.8),(1,.5)],'time_scalar':1.0,'gain':1.0,'cycles':3.0,'phase':0.0},
  {'name':'B','kind':'draw','points':[(0,.5),(0.3,.9),(0.7,.2),(1,.5)],'time_scalar':1.1975807343,'gain':.8,'cycles':5.0,'phase':.13},
  {'name':'C','kind':'draw','points':[(0,.5),(0.2,.2),(0.8,.8),(1,.5)],'time_scalar':1.6180339887,'gain':.7,'cycles':7.0,'phase':.27},
 ]}
raw_media,_=ms(lambda:render_layers(media_state),8)
b.memoized_result('media_bench',media_state,lambda:render_layers(media_state),max_entries=4)
pooled_media,_=ms(lambda:b.memoized_result('media_bench',media_state,lambda:render_layers(media_state),max_entries=4),2000)

arr1=b.borrow_array('bench',(65536,),np.float32,zero=True)
arr2=b.borrow_array('bench',(65536,),np.float32,zero=True)
assert arr1 is arr2

# Old row selection allocated/scanned a whole-song boolean mask per row. ABI-5
# build uses contiguous slices after searchsorted. Compare only indexing setup.
t=np.linspace(0,128.0,6_144_000,endpoint=False)
row=27; start=row*4.0; end=start+4.0
mask_ms,_=ms(lambda:((t>=start)&(t<end)),30)
slice_ms,_=ms(lambda:(np.searchsorted(t,start,'left'),np.searchsorted(t,end,'left')),2000)

print('sCode ABI',b.ABI)
print(f'plan uncached ms={uncached:.4f}')
print(f'plan cached ms={cached:.6f}  speedup={uncached/max(cached,1e-12):.1f}x')
print(f'work claim first ms={claim_first:.6f}')
print(f'work claim repeated ms={claim_repeat:.6f}')
print(f'layered media raw ms={raw_media:.4f}')
print(f'layered media sCode memo ms={pooled_media:.6f}  speedup={raw_media/max(pooled_media,1e-12):.1f}x')
print(f'row boolean-mask setup ms={mask_ms:.4f}')
print(f'row slice lookup ms={slice_ms:.6f}  speedup={mask_ms/max(slice_ms,1e-12):.1f}x')
print('stats',b.state_for_project()['stats'])
