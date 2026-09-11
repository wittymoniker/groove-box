from pathlib import Path
import re

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

def test_default_lengths_are_12():
    assert re.search(r'^DEFAULT_SEQUENCE_LENGTH\s*=\s*12\s*$', SRC, re.M)
    assert re.search(r'^DEFAULT_AUTOMATION_LENGTH\s*=\s*12\s*$', SRC, re.M)

def test_initial_draw_has_post_layout_sync():
    assert 'QTimer.singleShot(0, self._finalize_initial_sequencer_draw)' in SRC
    assert 'self.rebuild_sequencer_steps(count)' in SRC

def test_primary_grid_not_resized_to_canonical_length():
    start = SRC.index('def _engine_resize_untouched_sequences')
    block = SRC[start:SRC.index('# STEP_ISOLATION_FIX', start)]
    assert 'n = int(mem.get("pattern_length", DEFAULT_SEQUENCE_LENGTH) or DEFAULT_SEQUENCE_LENGTH)' in block
    assert 'else adopt' not in block

def test_step_cells_expand_and_scroll_when_needed():
    block = SRC[SRC.index('def rebuild_sequencer_steps'):SRC.index('def _canonical_level')]
    assert 'step_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)' in block
    assert 'self.steps_inner_layout.addWidget(step_btn, 1)' in block
    assert 'step_btn.setMaximumWidth(110)' not in block
    assert 'self.steps_layout_widget.setMinimumWidth' in block
