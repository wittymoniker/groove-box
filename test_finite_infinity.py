from finite_infinity import affine_jump, modular_jump, cycle_jump

def test_affine():
    r=affine_jump(3,2,1,20)
    x=3
    for _ in range(20): x=2*x+1
    assert r.value==x and r.mode=='exact_jump'

def test_modular():
    assert modular_jump(2,7,10**12,13).value == (2+7*(10**12))%13

def test_cycle():
    r=cycle_jump(lambda x:(x+3)%11,0,10**12,max_probe=100)
    assert r.value==(3*(10**12))%11 and r.mode=='exact_cycle'

if __name__=='__main__':
    test_affine(); test_modular(); test_cycle(); print('finite infinity tests OK')
