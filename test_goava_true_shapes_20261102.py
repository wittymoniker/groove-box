import os
SRC = os.path.dirname(os.path.abspath(__file__))


def test_goava_true_shapes_present_and_goava_only():
    g = open(os.path.join(SRC, "groovebox.py"), encoding="utf-8").read()
    a = g.index("def _subscene_goava"); b = g.index("def _subscene_math_filaments")
    body = g[a:b]
    assert "GOAVA_TRUE_SHAPES_20261102" in body
    assert 'if not st["snap"].get("goava"):' in body[:600]      # nothing is drawn while GOAVA is off
    i = body.index("GOAVA_TRUE_SHAPES_20261102")
    seg = body[i:]
    for needle in ("1D trace", "2D phase portrait", "3D space curve", "goava_irrational_stream("):
        assert needle in seg
