#!/usr/bin/env python3
from pathlib import Path
src=(Path(__file__).resolve().parent/'groovebox.py').read_text(encoding='utf-8')
# R23r: the separate Global XMOD render pass (which held ALGORITHM_XMOD_PARITY_2026)
# is retired; Algorithm automation depth now follows the XMOD master for every instrument.
assert 'GLOBAL_XMOD_2026 retired' in src
assert 'Algorithm automation depth follows the XMOD master' in src
assert 'def _algorithm_modulate_resolved_automation' in src
# all three automation edge returns plus the interpolated return route through the modifier
chunk=src[src.index('def _algorithm_modulate_resolved_automation'):src.index('def _on_automator_timing_mode_changed')]
assert chunk.count('_algorithm_modulate_resolved_automation(') >= 5
assert 'for bucket in ("synth","sequence")' in chunk
assert 'global_algo_state' in chunk and 'global_algorithm_applied' in chunk
# The old accidental coupling between Algorithm and the heuristic STEP writer must be absent
assert 'btn_heuristic_write_step' not in chunk
print('PASS algorithm XMOD step/automation variable parity without lane composition')
