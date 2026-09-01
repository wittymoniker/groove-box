import importlib.util, tempfile, shutil, sys
import numpy as np
from videogame_engine import classify_from_composition, export_game_files

def main():
    root=tempfile.mkdtemp(prefix='open_world_')
    try:
        meta={'seed':42.0,'bpm':120,'seq_length':32,'playlist_rows':32,'n_instruments':48,'goava_active':False,'randomizer_active':False,'phase_lock_active':False}
        ident=classify_from_composition(**meta); script=export_game_files(ident,root,meta)
        spec=importlib.util.spec_from_file_location('gw',script); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        g=mod.Game(); a0=g.angle; v0=dict(g.visual_view)
        for _ in range(120): g.tick(1/30)
        assert abs(((g.angle-a0+3.141592653589793)%6.283185307179586)-3.141592653589793) < 1e-6, 'world moved without player input'
        assert abs(g.visual_view['roll_deg']) < 1e-9, 'sandbox camera rolled itself'
        g.perspective_move(dz=1.0)
        for _ in range(10): g.tick(1/30)
        assert abs(((g.angle-a0+3.141592653589793)%6.283185307179586)-3.141592653589793) > 1e-4, 'player input failed to move'
        obj=g.sandbox_place('crate','test crate'); assert obj['label']=='test crate'
        reg=g.sandbox_region(); assert reg['objects']
        g.sandbox_remove(-1); assert not reg['objects']
        g.handle_console_command('/note hello sandbox'); assert g.region_state
        g.handle_console_command('/report'); assert g.report()['sandbox']['enabled']
        g.net.shutdown(); print('PASS: free-roam idle stability'); print('PASS: player-authored movement'); print('PASS: region sandbox place/remove/note'); print('PASS: sandbox report')
    finally: shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__': main()
