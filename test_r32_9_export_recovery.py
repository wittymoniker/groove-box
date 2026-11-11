"""R32.9: memory-bounded video assembly and SIGKILL recovery contracts."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def test_final_video_stitch_isolated_from_warm_part_workers():
    src = (ROOT / "export_scheduler.py").read_text(encoding="utf-8")
    assert "def _is_video_stitch_job(job, jobs):" in src
    assert "def _retire_idle_workers_for_stitch(self):" in src
    assert "if any(w.job is not None for w in self.workers):" in src
    assert "self._retire_idle_workers_for_stitch()" in src
    # A dead worker remains accounted for until QProcess reports its exit, so
    # a fresh stitch process is not spawned while its RSS is still resident.
    kill = src.split("def _kill_worker(self, w):", 1)[1].split("def _pump(self):", 1)[0]
    assert "return  # _worker_exited removes it" in kill


def test_sigkill_video_jobs_retry_from_recoverable_parts():
    src = (ROOT / "export_scheduler.py").read_text(encoding="utf-8")
    block = src.split("def _worker_exited(self, w):", 1)[1].split("def _finish(self, job, ok):", 1)[0]
    assert 'exit_code == 9' in block
    assert 'retries < 2' in block
    assert 'job.state = QUEUED' in block
    assert 'job.result.pop("fail", None)' in block
    assert 'restarting from saved render artifacts' in block


def test_video_export_releases_full_song_buffers_before_final_mux():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    audio_stage = src.split("# R32.10: audio is staged before video", 1)[1].split("_only_parts = None", 1)[0]
    assert "del pcm" in audio_stage and "del audio_clip" in audio_stage
    assert "_gc_export.collect(1)" in audio_stage
    # The read-only mmap master is intentionally retained while missing video
    # parts render, then released before concat/mux/probe to keep peak RSS bounded.
    release = src.index("del master", src.index("# Frames and soundtrack are now materialized on disk"))
    concat = src.index("# Build concat list", release)
    assert release < concat
    assert "master_rms" in src[release:]


def test_final_video_mux_has_bounded_fallback_and_staged_validation():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert '"-threads", "1", *pix' in src
    assert '"-preset", "ultrafast"' in src
    assert "ffprobe" in src and "codec_type=video" in src
    assert 'os.replace(final_tmp, out_path)' in src
    assert "recoverable .part segments were kept" in src


def test_memory_budget_uses_effective_cgroup_ceiling():
    import memory_guard
    import process_planner
    import resource_governor
    old = memory_guard.snapshot
    try:
        memory_guard.snapshot = lambda force=False: {
            "available": 2 * 1024**3, "total": 4 * 1024**3,
            "reserve": 384 * 1024**2, "usable": 2 * 1024**3 - 384 * 1024**2,
        }
        assert resource_governor.total_mb() == 4096
        assert resource_governor.available_mb() == 2048
        old_affinity = getattr(os, "sched_getaffinity", None)
        if old_affinity:
            os.sched_getaffinity = lambda _pid: set(range(8))
        cores, free_gb = process_planner.capacity()
        assert cores == 7 and free_gb == 1  # 2 GiB free => one 1.5-GiB worker slot
    finally:
        memory_guard.snapshot = old
        if 'old_affinity' in locals() and old_affinity:
            os.sched_getaffinity = old_affinity


def test_iso_overlay_matches_changed_runtime_sources():
    overlay = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz"
    for name in ("groovebox.py", "export_scheduler.py", "process_planner.py", "resource_governor.py"):
        assert (overlay / name).read_bytes() == (ROOT / name).read_bytes(), name
