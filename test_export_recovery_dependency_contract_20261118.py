"""R104 regression coverage for power-loss recovery of staged exports."""
import json
import os
from types import SimpleNamespace

import r32_finish


def test_video_mux_persistence_does_not_require_project_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(r32_finish, "_store", lambda *parts: str(tmp_path))
    job = SimpleNamespace(id=91, project=str(tmp_path / "not-created.MCC"), kind="video_mux",
                          options={"preset": {"resume": True}}, out_file=str(tmp_path / "mix.mp4"),
                          label="final mux", depends_on=[88, 89])
    r32_finish.persist_job(job)
    meta_path = tmp_path / "91.json"
    assert meta_path.is_file()
    meta = json.loads(meta_path.read_text())
    assert meta["schema"] == 5
    assert meta["has_project"] is False
    assert meta["depends_on"] == [88, 89]
    assert not (tmp_path / "91.MCC").exists()


def test_resume_restores_dependency_edges_before_pumping(tmp_path, monkeypatch):
    monkeypatch.setattr(r32_finish, "_store", lambda *parts: str(tmp_path))
    # Two prerequisite stages and a mux stage. The mux intentionally has no MCC.
    records = [
        (10, {"schema": 4, "job_id": 10, "kind": "audio_master", "out_file": "x.mp4", "options": {}, "depends_on": []}),
        (11, {"schema": 4, "job_id": 11, "kind": "video_file", "out_file": "x.mp4", "options": {}, "depends_on": [10]}),
        (12, {"schema": 4, "job_id": 12, "kind": "video_mux", "out_file": "x.mp4", "options": {}, "depends_on": [10, 11]}),
    ]
    for old_id, meta in records:
        (tmp_path / f"{old_id}.json").write_text(json.dumps(meta))
        if meta["kind"] != "video_mux":
            (tmp_path / f"{old_id}.MCC").write_text("{}")

    class Scheduler:
        def __init__(self): self.jobs = []; self._defer_pump = False; self.pumped = False
        def submit_job(self, kind, out_file, options, label=None, project_doc=None, depends_on=None, defer_pump=False):
            j = SimpleNamespace(id=100 + len(self.jobs), kind=kind, depends_on=list(depends_on or []))
            self.jobs.append(j)
            assert defer_pump is True
            return j
        def _pump(self): self.pumped = True
    sch = Scheduler()
    app = SimpleNamespace(_export_scheduler=lambda: sch)
    assert r32_finish.resume_exports(app) == 3
    assert [j.depends_on for j in sch.jobs] == [[], [100], [100, 101]]
    assert sch.pumped is True
    assert not list(tmp_path.glob("*.json"))


def test_completed_dependency_checkpoint_is_content_verified(tmp_path, monkeypatch):
    output = tmp_path / "part.mp4"
    output.write_bytes(b"rendered-part")
    digest = r32_finish._export_file_fingerprint(str(output))
    meta = {"schema": 5, "dependency_checkpoints": [{
        "job_id": 44, "state": "done", "output_path": str(output), "output_fingerprint": digest
    }]}
    assert r32_finish._verified_dependency_checkpoint(meta, 44)
    output.write_bytes(b"corrupted-part")
    assert not r32_finish._verified_dependency_checkpoint(meta, 44)


def test_completion_updates_downstream_checkpoint_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(r32_finish, "_store", lambda *parts: str(tmp_path))
    output = tmp_path / "audio.wav"
    output.write_bytes(b"finished-audio")
    downstream = SimpleNamespace(id=92, depends_on=[91])
    (tmp_path / "92.json").write_text(json.dumps({"schema": 5, "dependency_checkpoints": [
        {"job_id": 91, "state": "queued", "output_path": str(output)}
    ]}))
    completed = SimpleNamespace(id=91, kind="audio_master", out_file=str(output), result={})
    scheduler = SimpleNamespace(jobs=[downstream])
    assert r32_finish.mark_dependency_complete(scheduler, completed) == 1
    saved = json.loads((tmp_path / "92.json").read_text())
    assert r32_finish._verified_dependency_checkpoint(saved, 91)


def test_schema5_recovery_accepts_only_verified_pruned_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr(r32_finish, "_store", lambda *parts: str(tmp_path))
    output = tmp_path / "prerequisite.bin"
    output.write_bytes(b"valid-stage")
    digest = r32_finish._export_file_fingerprint(str(output))
    meta = {"schema": 5, "job_id": 55, "kind": "video_mux", "out_file": str(tmp_path / "final.mp4"),
            "options": {}, "depends_on": [44], "dependency_checkpoints": [{
                "job_id": 44, "state": "done", "output_path": str(output), "output_fingerprint": digest
            }]}
    (tmp_path / "55.json").write_text(json.dumps(meta))

    class Scheduler:
        def __init__(self): self.jobs = []; self._defer_pump = False; self.pumped = False
        def submit_job(self, kind, out_file, options, label=None, project_doc=None, depends_on=None, defer_pump=False):
            job = SimpleNamespace(id=155, kind=kind, depends_on=list(depends_on or []))
            self.jobs.append(job); return job
        def _pump(self): self.pumped = True
    scheduler = Scheduler()
    app = SimpleNamespace(_export_scheduler=lambda: scheduler)
    assert r32_finish.resume_exports(app) == 1
    assert scheduler.jobs[0].depends_on == []

    # A changed prerequisite must hold the mux stage rather than treating it as complete.
    (tmp_path / "55.json").write_text(json.dumps(meta))
    output.write_bytes(b"changed-stage")
    scheduler2 = Scheduler()
    app2 = SimpleNamespace(_export_scheduler=lambda: scheduler2)
    assert r32_finish.resume_exports(app2) == 0
    assert not scheduler2.jobs
