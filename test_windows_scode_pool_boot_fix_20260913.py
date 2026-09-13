from scode_optimizer_bridge import SCodeOptimizerBridge


def test_builtin_pool_catalog_matches_scode_abi3_contract():
    c = SCodeOptimizerBridge._builtin_pool_catalog()
    assert len(c) == 18
    assert c[0] == {'size': 64, 'buffers': 1, 'streaming': 0, 'persistent': 0}
    assert c[7] == {'size': 64, 'buffers': 2, 'streaming': 1, 'persistent': 0}
    assert c[8] == {'size': 32, 'buffers': 2, 'streaming': 0, 'persistent': 0}
    assert c[9] == {'size': 24, 'buffers': 3, 'streaming': 1, 'persistent': 0}
    assert c[11]['persistent'] == 1
    assert c[16]['persistent'] == 1
    assert c[17] == {'size': 48, 'buffers': 3, 'streaming': 1, 'persistent': 0}
