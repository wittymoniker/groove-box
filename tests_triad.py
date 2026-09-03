import ast, pathlib, numpy as np
from canonical_triad import ot_master_tensor_reference
src=pathlib.Path('groovebox.py').read_text(); tree=ast.parse(src)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ot_master_transform')
ns={'np':np,'MEUM_NORM':(1.1975807343385265188-1)/1.1975807343385265188}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'<ot>','exec'),ns)
rng=np.random.default_rng(20260903)
for scale in (.25,1,2,4,8):
    x=rng.normal(size=5000)*scale
    a=ns['ot_master_transform'](x); b=ot_master_tensor_reference(x,ns['MEUM_NORM'])
    assert np.array_equal(a,b), (scale,float(np.max(np.abs(a-b))))
print('OT tensor correspondence: PASS')
