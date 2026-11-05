import importlib.util, os, shutil, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from videogame_engine import classify_from_composition, export_game_files


def test_fps_readout_only_in_escape_menu():
    from PyQt6.QtWidgets import QApplication
    qa = QApplication.instance() or QApplication([])
    root = tempfile.mkdtemp(prefix="gb_fps_"); sys.path.insert(0, root)
    try:
        meta = {"seed": 42.0, "bpm": 120, "seq_length": 16, "playlist_rows": 8, "n_instruments": 8,
                "goava_active": False, "randomizer_active": False, "phase_lock_active": False}
        script = export_game_files(classify_from_composition(**meta), root, meta)
        spec = importlib.util.spec_from_file_location("gb_fps_game", script)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        game = mod.Game()
        view = mod.SceneViewport(game); view.resize(320, 200)
        assert view.fps_text() == "FPS: measuring…"
        for _ in range(4):
            view.grab(); qa.processEvents()
        assert view.fps_text().startswith("FPS ") or view.fps_text() == "FPS: measuring…"
        view._fps_stats["ema_dt"] = 1 / 50.0; view._fps_stats["ema_paint"] = 0.004; view._fps_stats["dts"] = [0.02]; view._fps_stats["worst"] = 0.02
        assert "FPS 50.0" in view.fps_text()
        game.menu_open = True; view.grab()                      # menu paints without error
        game.menu_open = False
        game.net.shutdown()
    finally:
        shutil.rmtree(root, ignore_errors=True)
