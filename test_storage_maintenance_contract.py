from pathlib import Path
import json, os, tempfile, time

import groovebox_paths as gp
from nearby_groovebox import NearbyGrooveboxService, Peer, classify_destination


def test_storage_layout_cleanup_and_autosave_contract():
    with tempfile.TemporaryDirectory() as td:
        old=os.environ.get('GROOVEBOX_DATA_DIR')
        os.environ['GROOVEBOX_DATA_DIR']=td
        try:
            layout=gp.ensure_app_layout()
            for rel in ('projects','samples','games','modules','exports/audio','cache','temp','logs','state','Nearby Grooveboxes/Inbox'):
                assert Path(layout[rel]).is_dir()
            project=Path(gp.default_project_path('Recovery Demo'))
            project.parent.mkdir(parents=True,exist_ok=True)
            project.write_text(json.dumps({'project_title':'Recovery Demo','project_notes':'saved state'}),encoding='utf-8')
            autos=project.parent/'metadata'/'autosave.MCC'
            autos.write_text(json.dumps({'project_title':'Recovery Demo','project_path':str(project),'project_notes':'working notes','seed':'123'}),encoding='utf-8')
            completed=project.parent/'recordings'/'take.wav'; completed.write_bytes(b'complete')
            scratch=project.parent/'recordings'/'take.wav.part'; scratch.write_bytes(b'scratch')
            export=project.parent/'exports'/'audio'/'mix.wav'; export.write_bytes(b'export')
            (Path(gp.cache_dir())/'thumb.bin').write_bytes(b'cache')
            (Path(gp.logs_dir())/'run.log').write_bytes(b'log')
            report=gp.storage_report()
            assert report['autosaves']['files'] == 1
            row=report['autosaves']['items'][0]
            assert row['title']=='Recovery Demo' and row['notes']=='working notes'
            cleaned=gp.cleanup_disposable(('cache','temp','logs','recording_scratch'))
            assert cleaned['files'] >= 3
            assert completed.is_file() and export.is_file() and autos.is_file() and project.is_file()
            assert not scratch.exists()
            assert gp.delete_autosave(str(autos)) is True and not autos.exists()
        finally:
            if old is None: os.environ.pop('GROOVEBOX_DATA_DIR',None)
            else: os.environ['GROOVEBOX_DATA_DIR']=old


def test_unused_media_is_detect_only_then_explicit_delete():
    with tempfile.TemporaryDirectory() as td:
        old=os.environ.get('GROOVEBOX_DATA_DIR'); os.environ['GROOVEBOX_DATA_DIR']=td
        try:
            project=Path(gp.default_project_path('Media Demo'))
            root=project.parent
            used=root/'samples'/'imports'/'used.wav'; used.write_bytes(b'u')
            unused=root/'samples'/'imports'/'unused.wav'; unused.write_bytes(b'x')
            project.write_text(json.dumps({'project_title':'Media Demo','instrument_media_samples':{'I1':{'path':str(used)}}}),encoding='utf-8')
            rows=gp.find_unreferenced_project_media(str(project))
            paths={Path(r['path']).name for r in rows}
            assert 'unused.wav' in paths and 'used.wav' not in paths
            assert unused.exists(), 'scan must never delete'
            result=gp.delete_unreferenced_project_media(rows,str(project))
            assert result['files']==1 and not unused.exists() and used.exists()
        finally:
            if old is None: os.environ.pop('GROOVEBOX_DATA_DIR',None)
            else: os.environ['GROOVEBOX_DATA_DIR']=old


def test_known_groovebox_history_is_bounded_separate_and_resettable():
    with tempfile.TemporaryDirectory() as td:
        svc=NearbyGrooveboxService(td)
        p=Peer('peer-1','Studio Groovebox','10.0.0.8',8784,'http://10.0.0.8:8784','Linux','v1',time.time(),'cat')
        svc._remember_peer(p); svc._flush_history(True)
        assert svc.history_path.is_file()
        assert svc.history_list()[0]['name']=='Studio Groovebox'
        inbox=Path(svc.roots['inbox'])/'keep.wav'; inbox.write_bytes(b'keep')
        svc2=NearbyGrooveboxService(td)
        assert svc2.history_list()[0]['node_id']=='peer-1'
        assert svc2.reset_history()==1
        assert inbox.exists(), 'history reset must never touch received files'
        assert classify_destination('set.MCC')=='projects'
        assert classify_destination('archive.MEUM')=='projects'
