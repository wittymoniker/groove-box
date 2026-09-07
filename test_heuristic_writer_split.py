"""Headless contract test for independent heuristic STEP/AUTOMATION revert layers."""
import ast, copy, re
from pathlib import Path
import numpy as np

SRC = Path(__file__).with_name('groovebox.py').read_text()
TREE = ast.parse(SRC)
wanted = {
    '_heuristic_snapshot_fields', '_heuristic_restore_fields',
    '_heuristic_write_step_into_sequence', '_heuristic_write_automation_into_sequence',
    '_heuristic_restore_writer', '_heuristic_apply_writer',
}
methods = []
for node in ast.walk(TREE):
    if isinstance(node, ast.ClassDef):
        for fn in node.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in wanted:
                methods.append(ast.get_source_segment(SRC, fn))
assert {re.search(r'def\s+(\w+)', m).group(1) for m in methods} == wanted
body = '\n'.join('    '+line if line else line for m in methods for line in (m+'\n').splitlines())
ns = {'copy': copy, 'np': np, 'identity_unit': lambda *a: 0.0}
exec('class Harness:\n'+body, ns)
Harness = ns['Harness']
Harness._HEURISTIC_STEP_FIELDS = (
    'steps','gates','amplitudes','pitches','probabilities','offsets','pattern_length',
    'heuristic_family','heuristic_bias','canonical_owner',
)
Harness._HEURISTIC_AUTOMATION_FIELDS = ('automation_lane','automation_lane_length')

class Box:
    def __init__(self, text): self.text=text
    def currentText(self): return self.text
class Spin:
    def __init__(self, v): self.v=v
    def value(self): return self.v

def make():
    h=Harness()
    original={
        'steps':[True,False], 'gates':[True,False], 'amplitudes':[.4,.6], 'pitches':[1.,2.],
        'probabilities':[50,60], 'offsets':[0.,.1], 'pattern_length':2,
        'automation_lane':[{'step':1,'value':.1}], 'automation_lane_length':1,
        'user_field':'keep',
    }
    h.instrument_sequence_banks={'A':{1:copy.deepcopy(original)}}
    h.instrument_sequencer_memory={'A':h.instrument_sequence_banks['A'][1]}
    h.instrument_selected_sequence={'A':1}
    h.sequencer_automation_points=[{'from_instrument':'A','from_sequence':1,'canonical_owner':'user:prior','value':.1}]
    h._heuristic_writer_snapshots={'step':None,'automation':None}
    h.combo_heuristic_family=Box('Hybrid'); h.combo_heuristic_bias=Box('Balanced')
    h.spin_heuristic_span=Spin(2); h.combo_heuristic_scope=Box('LOCAL')
    h._heuristic_target_list=lambda scope=None:[('A',1)]
    h._heuristic_values=lambda *a:[.2,.8]
    h._ensure_seq_mem_length=lambda mem,n: None
    def bake(points, pattern_name='', activate=True, instrument_name=None, sequence_id=None):
        mem=h.instrument_sequence_banks[instrument_name][int(sequence_id)]
        mem['automation_lane']=[{'step':i+1,'value':float(v)/100.0,'canonical_owner':'pattern:heuristic'} for i,v in enumerate(points)]
        mem['automation_lane_length']=len(points)
        h.sequencer_automation_points=[p for p in h.sequencer_automation_points if not (
            p.get('from_instrument')==instrument_name and int(p.get('from_sequence',1))==int(sequence_id)
        )]
        h.sequencer_automation_points.extend([
            {'from_instrument':instrument_name,'from_sequence':int(sequence_id),'canonical_owner':'pattern:heuristic','value':float(v)/100.0}
            for v in points
        ])
    h._bake_automation_pattern_to_tiles=bake
    return h, original

# Step then Automation: each revert owns only its layer.
h, original=make()
h._heuristic_apply_writer('step')
step_written=copy.deepcopy(h.instrument_sequence_banks['A'][1]['steps'])
assert step_written != original['steps']
h._heuristic_apply_writer('automation')
auto_written=copy.deepcopy(h.instrument_sequence_banks['A'][1]['automation_lane'])
h._heuristic_restore_writer('step')
mem=h.instrument_sequence_banks['A'][1]
for k in Harness._HEURISTIC_STEP_FIELDS:
    if k in original: assert mem[k] == original[k], k
    else: assert k not in mem, k
assert mem['automation_lane'] == auto_written
assert mem['user_field']=='keep'
h._heuristic_restore_writer('automation')
assert mem['automation_lane']==original['automation_lane']
assert mem['automation_lane_length']==original['automation_lane_length']
assert h.sequencer_automation_points[0]['canonical_owner']=='user:prior'

# Automation then Step: reverse order is equally independent.
h, original=make()
h._heuristic_apply_writer('automation')
h._heuristic_apply_writer('step')
step_written=copy.deepcopy(h.instrument_sequence_banks['A'][1]['steps'])
h._heuristic_restore_writer('automation')
mem=h.instrument_sequence_banks['A'][1]
assert mem['steps']==step_written
assert mem['automation_lane']==original['automation_lane']
h._heuristic_restore_writer('step')
assert mem['steps']==original['steps']
assert mem['user_field']=='keep'

# UI contract is explicitly split and no longer Step+Automation combined.
assert 'HEURISTIC WRITE STEP · OFF' in SRC
assert 'HEURISTIC WRITE AUTOMATION · OFF' in SRC
assert 'Sequence + Automation' not in SRC[SRC.find('HEURISTIC_COMPOSER_V3'):SRC.find('# SEED WEIGHT + FULLWEIGHT')]
print('PASS heuristic STEP/AUTOMATION independent revert + LOCAL/GLOBAL shared scope contract')

# V10 UI contract: exactly two heuristic write controls; the retired direct
# lattice/third Step writer must not exist or influence render activation.
assert 'self.btn_nt_apply =' not in SRC
assert 'def _on_nt_lattice_apply' not in SRC
assert 'chk_edit_algorithm_per_sequence' not in SRC
assert 'def _sync_nt_lattice_button_state' not in SRC
assert 'getattr(self, "btn_heuristic_write_step", None)' in SRC
assert SRC.count('QPushButton("HEURISTIC WRITE STEP · OFF")') == 1
assert SRC.count('QPushButton("HEURISTIC WRITE AUTOMATION · OFF")') == 1
print('PASS: exactly two heuristic writer controls; legacy third Step writer retired')
