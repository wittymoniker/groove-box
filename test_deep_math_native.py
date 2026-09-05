import ctypes, math
from pathlib import Path
import numpy as np
from universal_field import M, meum_space, _meum_space_python_reference, canonical_field, projection, clear_projection_cache
ROOT=Path(__file__).resolve().parent
lib=ctypes.CDLL(str(ROOT/'native'/'libgroovebox_accel.so'))
Pd=ctypes.POINTER(ctypes.c_double)
lib.gb_meum_space_f64.argtypes=[ctypes.c_size_t,ctypes.c_size_t,ctypes.c_double,Pd,Pd,Pd,Pd]
lib.gb_ot_apply_f64.argtypes=[Pd,Pd,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_double,Pd]
n=4096; start=17
outs=[np.empty(n,np.float64) for _ in range(4)]
lib.gb_meum_space_f64(start,n,M,*[x.ctypes.data_as(Pd) for x in outs])
ref=_meum_space_python_reference(start,n)
for got,key in zip(outs,ref):
    assert np.max(np.abs(got-np.asarray(ref[key]))) < 2e-12
# OT zero policy: 0/0=1, n/0 can be inf or n by owning operation.
a=np.array([0.,2.,-3.]); b=np.zeros(3); out=np.empty(3)
lib.gb_ot_apply_f64(a.ctypes.data_as(Pd),b.ctypes.data_as(Pd),3,3,2,0.,out.ctypes.data_as(Pd))
assert out[0]==1 and math.isinf(out[1]) and math.isinf(out[2])
lib.gb_ot_apply_f64(a.ctypes.data_as(Pd),b.ctypes.data_as(Pd),3,3,3,0.,out.ctypes.data_as(Pd))
assert out.tolist()==[1.,2.,-3.]
# Representation cache is identity-transparent.
f=canonical_field(M,'deep-native-test',[1,2,3],[.2,.4])
clear_projection_cache(); p1=projection(f,'meum_field'); p2=projection(f,'meum_field')
assert p1 is p2 and p1['field_id']==f['field_id']
print('DEEP MATH NATIVE PASS', f['field_id'], n)
