"""Overflow-safe entry points added to the original, working V3 workstation."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QGroupBox, QMenu, QToolBar, QToolButton, QLineEdit, QCompleter


class _WorkspaceNav:
    """GROOVEBOX_R32_WORKSPACE_NAV_20261110 — section navigation for the main workspace.

    * menu rebuilt on every open (all panels, grouped TOP / BOTTOM, incl. R32 side panels & deck)
    * find box with completion: type part of a title, Enter jumps
    * ◀ / ▶ step to the previous / next section in screen order
    * history: Back / Forward through jumps
    * 3 bookmarks: right-click 🔖n to store the current view, click to return
    * the target panel's border flashes for a moment after a jump
    """
    AREAS = (("top_ui_scroll", "Composition (top)"), ("bottom_render_scroll", "Playback · export · visuals (bottom)"))

    def __init__(self, host):
        self.host = host; self.back = []; self.fwd = []; self.marks = {}; self._last = None

    def sections(self):
        out = []
        for attr, label in self.AREAS:
            sc = getattr(self.host, attr, None)
            if sc is None or sc.widget() is None:
                continue
            seen = set()
            for g in sc.widget().findChildren(QGroupBox):
                t = g.title().strip()
                if not t or t in seen or not g.isVisibleTo(sc.widget()):
                    continue
                seen.add(t)
                pos = g.mapTo(sc.widget(), g.rect().topLeft())
                out.append((label, t, sc, g, (pos.y(), pos.x())))
        out.sort(key=lambda r: (r[0], r[4]))
        return out

    def _view(self, sc):
        return (sc, sc.horizontalScrollBar().value(), sc.verticalScrollBar().value())

    def jump(self, sc, g, record=True):
        if record:
            self.back.append(self._view(sc)); del self.back[:-50]; self.fwd.clear()
        sc.ensureWidgetVisible(g, 12, 12); self._last = g; self._flash(g)

    def _flash(self, g):
        old = g.styleSheet()
        try:
            g.setStyleSheet(old + " QGroupBox{border:2px solid #ffd85a;}")
            QTimer.singleShot(900, lambda: g.setStyleSheet(old))
        except RuntimeError:
            pass

    def step(self, d):
        secs = self.sections()
        if not secs:
            return
        idx = next((i for i, r in enumerate(secs) if r[3] is self._last), -1)
        r = secs[(idx + d) % len(secs)]
        self.jump(r[2], r[3])

    def go_back(self):
        if self.back:
            sc, x, y = self.back.pop(); self.fwd.append(self._view(sc))
            sc.horizontalScrollBar().setValue(x); sc.verticalScrollBar().setValue(y)

    def go_fwd(self):
        if self.fwd:
            sc, x, y = self.fwd.pop(); self.back.append(self._view(sc))
            sc.horizontalScrollBar().setValue(x); sc.verticalScrollBar().setValue(y)

    def fill_menu(self, menu):
        menu.clear(); cur = None
        for label, t, sc, g, _p in self.sections():
            if label != cur:
                if cur is not None:
                    menu.addSeparator()
                hdr = menu.addAction("— %s —" % label); hdr.setEnabled(False); cur = label
            a = menu.addAction(t)
            a.triggered.connect(lambda _c=False, s=sc, w=g: self.jump(s, w))

    def find(self, text):
        t = text.strip().lower()
        if not t:
            return
        for _l, title, sc, g, _p in self.sections():
            if t in title.lower():
                self.jump(sc, g); return

    def add_controls(self, toolbar):
        for cap, tip, fn in (("◀", "Previous section", lambda: self.step(-1)), ("▶", "Next section", lambda: self.step(1)),
                             ("↶", "Back (jump history)", self.go_back), ("↷", "Forward", self.go_fwd)):
            a = toolbar.addAction(cap); a.setToolTip(tip); a.triggered.connect(lambda _c=False, f=fn: f())
        box = QLineEdit(); box.setPlaceholderText("Find panel…"); box.setMaximumWidth(170)
        box.setToolTip("Type part of a panel title, press Enter to jump there")

        def _refresh_completer():
            comp = QCompleter(sorted({r[1] for r in self.sections()}), box)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); comp.setFilterMode(Qt.MatchFlag.MatchContains)
            comp.activated.connect(self.find); box.setCompleter(comp)
        box.returnPressed.connect(lambda: self.find(box.text()))
        QTimer.singleShot(3000, _refresh_completer)
        box.textEdited.connect(lambda _t: box.completer() is None and _refresh_completer())
        toolbar.addWidget(box)
        for n in (1, 2, 3):
            b = QToolButton(toolbar); b.setText("🔖%d" % n)
            b.setToolTip("Click: return to bookmark %d · right-click: store the current view" % n)
            b.clicked.connect(lambda _c=False, k=n: self._recall(k))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, k=n, bb=b: self._store(k, bb))
            toolbar.addWidget(b)

    def _store(self, k, b):
        sc = getattr(self.host, "top_ui_scroll", None)
        if sc is not None:
            self.marks[k] = self._view(sc); b.setText("🔖%d●" % k)

    def _recall(self, k):
        m = self.marks.get(k)
        if m:
            sc, x, y = m; self.back.append(self._view(sc))
            sc.horizontalScrollBar().setValue(x); sc.verticalScrollBar().setValue(y)


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
    nav = _WorkspaceNav(host)
    host._workspace_nav = nav
    menu.aboutToShow.connect(lambda: nav.fill_menu(menu))      # R32.8: rebuilt every time → new panels appear
    sections.setMenu(menu)
    toolbar.addWidget(sections)
    nav.add_controls(toolbar)

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
    action("3D Studio", lambda: __import__("obj_scene").open_window(host),
           "Wrap media on an OBJ, tint it, and place it in a scene")
    action("Export Jobs", lambda: host._open_export_jobs() if hasattr(host, "_open_export_jobs") else None,
           "The export queue: progress, retry, remove")
    action("File Studio", lambda: __import__("file_studio").open_window(host),
           "Browse, copy and manage project media")
    action("Takes", lambda: __import__("take_finisher").open_window(host),
           "Finish a take: trim, stamp the seed, keep the good one")
    action("Seed", lambda: __import__("seed_inspector").open_window(host),
           "Current seed fingerprint and the last export that carries it")
    action("Snapshot", lambda: __import__("session_snapshot").open_window(host),
           "Save which windows are open and where they sit")
    action("Last export", lambda: __import__("last_export").open_window(host),
           "Open the folder of the newest finished export and copy its path")
    from PyQt6.QtWidgets import QScrollArea, QSizePolicy
    area = QScrollArea()
    area.setWidgetResizable(False)
    area.setWidget(toolbar)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setFixedHeight(48)
    toolbar.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    layout.insertWidget(0, area)
    host.workstation_toolbar = toolbar
    return toolbar
