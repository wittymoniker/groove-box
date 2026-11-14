"""GROOVEBOX_DRIVE_UPDATE_DISC_20261112: update-from-drive, rollback, ISO plans, burn guards."""
import os
import shutil
import zipfile
from pathlib import Path

import pytest

import disc_burn
import self_update as su


def _tree(root: Path, version: str, extra: str = "") -> Path:
    root.mkdir(parents=True)
    for m in su.MARKERS:
        (root / m).write_text("X = 1\n", encoding="utf-8")
    (root / "CURRENT-RELEASE.txt").write_text(version + "\n", encoding="utf-8")
    if extra:
        (root / "new_mod.py").write_text(extra, encoding="utf-8")
    return root


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GROOVEBOX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(su, "removable_roots", lambda: [])
    monkeypatch.setattr(su, "CORE_IMPORTS", ("compat_settings",))
    app = _tree(tmp_path / "app", "R1")
    drive = tmp_path / "drive"
    _tree(drive / "MATH_GROOVEBOX-v3", "R2", extra="Y = 2\n")
    return app, drive


def test_find_stage_apply_rollback(env):
    app, drive = env
    found = su.find_update_sources([str(drive)])
    assert [f["kind"] for f in found] == ["tree"] and found[0]["version"] == "R2"
    r = su.update_from(found[0], native=False, app_root=app)
    assert r["ok"] and (app / "new_mod.py").is_file()
    assert (app / "CURRENT-RELEASE.txt").read_text().strip() == "R2"
    rb = su.rollback(app_root=app)
    assert rb["version"] == "R1" and not (app / "new_mod.py").exists()
    assert (app / "CURRENT-RELEASE.txt").read_text().strip() == "R1"
    assert not list(su.updates_dir().glob("staging-*"))


def test_broken_update_never_touches_app(env):
    app, drive = env
    (drive / "MATH_GROOVEBOX-v3" / "compat_settings.py").write_text("def broken(:\n", encoding="utf-8")
    r = su.update_from(str(drive / "MATH_GROOVEBOX-v3"), native=False, app_root=app)
    assert r["ok"] is False and r["stage"] == "verify"
    assert (app / "CURRENT-RELEASE.txt").read_text().strip() == "R1"


def test_zip_traversal_and_symlinks_are_ignored(env, tmp_path):
    app, drive = env
    z = drive / "MATH_GROOVEBOX-evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../../escape.txt", "x")
        zf.writestr("/abs.txt", "x")
        for m in su.MARKERS:
            zf.writestr("pkg/" + m, "X = 1\n")
    root = su.stage(str(z))
    assert (root / "groovebox.py").is_file()
    assert not (tmp_path / "escape.txt").exists()
    shutil.rmtree(root.parents[1], ignore_errors=True)


def test_own_tree_is_never_offered(env):
    found = su.find_update_sources([str(su.APP_ROOT.parent)], depth=1)
    assert all(os.path.realpath(f["path"]) != os.path.realpath(su.APP_ROOT) for f in found)


def test_burn_refuses_non_optical_and_plans_argv(tmp_path):
    iso = tmp_path / "x.iso"; iso.write_bytes(b"\0" * 4096)
    with pytest.raises(PermissionError):
        disc_burn.burn(str(iso), "/dev/sda", verify=False)
    assert disc_burn.plan_burn(str(iso), "/dev/sr0", "xorriso")[:4] == ["xorriso", "-as", "cdrecord", "-v"]
    assert disc_burn.plan_burn(str(iso), "/dev/sr0", "growisofs")[-1] == f"/dev/sr0={iso}"


@pytest.mark.skipif(disc_burn.iso_tool() is None, reason="no xorriso/genisoimage")
def test_source_iso_builds(env, tmp_path):
    app, _ = env
    r = disc_burn.build_source_iso(root=app, media="CD 700 MB", include_bootable=False, out=str(tmp_path / "s.iso"))
    assert r["ok"] and r["fits"] and os.path.getsize(r["iso"]) > 0
