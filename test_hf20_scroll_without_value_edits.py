from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / 'groovebox.py').read_text(encoding='utf-8')
OVERLAY = (ROOT / 'BUILD_ISO' / 'app-overlay-v35.22zz' / 'groovebox.py').read_text(encoding='utf-8')


def test_wheel_filter_routes_value_widget_wheel_to_scroll_area():
    block = SOURCE.split('class _NoWheelSliderFilter(QObject):', 1)[1].split('\n\nclass SeedScriptSyntaxHighlighter', 1)[0]
    for widget in ('QSlider', 'QDial', 'QSpinBox', 'QDoubleSpinBox', 'QComboBox'):
        assert widget in block
    assert 'area.verticalScrollBar()' in block
    assert 'area.horizontalScrollBar()' in block
    assert 'bar.setValue(bar.value() - delta.y())' in block
    assert 'event.accept()' in block and 'return True' in block


def test_main_and_iso_overlay_have_identical_wheel_behavior():
    block = 'class _NoWheelSliderFilter(QObject):'
    assert SOURCE[SOURCE.index(block):SOURCE.index('class SeedScriptSyntaxHighlighter')] == OVERLAY[OVERLAY.index(block):OVERLAY.index('class SeedScriptSyntaxHighlighter')]


def test_performance_tabs_are_scroll_wrapped_and_synth_master_volume_is_shared():
    perf = (ROOT / 'performance.py').read_text(encoding='utf-8')
    assert 'def _scroll_page(self, page: QWidget) -> QScrollArea:' in perf
    assert 'right.addTab(self._scroll_page(self._build_playlist_tab())' in perf
    assert 'self.host, "slider_master_vol"' in perf
    assert 'updater(value)' in perf


def test_hardware_volume_instances_poll_shared_state_without_touching_synth_master():
    hw = (ROOT / 'hardware_volume.py').read_text(encoding='utf-8')
    assert "STATE_PATH = Path(os.environ.get('GROOVEBOX_HARDWARE_VOLUME_STATE','/var/lib/groovebox/hardware-volume.state'))" in hw
    assert 'self._poll.timeout.connect(self.sync_from_state)' in hw
    assert "request_hardware_volume('set',value)" in hw
    assert 'self.master_volume' not in hw


def test_hf23_all_value_controls_are_wheel_locked_even_when_focused_or_dynamic():
    block = SOURCE.split('    def eventFilter(self, obj, event):', 1)[-1].split('\n    def _sync_square_visuals', 1)[0]
    assert '(QSlider, QDial, QSpinBox, QDoubleSpinBox, QComboBox)' in block
    assert 'event.type() == QEvent.Type.Wheel' in block
    assert 'self._forward_wheel_to_scroll_area(obj, event)' in block
    assert 'event.accept()' in block and 'return True' in block
    assert 'allow = bool(obj.hasFocus())' not in block


def test_hf23_iso_overlay_has_same_project_wheel_guard():
    marker = '    def eventFilter(self, obj, event):'
    end = '\n    def _sync_square_visuals'
    assert SOURCE[SOURCE.index(marker):SOURCE.index(end, SOURCE.index(marker))] == OVERLAY[OVERLAY.index(marker):OVERLAY.index(end, OVERLAY.index(marker))]
