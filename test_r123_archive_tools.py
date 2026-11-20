"""R123: File Manager archiving — .zip / .tar.gz / .7z / .MCC compress + safe extract."""
import io
import os
import tarfile
import time
import zipfile

import pytest

import archive_tools as at


def _tree(tmp_path):
    src = tmp_path / "Album"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("alpha")
    (src / "sub" / "b.bin").write_bytes(bytes(range(256)) * 16)
    return src


@pytest.mark.parametrize("fmt", ["zip", "tar.gz", "mcc", "7z"])
def test_round_trip(tmp_path, fmt):
    if fmt == "7z" and not at.seven_zip_available():
        with pytest.raises(at.ArchiveError, match="7zip|7-Zip"):
            at.create_archive([str(_tree(tmp_path))], str(tmp_path / "p"), fmt)
        return
    src = _tree(tmp_path)
    out = at.create_archive([str(src)], str(tmp_path / "out" / "pack"), fmt)
    assert out.endswith(at.SUFFIX[fmt]) and not os.path.exists(out + ".part")
    assert at.detect_format(out) == ("tar" if fmt == "tar.gz" else fmt)
    got = at.extract_archive(out, str(tmp_path / "x"))
    assert (tmp_path / "x" / "Album" / "sub" / "b.bin").read_bytes() == (src / "sub" / "b.bin").read_bytes()
    assert got == str((tmp_path / "x").resolve())


def test_extraction_is_confined(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../evil.txt", "x")
    with pytest.raises(at.ArchiveError, match="outside"):
        at.extract_archive(str(z), str(tmp_path / "d"))
    assert not (tmp_path / "evil.txt").exists()
    t = tmp_path / "evil.tar.gz"
    with tarfile.open(t, "w:gz") as f:
        i = tarfile.TarInfo("link"); i.type = tarfile.SYMTYPE; i.linkname = "/etc"; f.addfile(i)
        i = tarfile.TarInfo("ok.txt"); i.size = 2; f.addfile(i, io.BytesIO(b"hi"))
    out = at.extract_archive(str(t), str(tmp_path / "e"))
    assert sorted(os.listdir(out)) == ["ok.txt"]


def test_project_mcc_is_not_an_archive(tmp_path):
    p = tmp_path / "song.MCC"
    p.write_text('{"bpm": 120}')
    assert at.detect_format(str(p)) == "mcc-project" and not at.is_archive(str(p))
    with pytest.raises(at.ArchiveError, match="Open Project"):
        at.extract_archive(str(p))


def test_default_extract_dir_never_overwrites(tmp_path):
    (tmp_path / "Album").mkdir()
    assert at.default_extract_dir(str(tmp_path / "Album.tar.gz")).endswith("Album (2)")


def test_file_manager_buttons(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QInputDialog, QFileDialog
    app = QApplication.instance() or QApplication([])
    import performance as perf
    src = _tree(tmp_path)
    dlg = perf.FileManagerDialog(None, str(tmp_path))
    try:
        assert dlg.btn_compress.text().startswith("🗜") and dlg.btn_extract.text().startswith("📂")
        monkeypatch.setattr(dlg, "_selected_paths", lambda: [str(src)])
        monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (at.FORMAT_LABELS["zip"], True)))
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "Album.zip"), "")))
        dlg._compress_selected()
        end = time.monotonic() + 20
        while getattr(dlg, "_archive_busy", False) and time.monotonic() < end:
            app.processEvents(); time.sleep(0.02)
        assert (tmp_path / "Album.zip").is_file(), dlg.lbl_status.text()
        assert "done" in dlg.lbl_status.text()
        monkeypatch.setattr(dlg, "_selected_paths", lambda: [str(tmp_path / "Album.zip")])
        dlg._extract_selected()
        end = time.monotonic() + 20
        while getattr(dlg, "_archive_busy", False) and time.monotonic() < end:
            app.processEvents(); time.sleep(0.02)
        assert (tmp_path / "Album (2)" / "Album" / "a.txt").read_text() == "alpha", dlg.lbl_status.text()
    finally:
        dlg.close()
