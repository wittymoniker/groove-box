from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent
stage=ROOT/'sCode'/'bootstrap'/'linux-x86_64'/'scode0'
if not stage.exists():
    raise SystemExit('linux-x86_64 stage0 absent')
r=subprocess.run([str(stage),'run','apps/groovebox/pool_catalog.sC'],cwd=ROOT/'sCode',capture_output=True,text=True,timeout=15)
assert r.returncode==0,(r.stdout,r.stderr)
assert 'pool_catalog_abi=1' in r.stdout
assert 'pool_abi=3' in r.stdout
assert 'pool_format_abi=1' in r.stdout
assert 'pool_format_count=18' in r.stdout
lines=[x for x in r.stdout.splitlines() if x.startswith('format=')]
assert len(lines)==18,len(lines)
assert lines[0]=='format=0,size=64,buffers=1,streaming=0,persistent=0'
assert lines[7]=='format=7,size=64,buffers=2,streaming=1,persistent=0'
assert lines[17]=='format=17,size=48,buffers=3,streaming=1,persistent=0'
print('PASS: native stage0 pool catalog ABI-1 / 18 deterministic formats')

# Universal request-probe dispatch is also part of the frozen stage-0 pool contract.
env={**__import__('os').environ,'POOL_FMT':'17','POOL_MODALITY':'4','POOL_ID':'12345','POOL_SHAPE':'23','POOL_SUBTYPE':'2','POOL_FRAME':'9','POOL_BUCKET':'2','POOL_LANES':'8','POOL_SIZE':'48','POOL_DEP':'1','POOL_SIDE_EFFECT':'0'}
r2=subprocess.run([str(stage),'run','apps/groovebox/pool_request_probe.sC'],cwd=ROOT/'sCode',env=env,capture_output=True,text=True,timeout=15)
assert r2.returncode==0,(r2.stdout,r2.stderr)
for key in ('key=','slot=','generation=','lane=','coalesce_slot=','buffer_slot=','result_slot=','poolable=1'):
    assert key in r2.stdout,(key,r2.stdout)
print('PASS: native stage0 universal pool request probe dispatch')
