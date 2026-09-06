from finite_infinity import transition_jump
def test_transition_jump():
    t={0:1,1:2,2:3,3:0}
    for n in [0,1,2,3,4,5,17,10000003]:
        r=transition_jump(t,0,n); assert r.mode=="exact_jump"; assert r.value==n%4
