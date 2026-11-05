from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "groovebox.py").read_text(encoding="utf-8")
OVERLAY = (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py").read_text(encoding="utf-8")


def test_semantic_flow_palette_is_explicit_and_stable():
    expected = {
        "#5aa9ff": "selection / input / data source",
        "#3bd18a": "synthesis / mathematical transformation",
        "#d4af37": "vector blend / weighted aggregation",
        "#e05252": "global routing / shared-state influence",
        "#f1ce68": "transport / playback",
        "#c58cff": "render / export / artifact creation",
    }
    for color, meaning in expected.items():
        assert color in SOURCE
        assert meaning in SOURCE


def test_workflow_steps_use_semantic_stage_labels():
    for label in ("INPUT", "TRANSFORM", "VECTOR", "BLEND", "ROUTE", "TRANSPORT", "RENDER"):
        assert label in SOURCE
    assert "Blue=input/selection" in SOURCE
    assert "purple=render/export" in SOURCE


def test_active_iso_overlay_matches_root_source():
    assert SOURCE == OVERLAY


def test_execution_fabric_map_documents_real_time_boundaries():
    doc = (ROOT / "EXECUTION_FABRIC_MAP_R29F.md").read_text(encoding="utf-8")
    for term in ("AudioRingBuffer", "VideoFrameQueue", "ConcurrentAudioBus", "SharedWorkLane", "Qt", "typed graph"):
        assert term in doc
