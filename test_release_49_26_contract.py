"""R49-26 release integration contracts."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BI = ROOT / "BUILD_ISO"


def test_direct_limine_secure_boot_contract():
    p = subprocess.run([sys.executable, str(BI / "verify_secure_boot_contract_r49_26.py")],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "17 Secure Boot contract checks" in p.stdout


def test_dell_and_acer_profiles_are_staged():
    profiles = BI / "hardware-profiles"
    for name in ("dell-latitude-3510-32gb.json", "acer-nitro-5-generic.json"):
        data = json.loads((profiles / name).read_text())
        assert data["schema"] == 1
        assert data["runtime_policy"]["mode"] == "detect-at-boot"


def test_active_overlay_matches_runtime_source():
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_runtime_payload.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_historical_overlay_python_compiles():
    files = []
    for overlay in sorted(BI.glob("app-overlay-*")):
        files.extend(overlay.rglob("*.py"))
    for source in files:
        if "__pycache__" in source.parts:
            continue
        compile(source.read_text(encoding="utf-8"), str(source), "exec")
