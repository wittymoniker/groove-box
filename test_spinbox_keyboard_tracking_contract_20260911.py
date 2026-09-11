"""Regression: typed spinbox edits publish only committed values project-wide."""
from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

assert 'QAbstractSpinBox' in SRC
assert 'def _configure_spinbox_input_behavior(widget):' in SRC
cfg = SRC[SRC.index('def _configure_spinbox_input_behavior'):SRC.index('class _MathSymbolSpinWatcher')]
assert 'widget.setKeyboardTracking(False)' in cfg
assert 'isinstance(widget, QAbstractSpinBox)' in cfg

watch_start = SRC.index('    def eventFilter(self, obj, event):', SRC.index('class _MathSymbolSpinWatcher'))
watch_end = SRC.index('# =============================================================================\n# PROCESSOR SYNTAX', watch_start)
watch = SRC[watch_start:watch_end]
assert 'event.type() == QEvent.Type.Show and isinstance(obj, QAbstractSpinBox)' in watch
assert '_configure_spinbox_input_behavior(obj)' in watch
# Behavior must happen before the optional Math Symbols branch.
assert watch.index('_configure_spinbox_input_behavior(obj)') < watch.index('if MATH_SYMBOLS_ENABLED')

install = SRC[SRC.index('def _install_math_symbol_numeric_overlays'):SRC.index('def _refresh_math_symbol_numeric_overlays')]
assert 'self.findChildren(QAbstractSpinBox)' in install
assert '_configure_spinbox_input_behavior(w)' in install
# Watcher installation occurs before the Symbols-OFF early return.
assert install.index('app.installEventFilter(self._math_symbol_spin_watcher)') < install.index('if not MATH_SYMBOLS_ENABLED:')
print('PASS global committed-only spinbox keyboard tracking contract')
