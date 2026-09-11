from pathlib import Path
import re

SRC = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")
HELP = Path(__file__).with_name("HELP_TEXT.md").read_text(encoding="utf-8")


def test_authoritative_default_constants():
    assert re.search(r"^DEFAULT_SEQUENCE_LENGTH\s*=\s*12\s*$", SRC, re.M)
    assert re.search(r"^DEFAULT_AUTOMATION_LENGTH\s*=\s*12\s*$", SRC, re.M)
    assert re.search(r"^DEFAULT_PLAYLIST_ROWS\s*=\s*32\s*$", SRC, re.M)
    assert re.search(r"^CANONICAL_SIGNAL_CONTROL_DEFAULT\s*=\s*1\.00\s*$", SRC, re.M)
    assert re.search(r"^CANONICAL_LIVE_OVERBLEND_DEFAULT_PCT\s*=\s*50\.0\b", SRC, re.M)
    assert re.search(r"^EQR_DEFAULT\s*=\s*0\.4014\s*$", SRC, re.M)


def test_ui_uses_authoritative_defaults():
    assert "self.spin_seq_length.setValue(DEFAULT_SEQUENCE_LENGTH)" in SRC
    assert "self.spin_auto_point_length.setValue(DEFAULT_AUTOMATION_LENGTH)" in SRC
    assert "self.spin_playlist_length.setValue(DEFAULT_PLAYLIST_ROWS)" in SRC
    assert "self.slider_eqr.setValue(EQR_DEFAULT * 100.0)" in SRC
    assert "self.spin_canonical_live_overblend.setValue(CANONICAL_LIVE_OVERBLEND_DEFAULT_PCT)" in SRC


def test_no_legacy_spin_fallback_defaults():
    assert not re.search(r"spin_seq_length[^\n]*else\s+(?:16|48)\b", SRC)
    assert not re.search(r"spin_playlist_length[^\n]*else\s+(?:64|96)\b", SRC)
    assert "default_seq_len = 16" not in SRC
    assert "auto_len = 16" not in SRC
    assert "int(auto_len) or 16" not in SRC
    assert "length_steps=16" not in SRC
    assert "length_spin.setValue(16)" not in SRC
    assert "Default playlist row duration: 16 beats." not in SRC


def test_overblend_and_help_wording_agree():
    assert "0% (default) preserves maximum user/live dynamics" not in SRC
    assert "50% is the default equal user/canonical waveform blend" in SRC
    assert "EQR: **0.4014**" in HELP
    assert "Default Step Sequence Length: 12 steps" in HELP
    assert "Default Automation Sequence Length: 12 steps" in HELP
    assert "Playlist Rows defaults to 32" in HELP


def test_sequence_automation_project_and_clear_memory_sync():
    assert '"automation_length": int(self.spin_auto_point_length.value())' in SRC
    assert '("spin_auto_point_length", "automation_length")' in SRC
    assert '"spin_auto_point_length", "spin_auto_point_step", "spin_auto_syncopate"' in SRC
    assert '_set_value("spin_seq_length", DEFAULT_SEQUENCE_LENGTH)' in SRC
    assert '_set_value("spin_auto_point_length", DEFAULT_AUTOMATION_LENGTH)' in SRC
    assert 'self.sequencer_automation_points = []' in SRC
