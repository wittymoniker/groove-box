from mcc_filetype import ensure_project_extension, is_project_path, project_argument

def test_extensions():
    assert ensure_project_extension('song') == 'song.MCC'
    assert ensure_project_extension('song.MCC') == 'song.MCC'
    assert ensure_project_extension('song.mcc') == 'song.mcc'
    assert ensure_project_extension('song.mgpr') == 'song.MCC'
    assert ensure_project_extension('song.mgpr.part') == 'song.MCC'
    assert is_project_path('song.MCC')
    assert is_project_path('old.mgpr')
    assert project_argument(['--foo', 'x.MCC']).endswith('x.MCC')
