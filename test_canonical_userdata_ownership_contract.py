from pathlib import Path
import ast

SRC = Path(__file__).with_name('groovebox.py')
TEXT = SRC.read_text(encoding='utf-8')
TREE = ast.parse(TEXT)

def _method(name):
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f'missing method {name}')

def test_canonical_global_algo_projection_never_assigns_userdata_store():
    fn = _method('_canonical_superwrite_global_algo')
    segment = ast.get_source_segment(TEXT, fn) or ''
    assert 'self.global_algo_state =' not in segment
    assert 'self._canonical_global_algo_projection = gas' in segment
    assert 'gas["user_data"] = False' in segment
    assert 'gas["user_defined"] = False' in segment
    assert 'gas["canonical_owner"] = "unison"' in segment

def test_effective_projection_is_separate_from_saved_userdata():
    effective = ast.get_source_segment(TEXT, _method('_effective_global_algo_state')) or ''
    snap = ast.get_source_segment(TEXT, _method('_project_history_snapshot')) or ''
    assert '_canonical_global_algo_projection' in effective
    # History/project state must store the authored bay, not the ephemeral canonical projection.
    assert 'global_algo_state' in snap
    assert '_canonical_global_algo_projection' not in snap

def test_zero_engine_path_drops_projection_and_reseeds_clean_baseline():
    fn = ast.get_source_segment(TEXT, _method('_ensure_perfect_unison')) or ''
    assert 'self._clear_canonical_global_algo_projection()' in fn
    assert 'self._canonical_last_active_set = frozenset()' in fn
    assert 'self._canonical_user_rows_snapshot = copy.deepcopy' in fn
    assert 'self._canonical_pattern_user_store = copy.deepcopy' in fn
    assert 'self._canonical_panels_user_store = copy.deepcopy' in fn
    assert 'self._canonical_macro_user_store = copy.deepcopy' in fn

def test_mixed_engine_cycles_rederive_projection_not_previous_projection():
    fn = ast.get_source_segment(TEXT, _method('_ensure_perfect_unison')) or ''
    superwrite = ast.get_source_segment(TEXT, _method('_canonical_superwrite_global_algo')) or ''
    assert 'if not _prev_active:' in fn
    assert 'self._clear_canonical_global_algo_projection()' in fn
    assert 'user_gas = getattr(self, "global_algo_state", None)' in superwrite
    assert 'gas = copy.deepcopy(user_gas)' in superwrite
    assert 'getattr(self, "_canonical_global_algo_projection"' not in superwrite

def test_user_edit_paths_do_not_mark_authored_bay_as_canonical():
    # Outside the canonical projection method there must be no authored-state assignment
    # that flips canonical_superwrite back on.
    start = TEXT.index('    def _canonical_superwrite_global_algo(self):')
    end = TEXT.index('    def _get_active_engine_set(self):', start)
    outside = TEXT[:start] + TEXT[end:]
    assert 'self.global_algo_state["canonical_superwrite"] = True' not in outside
