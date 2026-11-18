from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_multidim_combo_uses_display_label_but_keeps_stable_key():
    src = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    assert "self.cmb_inst.addItem(str(_label), str(_key))" in src
    assert "key = self.cmb_inst.currentData()" in src
    assert "def refresh_instrument_labels(self):" in src


def test_multidim_has_direct_rename_and_restore_control():
    src = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    assert "self.ed_instrument_label = QLineEdit()" in src
    assert "self.btn_apply_instrument_label.clicked.connect(self._apply_instrument_label)" in src
    assert "setter(key, self.ed_instrument_label.text())" in src
    assert "Clear and apply to restore the default label." in src


def test_host_rename_preserves_instrument_identity_and_refreshes_multidim():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "def _set_instrument_display_name(self, key, value):" in src
    assert "win.refresh_instrument_labels()" in src
    assert '"instrument_display_names"' in src
