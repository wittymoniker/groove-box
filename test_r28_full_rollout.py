from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parent

def test_webm_audio_encoder_and_live_export_ui_contract():
    src=(ROOT/'video_clip_studio.py').read_text()
    assert "_audio_encoder_for(ff, ext)" in src
    assert "QApplication.processEvents()" in src
    assert 'GrooveboxVideoFrameBuffer' in src and '_render_frame_snapshot' in src
    assert "subprocess.Popen(cmd" in src and "proc.poll()" in src
    assert "_probe_has_audio(publish)" in src
    assert "_cleanup_stale_render_parts" in src

def test_game_wav_install_runs_off_gui_thread():
    src=(ROOT/'videogame_engine.py').read_text()
    assert 'GrooveboxGameAssetInstall' in src
    assert '_install_events.get_nowait()' in src
    assert 'install_game(IDENTITY, root_dir=_sim_dir, progress=_install_progress)' in src

def test_removable_inventory_supports_partitioned_and_bootable_media():
    src=(ROOT/'removable_media_inventory.py').read_text()
    for token in ('mmcblk\\d+p\\d+','PARTFLAGS','PARTTYPE','bootable','mountpoints','no-filesystem'):
        assert token in src
    tree=ast.parse(src)
    assert any(isinstance(n,ast.FunctionDef) and n.name=='inventory' for n in tree.body)

def test_root_and_iso_overlay_sources_are_identical():
    for name in ('video_clip_studio.py','videogame_engine.py','media_output_router.py','performance.py','groovebox.py'):
        a=ROOT/name; b=ROOT/'BUILD_ISO'/'app-overlay-v35.22zz'/name
        if a.exists() and b.exists(): assert a.read_bytes()==b.read_bytes(), name
