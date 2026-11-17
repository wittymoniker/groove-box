"""R80 shared-buffer, GOAVA responsiveness and export-stage cache contracts."""
from pathlib import Path
import os
import tempfile
import numpy as np
import export_stage_cache

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "groovebox.py").read_text(encoding="utf-8")
WORKER = (ROOT / "export_worker.py").read_text(encoding="utf-8")


def test_goava_toggle_forces_existing_time_sliced_canonical_commit():
    toggle = SRC.split("def _on_goava_toggled(self, checked):", 1)[1].split("def _finish_goava_toggle", 1)[0]
    flush = SRC.split("def _flush_live_source_update(self):", 1)[1].split("def _ui_after_canonical_write", 1)[0]
    assert "_goava_force_cooperative_commit = True" in toggle
    assert "_force_cooperative" in flush
    assert "CanonicalCommit(self)" in flush
    assert "job.start()" in flush
    assert "for start in range(0, rows, chunk)" in (ROOT / "canonical_cooperative_kernels.py").read_text(encoding="utf-8")
    assert "reset_ledger=(start == 0)" in (ROOT / "canonical_cooperative_kernels.py").read_text(encoding="utf-8")


def test_authoritative_mixdown_is_published_for_other_consumers():
    assert "publish_shared_buffer(key, ent[0]" in SRC
    assert "publish_shared_buffer(key, buf" in SRC


def test_export_worker_uses_cached_audio_master_stage():
    assert "export_stage_cache" in WORKER
    assert "reused cached master audio" in WORKER
    assert "_esc.store(cache_key, audio_path, master_rms)" in WORKER


def test_export_stage_cache_key_tracks_pcm_project_and_options():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "project.MCC"
        project.write_bytes(b"frozen project")
        pcm = np.arange(4096, dtype=np.float32)
        a = export_stage_cache.key_for_buffer(pcm, 48000, str(project), {"depth": 24})
        b = export_stage_cache.key_for_buffer(pcm, 48000, str(project), {"depth": 16})
        assert a != b
        project.write_bytes(b"changed project")
        c = export_stage_cache.key_for_buffer(pcm, 48000, str(project), {"depth": 24})
        assert a != c


def test_export_stage_cache_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        os.environ["XDG_CACHE_HOME"] = td
        src = Path(td) / "source.wav"
        dst = Path(td) / "out.wav"
        src.write_bytes(b"RIFF-test-audio")
        key = "a" * 64
        export_stage_cache.store(key, str(src), 0.125)
        entry = export_stage_cache.lookup(key)
        assert entry and entry[1] == 0.125
        assert export_stage_cache.copy_cached(entry, str(dst))
        assert dst.read_bytes() == src.read_bytes()
