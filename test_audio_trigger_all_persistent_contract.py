from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / 'groovebox.py').read_text()
callback = src[src.index('    def _pkp_poly_callback'):src.index('    def _pkp_poly_submit')]
submit = src[src.index('    def _pkp_poly_submit'):src.index('    def _pkp_fire_step_hit')]
trigger = src[src.index('    def trigger_all_instruments_hit'):src.index('    def _on_viz_mode_changed')]
assert 'master_volume' in callback, 'polyphonic audition must use authoritative master volume'
assert 'open_output_stream' in submit and 'stream.start()' in submit, 'persistent audition stream must be startable'
assert 'self._pkp_poly_submit(mix, sr)' in trigger, 'Trigger All must use persistent audition stream'
assert 'play_buffer(' not in trigger and 'sd.play(' not in trigger, 'Trigger All must not replace/conflict with active output stream'
assert 'self.ball_synth_group' in src and 'self.cellular_synth_group' in src
assert 'below_seq_layer.addWidget(self.ball_synth_group, 1)' in src
assert 'below_seq_layer.addWidget(self.cellular_synth_group, 1)' in src
print('PASS persistent Trigger All shared-gain stream and Ball/Cellular Automata side panels')
