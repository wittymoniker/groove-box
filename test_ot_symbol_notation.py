from ot_symbol_notation import *

def run():
    for n in range(16):
        for d in Direction:
            g=encode_nibble(n,direction=d)
            assert decode_nibble(g)==n
    for v in list(range(-999,1000))+[-123456,123456]:
        gs=encode_decimal(v)
        assert decode_decimal(gs)==v, (v,gs,decode_decimal(gs))
    assert sum(direction_for(-1,i) in (Direction.DOWN,Direction.LEFT) for i in range(4))==4
    # Across all four direction states, exactly two are negative-oriented.
    assert len([d for d in Direction if d in (Direction.DOWN,Direction.LEFT)])==2
    print('OT symbol codec: PASS')
if __name__=='__main__': run()
