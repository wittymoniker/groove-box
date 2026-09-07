#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess
from pathlib import Path
from scode_optimizer_bridge import SCodeOptimizerBridge, stable_numeric_identity

ROOT = Path(__file__).resolve().parent
bridge = SCodeOptimizerBridge(ROOT / 'sCode')

cases = [
    ('generic', {'a': 1}, 0, 0, 0, 0, 8, None, True, False),
    ('audio_render', {'shape': [2,512], 'dtype':'float32'}, 7, 1, 13, 7, 8, None, True, False),
    ('visual_frame', ('frame',1920,1080), 8, 2, 31, 2, 6, 128, True, False),
    ('video_frame', b'abc123', 9, 2, 9, 3, 8, None, True, False),
    ('symbols_face', {'value':16,'solid':15,'dotted':0}, 12, 7, 17, 4, 8, 256, True, False),
    ('project_save', {'project':'x'}, 13, 8, 1, 5, 4, None, True, True),
    ('canonical_sequence', [1,2,3,4], 14, 6, 11, 1, 8, None, True, False),
    ('world_chunk', {'x':3,'y':4}, 16, 3, 99, 6, 8, None, False, False),
    ('media_stream', ('pcm',48000,2), 17, 4, 23, 2, 8, None, True, False),
]

probe_rel = bridge.pool_request_probe_script.relative_to(bridge.root)

def parse(s):
    out = {}
    for line in s.splitlines():
        if '=' in line:
            k,v=line.strip().split('=',1)
            try: out[k]=int(round(float(v)))
            except Exception: pass
    return out

for idx,(kind,payload,fid,modality,frame,subtype,lanes,pool_size,dep,side) in enumerate(cases):
    # Override the bridge's last plan width to test exact lane arithmetic.
    bridge._last_plan['parallel_width'] = int(lanes)
    desc = bridge.pool_request_descriptor(kind, payload, format_id=fid, frame=frame,
        subtype=subtype, modality=modality, pool_size=pool_size,
        dependency_ready=dep, side_effecting=side)
    env=os.environ.copy()
    env.update({
        'POOL_FMT':str(desc['format_id']), 'POOL_MODALITY':str(desc['modality']),
        'POOL_ID':str(desc['identity']), 'POOL_SHAPE':str(desc['shape']),
        'POOL_SUBTYPE':str(desc['subtype']), 'POOL_FRAME':str(desc['frame']),
        'POOL_BUCKET':str(desc['frame_bucket']), 'POOL_LANES':str(lanes),
        'POOL_SIZE':str(desc['pool_size']), 'POOL_DEP':'1' if dep else '0',
        'POOL_SIDE_EFFECT':'1' if side else '0',
    })
    p=subprocess.run([str(bridge.stage0),'run',str(probe_rel)], cwd=bridge.root,
                     env=env, capture_output=True, text=True, timeout=10)
    if p.returncode:
        raise SystemExit(f'probe {idx} failed: {p.stderr or p.stdout}')
    sc=parse(p.stdout)
    keys=('request_key','slot','generation','lane','coalesce_slot','buffer_slot','result_slot','poolable')
    mapping={'request_key':'key'}
    mism=[]
    for hk in keys:
        sk=mapping.get(hk,hk)
        if int(desc[hk]) != int(sc.get(sk,-999999)):
            mism.append((hk,desc[hk],sc.get(sk)))
    if mism:
        raise SystemExit(f'FAIL case {idx} {kind}: {mism}\nhost={desc}\nscode={sc}\nout={p.stdout}')
    print(f'PASS {idx}: {kind} fmt={fid} key={desc["request_key"]} slot={desc["slot"]} gen={desc["generation"]}')

bridge.shutdown()
print('PASS: host universal pool descriptor parity with sCode stage-0')
