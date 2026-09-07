#!/usr/bin/env python3
from pathlib import Path
src=(Path(__file__).resolve().parent/'groovebox.py').read_text(encoding='utf-8')
assert 'ALGORITHM_XMOD_PARITY_2026' in src
assert 'Heuristic writers remain' in src
assert 'def _algorithm_modulate_resolved_automation' in src
# all three automation edge returns plus the interpolated return route through the modifier
chunk=src[src.index('def _algorithm_modulate_resolved_automation'):src.index('def _on_automator_timing_mode_changed')]
assert chunk.count('_algorithm_modulate_resolved_automation(') >= 5
assert 'for bucket in ("synth","sequence")' in chunk
assert 'global_algo_state' in chunk and 'global_algorithm_applied' in chunk
# The old accidental coupling between Algorithm and the heuristic STEP writer must be absent
render=src[src.index('ALGORITHM_XMOD_PARITY_2026')-1000:src.index('ALGORITHM_XMOD_PARITY_2026')+2200]
assert 'btn_heuristic_write_step' not in render
print('PASS algorithm XMOD step/automation variable parity without lane composition')
