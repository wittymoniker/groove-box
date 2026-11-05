from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parent

def test_multitrack_clip_studio_has_arbitrary_regions_and_layers():
    src=(ROOT/'clip_timeline_studio.py').read_text()
    for token in ('Timeline start (s)','Source in (s)','Source out (s)','Track / layer','Gain (dB)','Opacity','overlay=','amix=inputs=','Save timeline','Load timeline'):
        assert token in src, token
    ast.parse(src)

def test_multitrack_clip_studio_is_lazy_and_iso_overlay_synced():
    ui=(ROOT/'video_clip_studio.py').read_text()
    assert 'Open Multitrack Clip Studio' in ui
    assert 'from clip_timeline_studio import ClipTimelineStudio' in ui
    overlay=ROOT/'BUILD_ISO'/'app-overlay-v35.22zz'
    assert (overlay/'video_clip_studio.py').read_bytes()==(ROOT/'video_clip_studio.py').read_bytes()
    assert (overlay/'clip_timeline_studio.py').read_bytes()==(ROOT/'clip_timeline_studio.py').read_bytes()
