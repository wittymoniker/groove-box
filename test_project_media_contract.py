#!/usr/bin/env python3
from pathlib import Path
import os, tempfile
import groovebox_paths as gp
from groovebox_media_tools import local_bin_dirs

with tempfile.TemporaryDirectory() as td:
    os.environ['GROOVEBOX_DATA_DIR']=td
    chosen=Path(td)/'projects'/'My Album.MCC'
    canon=Path(gp.canonical_project_path(str(chosen)))
    assert canon.parent.name=='My Album' and canon.name=='My Album.MCC'
    root=Path(gp.project_root(str(canon)))
    required=['samples/imports','samples/global','samples/operators','recordings','layers','exports/audio','exports/video','exports/frames','games','metadata']
    assert all((root/r).is_dir() for r in required)
    assert Path(gp.renders_dir(str(canon))).parent==root
    src=Path(td)/'tone.wav'; src.write_bytes(b'RIFFfake')
    ing=Path(gp.ingest_file(str(src),'operator_sample',str(canon)))
    assert ing.parent==root/'samples'/'operators'
    gp.index_file(str(ing),'operator_sample',str(canon))
    assert (root/'metadata'/'project_index.json').is_file()
print('PASS project-local paths + media index contract')
