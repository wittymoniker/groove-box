from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_audio_export_has_frozen_snapshot_and_dedicated_single_worker_lane():
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    assert "GROOVEBOX_V35_22ZZ_R28_4_2_CANONICAL_ASYNC_AUDIO_EXPORT_20261017 = True" in source
    assert "class _AudioExportSnapshot:" in source
    assert "@dataclass(frozen=True)" in source
    assert "class _AudioExportTask(QRunnable):" in source
    assert "self._audio_export_pool = QThreadPool(self)" in source
    assert "self._audio_export_pool.setMaxThreadCount(1)" in source
    assert "self._audio_export_pool.start(_AudioExportTask(snapshot, self._write_audio_parts_and_final, signals))" in source


def test_export_worker_does_not_touch_qt_widgets_or_project_index():
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    task = source[source.index("class _AudioExportTask(QRunnable):"):source.index("class VideoSynthViewer(QFrame):")]
    assert "self.writer(" in task
    assert "worker_safe=True" in task
    assert "self.scope_status_label" not in task
    writer = source[source.index("    def _write_audio_parts_and_final("):source.index("    def _on_audio_export_progress(")]
    assert "if not worker_safe:" in writer
    assert "if progress_callback is not None:" in writer
    assert "if not worker_safe:\n            self._index_project_file(file_path, \"audio_export\")" in writer


def test_export_snapshot_is_private_readonly_and_worker_completion_is_main_thread_bound():
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    export = source[source.index("    def export_mixdown_dialog(self, audio_format=\"wav\"):"):source.index("    # =====================================================================\n    # VIDEO_EXPORT_FEATURE", source.index("    def export_mixdown_dialog(self, audio_format=\"wav\"):"))]
    assert "frozen_master.setflags(write=False)" in export
    assert "preview.setflags(write=False)" in export
    assert "signals.finished.connect(self._on_audio_export_finished)" in export
    assert "signals.failed.connect(self._on_audio_export_failed)" in export
    assert "self._audio_export_active = True" in export


def test_shutdown_cannot_destroy_owner_while_export_worker_is_active():
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    i = source.index("    def closeEvent(self, event):", source.index("class MathematiciansGrooveboxApp"))
    frag = source[i:i+1800]
    assert "if getattr(self, \"_audio_export_active\", False):" in frag
    assert "event.ignore()" in frag
    assert "pool.waitForDone(15000)" in source


def test_overlay_exactly_matches_root_after_canonical_worker_update():
    assert (ROOT / "groovebox.py").read_bytes() == (ROOT / "BUILD_ISO/app-overlay-v35.22zz/groovebox.py").read_bytes()


def test_export_worker_has_cancellable_progress_and_atomic_final_publication():
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    assert "class _AudioExportSnapshot:" in source and "cancel_event: object" in source
    assert "def _cancel_audio_export(self, token):" in source
    assert "progress_dialog.canceled.connect(lambda _token=token: self._cancel_audio_export(_token))" in source
    writer = source[source.index("    def _write_audio_parts_and_final("):source.index("    def _on_audio_export_progress(")]
    assert "cancel_event.is_set()" in writer
    assert "subprocess.Popen(" in writer
    assert "os.replace(candidate_path, file_path)" in writer
    assert '"CANCELLED: Audio export cancelled during encoding' in writer


def test_widget_free_hardclip_snapshot_keeps_canonical_volume_drive_equation():
    import ast
    import numpy as np
    source = (ROOT / "groovebox.py").read_text(errors="replace")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_master_hardclip_snapshot")
    namespace = {"np": np, "_GB_ACCEL_FUNCS": {}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "groovebox.py"), "exec"), namespace)
    x = np.asarray([-2.0, -0.5, 0.0, 0.5, 2.0], dtype=np.float32)
    y, report = namespace["_master_hardclip_snapshot"](x, 50.0, 0.5)
    expected = np.clip(x * np.float32(0.5 * 1.75), -1.0, 1.0).astype(np.float32)
    assert np.array_equal(y, expected)
    assert report["drive"] == 1.75 and report["vol"] == 0.5
    assert report["peak"] == 1.0
