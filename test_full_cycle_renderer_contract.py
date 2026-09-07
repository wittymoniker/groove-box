"""Static renderer contract test that does not require PyQt6 at package-test time."""
import ast, re
from pathlib import Path
src=Path(__file__).with_name('author_numeric_font.py').read_text()
tree=ast.parse(src)
methods={}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in {'_draw_full_cycle','_face_pixmap'}:
        methods[node.name]=ast.get_source_segment(src,node)
assert '_draw_full_cycle' in methods and '_face_pixmap' in methods
full=methods['_draw_full_cycle']
# The saturated body is explicitly encoded as 4 groups x 3 main strokes.
group_block=full[full.index('groups = ('):full.index('painter.setPen', full.index('groups = ('))]
coords=re.findall(r'\(0\.\d+,0\.\d+,0\.\d+,0\.\d+\)', group_block)
assert len(coords)==12, len(coords)
assert 'dotted=False' in full
face=methods['_face_pixmap']
assert face.index('self._draw_full_cycle') < face.index('self._draw_crossbars')
print('PASS renderer full-cycle 16 = 12 solid main strokes + invariant 4 solid subdividers')
