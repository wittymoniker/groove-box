"""Overflow-safe entry points added to the original, working V3 workstation."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QGroupBox, QMenu, QToolBar, QToolButton


def install_workstation_tools(host, layout):
    toolbar = QToolBar("Workstation tools", host)
    toolbar.setObjectName("grooveboxWorkstationTools")
    toolbar.setAccessibleName("Workstation tools and section navigation")
    toolbar.setMovable(False)
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    toolbar.setStyleSheet(
        "QToolBar{background:#182638;border:1px solid #36536b;spacing:4px;padding:4px;}"
        "QToolButton{color:#e2edf5;padding:6px 9px;border:1px solid transparent;}"
        "QToolButton:hover,QToolButton:focus{background:#29455e;border-color:#87c9df;}")
    sections = QToolButton(toolbar)
    sections.setText("Workspace")
    sections.setToolTip("Jump to a control section")
    sections.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(sections)
    seen = set()
    for scroll_name in ("top_ui_scroll", "bottom_render_scroll"):
        scroll = getattr(host, scroll_name)
        for group in scroll.widget().findChildren(QGroupBox):
            title = group.title().strip()
            if not title or title in seen:
                continue
            seen.add(title)
            action = menu.addAction(title)
            action.triggered.connect(
                lambda checked=False, s=scroll, target=group: s.ensureWidgetVisible(target, 8, 8))
    sections.setMenu(menu)
    toolbar.addWidget(sections)

    def action(label, callback, description):
        item = toolbar.addAction(label)
        item.setToolTip(description)
        item.triggered.connect(lambda checked=False: callback())

    action("Live Jam", host._open_live_jam_dialog,
           "Jam-only macros, envelopes, FX and replay; does not rewrite your project")
    action("Global DJ FX", lambda: host.top_ui_scroll.ensureWidgetVisible(host.pkp_ui_group, 12, 12),
           "GOAVA, random parameters, boost, Beat Gate, Harmonic Fold and Spectral Tilt")

    def center_master():
        target = getattr(getattr(host, "main_md_panel", None), "view", None)
        if target is None:
            return
        scroll = host.top_ui_scroll
        point = target.mapTo(scroll.widget(), target.rect().center())
        scroll.horizontalScrollBar().setValue(point.x() - scroll.viewport().width() // 2)
        scroll.verticalScrollBar().setValue(point.y() - scroll.viewport().height() // 2)

    action("Master Synth", center_master, "Center the large animated master synth in the composition viewport")
    action("LAN Chat", host._open_lan_chat, "Open the existing performance/LAN chat implementation")
    cancel_work = QAction("Cancel Work", toolbar)
    cancel_work.setToolTip("Stop a partial canonical recomputation; never stops audio or deletes user sequences")
    cancel_work.setEnabled(False)
    cancel_work.triggered.connect(lambda: getattr(host, "_canonical_commit", None)
                                 and host._canonical_commit.cancel())
    toolbar.addAction(cancel_work)
    host._cancel_canonical_action = cancel_work
    host._cancel_canonical_button = toolbar.widgetForAction(cancel_work)
    action("Random Object", host._open_random_object_dialog,
           "Generate seeded audio, image, video or voxel assets; binding is explicit")

    def multidim():
        from multidim_ui import open_multidim_window
        open_multidim_window(host)

    action("Multidimensional", multidim, "Open the existing multidimensional synth editor")
    action("Canonical data", host._open_canonical_data, "Inspect canonical source data and ownership")
    action("Performance", host._open_performance_tab, "Open the existing performance controls")
    layout.insertWidget(0, toolbar)
    host.workstation_toolbar = toolbar
    return toolbar
