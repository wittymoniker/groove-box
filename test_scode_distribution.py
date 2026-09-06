from pathlib import Path
import json, tempfile, subprocess, hashlib, zipfile
def test_channels_exist():
    for n in ("stable","beta","nightly"):
        d=json.loads(Path("distribution/channels",n+".json").read_text())
        assert d["channel"]==n
        assert "sha256" in d and "artifact_url" in d
def test_release_workflow_has_attestation():
    s=Path("distribution/github/workflows/release.yml").read_text()
    assert "attest-build-provenance" in s
    assert "id-token: write" in s
def test_selfbuild_is_nonpropagating():
    s=Path("scode_selfbuild.py").read_text()
    assert "socket" not in s
    assert "ssh" not in s
    assert "rglob" in s
