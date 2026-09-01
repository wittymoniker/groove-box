"""Generated-game runtime smoke test."""
from __future__ import annotations
import importlib.util
import shutil
import sys
import tempfile
import numpy as np
from videogame_engine import classify_from_composition, export_game_files

def main():
    root = tempfile.mkdtemp(prefix="groovebox_game_smoke_")
    sys.path.insert(0, root)
    try:
        meta={"seed":42.0,"bpm":120,"seq_length":32,"playlist_rows":32,"n_instruments":48,
              "goava_active":False,"randomizer_active":False,"phase_lock_active":False}
        ident=classify_from_composition(**meta)
        script=export_game_files(ident,root,meta)
        spec=importlib.util.spec_from_file_location("generated_game_smoke",script)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        game=mod.Game(); report=game.report()
        assert isinstance(report["arcade"],dict)
        assert all(v is None or isinstance(v,dict) for k,v in report["arcade"].items() if k != "active")
        game.tick(1/30); frame=np.asarray(game.render_instant_frame(64,36)); assert frame.shape==(36,64,3); game.net.shutdown()
        bed=mod.MusicBed(42); audio=np.asarray([bed.step(1/22050) for _ in range(22050)])
        assert np.max(np.abs(audio))<=1.0 and np.sqrt(np.mean(audio*audio))<0.75
        sfx=mod.LiveSFX(42,["collect","kill","portal","quest"]); sfx.trigger("collect"); burst=np.asarray(sfx.mix(5000))
        assert np.max(np.abs(burst))>0.01
        print("PASS: safe inactive-arcade report")
        print("PASS: player tick + video frame")
        print("PASS: MusicBed dynamic headroom")
        print("PASS: LiveSFX audible burst")
    finally:
        shutil.rmtree(root,ignore_errors=True)
if __name__=="__main__": main()
