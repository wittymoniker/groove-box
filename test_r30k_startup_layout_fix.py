from pathlib import Path
p = Path(__file__).with_name('groovebox.py')
s = p.read_text(encoding='utf-8')
start = s.index('        editor_button_grid = QHBoxLayout()')
end = s.index('        editor_bottom_row = QHBoxLayout()', start)
block = s[start:end]
assert 'editor_button_grid.setHorizontalSpacing(' not in block
assert 'editor_button_grid.setVerticalSpacing(' not in block
assert 'editor_button_grid.setSpacing(5)' in block
print('PASS: QHBoxLayout editor launcher uses supported spacing API')
