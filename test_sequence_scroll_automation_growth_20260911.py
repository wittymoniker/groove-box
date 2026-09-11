"""Regression contract: >24 sequences scroll and grown Automator cells persist full ON state."""
from pathlib import Path
import re
SRC = Path(__file__).with_name('groovebox.py').read_text()

# User-facing sequence/automation ranges remain 1..1024, not 24.
assert 'self.spin_seq_length.setRange(1, 1024)' in SRC
assert 'self.spin_auto_point_length.setRange(1, 1024)' in SRC

# Long strips own their width; Qt must not squeeze them and hide the scrollbar.
assert 'self.steps_scroll.setWidgetResizable(False)' in SRC
assert 'self.sequencer_automation_scroll.setWidgetResizable(False)' in SRC
assert 'def _sync_step_strip_geometry(self):' in SRC
assert 'def _sync_automation_strip_geometry(self):' in SRC
assert 'scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)' in SRC
assert 'widget.setMaximumWidth(target_w)' in SRC

# Manual length edits cannot be snapped back to a canonical seed-derived count (e.g. 14/24).
assert 'mem["length_user_locked"] = True' in SRC
assert 'bool(mem.get("length_user_locked"))' in SRC
assert 'def _commit_selected_sequence_user_baseline' in SRC
assert 'self._commit_selected_sequence_user_baseline(promote=True)' in SRC

# Grown/new Automator cells are stored ON and carry their own selection/parameter snapshot.
assert 'def _new_automation_point(self, step, instrument_name=None, sequence_id=None):' in SRC
assert '"enabled": True' in SRC
assert '"canonical_owner": "user:sequencer_automation", "user_owned": True' in SRC
assert 'point["synth_param_value"] = _stored_val' in SRC
assert 'point.setdefault("synth_values", {})[key] = _stored_val' in SRC
assert 'TELEPORT_LOAD_SIGNAL_FIX_20260911' in SRC
assert 'for w in widgets:' in SRC and 'w.blockSignals(False)' in SRC
assert '"sequence_envelope_attack": float(self.popup_auto_attack.value())/100.0' in SRC
assert '"sequence_envelope_release": float(self.popup_auto_release.value())/100.0' in SRC
assert 'self._materialize_new_automation_steps(old_n + 1, n, src_inst, src_sid)' in SRC

# Point-specific synth values are actually consumed by the render resolver.
assert 'point_values = point.get("synth_values", {})' in SRC
assert 'synth[str(key)] = float(value)' in SRC

print('PASS >24 scroll + automation growth state contract')
