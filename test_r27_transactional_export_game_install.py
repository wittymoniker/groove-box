#!/usr/bin/env python3
"""R27.0.0 regression checks for transactional video exports and WAV asset installs."""
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parent
video=(ROOT/'video_clip_studio.py').read_text()
overlay=(ROOT/'BUILD_ISO/app-overlay-v35.22zz/video_clip_studio.py').read_text()
game=(ROOT/'videogame_engine.py').read_text()
checks={
 'root and ISO overlay stay in sync': video == overlay,
 'render uses suffix-preserving partial path': "publish=out[:-len(ext)]+'.part'+ext" in video,
 'render validates duration before publication': "_probe_duration(publish)<=0" in video,
 'render validates audio when audio inputs are present': "if audio_refs and not _probe_has_audio(publish)" in video,
 'render atomically publishes completed output': 'os.replace(publish,out)' in video,
 'render removes stale partial output on failure': 'if os.path.isfile(stale): os.remove(stale)' in video,
 'WAV assets are written to a temporary file first': 'prefix=".wav-install-"' in game,
 'WAV assets are validated before atomic publication': 'check.getnframes() < 1' in game and 'os.replace(tmp, path)' in game,
 'game install logs asset errors instead of silently ignoring': '[SIM] asset install failed for' in game,
 'WAV asset generation is isolated from the GUI thread': 'GrooveboxGameAssetInstall' in game and '_install_events.get_nowait()' in game and 'QApplication.processEvents()' in game,
}
for name,ok in checks.items(): print(('PASS: ' if ok else 'FAIL: ')+name)
if not all(checks.values()): raise SystemExit(1)
print('PASS: R27.0.0 export/install static regression contracts')
