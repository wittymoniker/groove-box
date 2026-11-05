from pathlib import Path

SRC = (Path(__file__).with_name("groovebox.py")).read_text(encoding="utf-8")


def test_purple_shortcut_area_has_no_redundant_editor_or_per_canonical_buttons():
    block = SRC[SRC.index('(\"PURPLE · GLOBAL PATCH / SYNTH\"'):SRC.index('(\"Project\"', SRC.index('(\"PURPLE · GLOBAL PATCH / SYNTH\"'))]
    assert 'Edit Synth' not in block
    assert 'SEEDED Engine' not in block
    assert 'RAND Engine' not in block
    assert 'LOCK Engine' not in block
    assert 'EUCLIDEAN Engine' not in block
    assert 'GOAVA Engine' not in block
    assert 'FRACTAL SEED Engine' not in block
    assert 'Canonical Mixer' in block
    assert 'Scenograph' in block
    assert 'Background / Video Studio' in block


def test_project_wide_modulation_has_one_shared_attachment_and_reset():
    assert 'self.global_mod_group = None' in SRC
    assert 'self.btn_reset_global_xmod = QPushButton("RESET MASTER XMOD")' in SRC
    assert 'btn_reset_window_mods = QPushButton' not in SRC
    assert 'Individual synth panels do not have duplicate global controls.' in SRC


def test_green_and_purple_action_sections_are_nested_in_parent_panels():
    assert 'purpleWorkspaceParent' in SRC
    assert 'greenWorkspaceParent' in SRC
    assert 'purple_child_row.addWidget(box, 1)' in SRC
    assert 'green_parent_layout.addWidget(box)' in SRC


def test_master_eq_and_automation_source_selector_are_visible_controls():
    assert 'self.master_global_eq_group.setMinimumHeight(190)' in SRC
    assert 'self.master_global_eq_curve.setMinimumHeight(118)' in SRC
    assert 'self.combo_automation_source_sequence = QComboBox()' in SRC
    assert 'AUTOMATION · SOURCE SEQUENCE / STEP DESTINATION / MODULATION' in SRC


def test_scenograph_async_render_always_releases_lane_and_exposes_failure():
    assert 'def _queue_render_request(self, request):' in SRC
    assert 'def _fallback_frame(self, width, height):' in SRC
    assert 'SCENOGRAPH RENDER ERROR' in SRC
    assert 'self._render_pool.setMaxThreadCount(1)' in SRC


def test_background_is_revealed_and_lower_visual_stage_is_prioritized():
    assert 'if not bg.isVisible():' in SRC
    assert 'timer.start()' in SRC
    stage = SRC[SRC.index('# The visual stage is the primary lower pane content'):SRC.index('bottom_scroll = QScrollArea()', SRC.index('# The visual stage is the primary lower pane content'))]
    assert stage.index('bottom_layout.addLayout(vis_row)') < stage.index('bottom_layout.addWidget(visual_container, 1)')
    assert stage.index('bottom_layout.addWidget(visual_container, 1)') < stage.index('self._build_panel2_tools(zone="bottom")')
