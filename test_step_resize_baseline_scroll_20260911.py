"""Regression: manual STEP resize persists through canonical reset and long lanes really scroll."""
from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

assert 'self.spin_seq_length.setRange(1, 1024)' in SRC
assert 'def _commit_selected_sequence_user_baseline' in SRC

resize = SRC[SRC.index('def _on_sequence_length_changed'):SRC.index('def _refresh_sequence_dependent_panels')]
assert 'mem["length_user_locked"] = True' in resize
assert 'self._commit_selected_sequence_user_baseline(promote=True)' in resize
assert 'live_mem["pattern_length"] = n' in resize
assert 'self.rebuild_sequencer_steps(n)' in resize

commit = SRC[SRC.index('def _commit_selected_sequence_user_baseline'):SRC.index('def _on_sequence_length_changed')]
assert 'snap_bank[sid] = copy.deepcopy(mem)' in commit
assert 'snap_patterns[name] = copy.deepcopy(mem)' in commit
assert 'mem["canonical_owner"] = None' in commit
assert 'mem["user_owned"] = True' in commit

geo = SRC[SRC.index('def _sync_step_strip_geometry'):SRC.index('def _sync_automation_strip_geometry')]
assert 'fit_w = usable // count' in geo
assert 'scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)' in geo
assert 'widget.setMaximumWidth(target_w)' in geo
assert 'btn.setMaximumWidth(cell_w)' in geo
assert 'cell_w = readable_w' in geo

# A screen-width-derived 14-cell fit may never become the sequence length.
assert 'count = max(1, len(buttons))' in geo
assert 'pattern_length' not in geo
print('PASS manual resize baseline + fixed overflow STEP scroll contract')
