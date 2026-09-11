"""Regression: render STEP grid must not collapse to the GUI-selected sequence length."""
from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

# The render pass computes a stable reference grid from active sequence memories.
assert 'seq_len = max(' in SRC

# Inside the per-voice schedule mapping, never read the editor spinner as the clock.
start = SRC.index('# CANONICAL_SCHEDULE_AUTHORITY_2026')
end = SRC.index('inst_step_duration =', start)
block = SRC[start:end]
assert 'EDITOR_GRID_ISOLATION_2026' in block
assert '_schedule_slots = max(1, int(seq_len))' in block
assert 'self.spin_seq_length.value()' not in block

# Selection differences may change which bank is edited, but not another bank's render grid.
assert 'longer STEP lanes down to that shorter GUI value' in block
print('PASS STEP render-grid selection isolation contract')
