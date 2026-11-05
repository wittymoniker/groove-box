def test_notes_button_wiring():
    s = open("performance.py", encoding="utf-8").read()
    assert "btn_notes_diary" in s and "_open_notes_tab" in s and "_perf_right_tabs = right" in s
