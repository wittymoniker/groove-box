import os
SRC = os.path.dirname(os.path.abspath(__file__))


def test_worker_and_export_take_a_settings_snapshot():
    w = open(os.path.join(SRC, "export_worker.py"), encoding="utf-8").read()
    assert w.index("_snapshot_render_inputs()") < w.index("_get_shared_mixdown_buffer(")
    g = open(os.path.join(SRC, "groovebox.py"), encoding="utf-8").read()
    i = g.index("EXPORT_SNAPSHOT_20261102")
    assert "self._snapshot_render_inputs()" in g[i:i + 700]
