"""Regression: STEP sequence length has one user-authoritative writer."""
from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

# Explicit user edit remains the primary pattern_length writer.
resize = SRC[SRC.index('def _on_sequence_length_changed'):SRC.index('def _refresh_sequence_dependent_panels')]
assert 'mem["pattern_length"] = n' in resize
assert 'mem["length_user_locked"] = True' in resize

# Canonical reconciliation may create canonical banks of their own lengths, but the
# post-reconcile normalizer may not mutate user/editor pattern_length or the spinner.
eng = SRC[SRC.index('def _engine_resize_untouched_sequences'):SRC.index('# STEP_ISOLATION_FIX')]
assert 'mem["pattern_length"] =' not in eng
assert 'spin_seq_length.setValue' not in eng
assert 'without ever resizing a user/editor sequence' in eng

# Automation lane length is independent of STEP sequence length.
loc = SRC[SRC.index('def _randomize_automation_in_sequence'):SRC.index('def _randomize_all_automation_everywhere')]
assert 'auto_n =' in loc and 'seq_n =' in loc
assert 'mem["pattern_length"] =' not in loc
assert 'for step in range(1, auto_n+1)' in loc

glob = SRC[SRC.index('def _randomize_all_automation_everywhere'):SRC.index('def _randomizer_toggle_restore')]
assert 'mem["pattern_length"] =' not in glob

# Heuristic sample count cannot become editor sequence length.
heu = SRC[SRC.index('def _heuristic_write_step_into_sequence'):SRC.index('def _heuristic_write_automation_into_sequence')]
assert 'target_n =' in heu
assert 'np.interp' in heu
assert 'mem["pattern_length"] = n' not in heu

print('PASS sequence length single-writer / automation independence contract')
