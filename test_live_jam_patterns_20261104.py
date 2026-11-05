import time
from live_jam import LiveJamController


def test_recorded_note_and_bend_share_pattern_envelope():
    jam = LiveJamController(seed=123)
    jam.start()
    jam.begin_performance_recording()
    jam.record_performance_event("pitch_bend", semitones=5)
    time.sleep(0.01)
    jam.record_performance_event("jam_note", key="A", degree=2, semitones=5,
                                 sample_binding={"sample": "bank-a"})
    take = jam.finish_performance_recording()
    saved = jam.save_pattern("test", take)
    pattern = jam.snapshot()["pattern_bank"]["test"]
    assert saved["entries"] == 2
    assert pattern["duration"] == take["duration"]
    assert [e["kind"] for e in pattern["events"]] == ["pitch_bend", "jam_note"]
    assert pattern["events"][1]["semitones"] == 5


def test_pattern_macro_assignment_round_trip():
    jam = LiveJamController()
    jam.pattern_bank["riff"] = {"duration": 0.5, "events": []}
    jam.assign_pattern_macro("F3", "riff")
    state = jam.snapshot()
    restored = LiveJamController()
    restored.load_snapshot(state)
    assert restored.pattern_for_macro("F3") == "riff"
