import numpy as np
import groovebox as g


def main():
    x=np.linspace(-100.0,100.0,200000,dtype=np.float64)
    s=g.ot_sin_vec_equiv(x)
    c=g.ot_cos_vec_equiv(x)
    es=float(np.max(np.abs(s-np.sin(x))))
    ec=float(np.max(np.abs(c-np.cos(x))))
    print('sin max abs',es)
    print('cos max abs',ec)
    assert es <= 2e-15, es
    assert ec <= 2e-15, ec
    for v in (-3.2,-1.0,0.0,0.5,3.1):
        assert g.ot_sin_vec_equiv(v)==__import__('math').sin(v)
        assert g.ot_cos_vec_equiv(v)==__import__('math').cos(v)
    print('OT/isn/ics trig router parity PASS')

if __name__=='__main__': main()
