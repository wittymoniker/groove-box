import os
import drive_targets as dt


def _mountinfo(tmp_path, lines):
    p = tmp_path / "mountinfo"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def _sys(tmp_path, devs):
    base = tmp_path / "sys"
    for name, removable in devs.items():
        d = base / "devices" / ("usb1" if removable else "pci0") / "block" / name.rstrip("0123456789")
        part = d / name
        part.mkdir(parents=True, exist_ok=True)
        (d / "removable").write_text("1" if removable else "0")
        cls = base / "class" / "block"
        cls.mkdir(parents=True, exist_ok=True)
        if not (cls / name).exists():
            os.symlink(part, cls / name)
    return str(base / "class" / "block")


def test_detects_usb_and_sd_skips_internal_and_readonly(tmp_path):
    usb = tmp_path / "media" / "u" / "STICK"; usb.mkdir(parents=True)
    ro = tmp_path / "media" / "u" / "ROCD"; ro.mkdir(parents=True)
    internal = tmp_path / "data"; internal.mkdir()
    sysb = _sys(tmp_path, {"sdb1": True, "sda1": False})
    info = _mountinfo(tmp_path, [
        f"1 0 8:17 / {usb} rw,nosuid - vfat /dev/sdb1 rw",
        f"2 0 8:18 / {ro} ro - iso9660 /dev/sr0 ro",
        f"3 0 8:1 / {internal} rw - ext4 /dev/sda1 rw",
        f"4 0 0:5 /tmp /run/user/1 rw - tmpfs tmpfs rw",
    ])
    # paths under tmp are not in the standard roots, so only the removable flag can accept them
    rows = dt.removable_drives(info, sysb)
    assert [r["path"] for r in rows] == [str(usb)]
    assert rows[0]["kind"] == "USB drive" and rows[0]["free"] > 0


def test_sd_card_by_name(tmp_path):
    sd = tmp_path / "SD"; sd.mkdir()
    info = _mountinfo(tmp_path, [f"1 0 179:1 / {sd} rw - exfat /dev/mmcblk0p1 rw"])
    rows = dt.removable_drives(info, str(tmp_path / "none"))
    assert rows and rows[0]["kind"] == "SD card"


def test_copy_verifies_keeps_existing_and_sanitises(tmp_path):
    drive = tmp_path / "drive"; drive.mkdir()
    (drive / "keep.txt").write_text("mine")
    src = tmp_path / "proj"; (src / "samples").mkdir(parents=True)
    (src / "a:b.MCC").write_text("{}"); (src / "samples" / "x.wav").write_bytes(b"\0" * 5000)
    rep = dt.copy_to_drive([str(src)], str(drive))
    assert not rep["failed"] and len(rep["copied"]) == 2
    assert (drive / "keep.txt").read_text() == "mine"
    assert (drive / "Groovebox" / "proj" / "a_b.MCC").is_file()
    assert (drive / "Groovebox" / "proj" / "samples" / "x.wav").stat().st_size == 5000
    assert not list(drive.rglob("*.part"))
    (src / "a:b.MCC").write_text('{"v":2}')
    dt.copy_to_drive([str(src / "a:b.MCC")], str(drive))   # replaced after verify
    assert (drive / "Groovebox" / "a_b.MCC").read_text() == '{"v":2}'


def test_copy_refuses_when_full(tmp_path, monkeypatch):
    f = tmp_path / "big.bin"; f.write_bytes(b"1" * 100)
    import shutil, collections
    DU = collections.namedtuple("DU", "total used free")
    monkeypatch.setattr(dt.shutil, "disk_usage", lambda p: DU(1000, 990, 10))
    rep = dt.copy_to_drive([str(f)], str(tmp_path))
    assert rep["failed"] and "not enough space" in rep["failed"][0][1]


def test_auto_copy_needs_setting_and_drive(tmp_path, monkeypatch):
    f = tmp_path / "p.MCC"; f.write_text("{}")
    monkeypatch.setattr(dt, "auto_copy_enabled", lambda: False)
    assert dt.auto_copy(str(f)) is False
    monkeypatch.setattr(dt, "auto_copy_enabled", lambda: True)
    monkeypatch.setattr(dt, "removable_drives", lambda *a, **k: [])
    assert dt.auto_copy(str(f)) is False
    d = tmp_path / "d"; d.mkdir()
    monkeypatch.setattr(dt, "removable_drives", lambda *a, **k: [{"path": str(d)}])
    got = []
    t = dt.copy_in_background  # real thread; wait for it
    assert dt.auto_copy(str(f), done=got.append) is True
    for _ in range(100):
        if got: break
        import time; time.sleep(0.05)
    assert got and not got[0]["failed"] and (d / "Groovebox" / "p.MCC").is_file()


def test_dialog_sidebar_support_installs():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QFileDialog
    QApplication.instance() or QApplication([])
    assert dt.install_file_dialog_support()
    # Whichever dialog layer is outermost must list the drives: drive_targets' own wrapper, or the
    # purpose-based dialog (nonmodal_dialogs) that replaces it once the app has imported it.
    name = getattr(QFileDialog.getSaveFileName, "__name__", "")
    assert name in ("save", "_get_save")
    if name == "_get_save":
        assert "removable_drives()" in open("nonmodal_dialogs.py", encoding="utf-8").read()


def test_wiring():
    g = open("groovebox.py", encoding="utf-8").read()
    for marker in ("chk_autosave", "_autosave_into_open_project", "before-autosave.MCC", "_show_drive_copy_dialog",
                   "_apply_start_project", "_proj_name", "btn_drive_copy", "install_file_dialog_support"):
        assert marker in g, marker
    assert "_open_drive_copy" in open("performance.py", encoding="utf-8").read()
