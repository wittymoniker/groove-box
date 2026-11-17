from pathlib import Path
p = Path(__file__).with_name('groovebox.py')
s = p.read_text(encoding='utf-8')
start = s.index('        editor_button_grid = QGridLayout()')
end = s.index('        editor_bottom_row = QHBoxLayout()', start)
block = s[start:end]
# The four editor launchers are a 2x2 QGridLayout, which supports per-axis spacing.
assert 'editor_button_grid.setHorizontalSpacing(' in block
assert 'editor_button_grid.setVerticalSpacing(' in block
assert 'editor_button_grid.setSpacing(5)' not in block
print('PASS: 2x2 editor launcher grid uses the QGridLayout spacing API')
