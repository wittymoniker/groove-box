import ctypes
from pathlib import Path
from decimal import Decimal, localcontext

from meum_constants import (
    MEUM, MEUM_DECIMAL, MEUM_MINUS_1, MEUM_INV, MEUM_TWO_MINUS, MEUM_NORM,
    MEUM_SQ, MEUM_CUBE, MEUM_FOURTH, MEUM_TWO_POW, MEUM_POWERS_12,
    MEUM_D, MEUM_INV_D, MEUM_NORM_D, meum_equation_residual,
)

assert MEUM.hex() == '0x1.3294a6a84dbb1p+0'
assert float(MEUM_D) == MEUM
assert float(MEUM_INV_D) == MEUM_INV
assert float(MEUM_NORM_D) == MEUM_NORM
assert MEUM_MINUS_1 == float.fromhex('0x1.94a535426dd88p-3')
assert MEUM_TWO_MINUS == float.fromhex('0x1.9ad6b2af6489ep-1')
assert MEUM_SQ == float.fromhex('0x1.6f27b4bb78ebcp+0')
assert MEUM_CUBE == float.fromhex('0x1.b7b2a801b3a72p+0')
assert MEUM_FOURTH == float.fromhex('0x1.07496f2d0ab58p+1')
assert MEUM_TWO_POW == float.fromhex('0x1.2592f636a04dep+1')
assert len(MEUM_POWERS_12) == 12 and MEUM_POWERS_12[6] == 1.0 and MEUM_POWERS_12[7] == MEUM
assert abs(meum_equation_residual()) <= 2e-15

# Native library must expose exactly the same binary64 constants.
root=Path(__file__).resolve().parent
lib=ctypes.CDLL(str(root/'native'/'libgroovebox_accel.so'))
Pd=ctypes.POINTER(ctypes.c_double)
lib.gb_meum_constants_f64.argtypes=[Pd,ctypes.c_size_t]
lib.gb_meum_constants_f64.restype=ctypes.c_size_t
n=lib.gb_meum_constants_f64(None,0)
assert n == 9
arr=(ctypes.c_double*n)()
assert lib.gb_meum_constants_f64(arr,n) == n
expected=[MEUM,MEUM_MINUS_1,MEUM_INV,MEUM_TWO_MINUS,MEUM_NORM,MEUM_SQ,MEUM_CUBE,MEUM_FOURTH,MEUM_TWO_POW]
assert list(arr) == expected
print('MEUM PRECISION PASS', MEUM.hex(), MEUM_DECIMAL[:30]+'…')
