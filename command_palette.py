"""GROOVEBOX_R124_COMMAND_PALETTE: Ctrl+K (bound by accessibility.install, which delegates here) — search every action, window and setting by name.

Sources: every QAction in the main window's menus (with its shortcut), every live_keys binding (live +
heavy commands with keys), every r124 science/live feature, and the open windows. Typing filters by
all words (any order, case-insensitive); Enter runs, Esc closes. The shortcut is shown on each row, so
the palette also teaches the keybinds.
"""
from __future__ import annotations


def entries(app):
    from PyQt6.QtGui import QAction
    out, seen = [], set()

    def add(title, keys, fn, group):
        k = (title.strip().lower(), group)
        if not title.strip() or k in seen or fn is None:
            return
        seen.add(k); out.append({"title": title.replace("&", "").strip(), "keys": keys or "", "fn": fn, "group": group})

    def walk(menu, path):
        for a in menu.actions():
            if a.isSeparator():
                continue
            if a.menu() is not None:
                walk(a.menu(), path + [a.text().replace("&", "")]); continue
            if a.isEnabled() and a.isVisible():
                add(" ▸ ".join(path + [a.text()]), a.shortcut().toString(), a.trigger, "Menu")
    try:
        for a in app.menuBar().actions():
            if a.menu() is not None:
                walk(a.menu(), [a.text().replace("&", "")])
    except Exception:
        pass
    try:
        import live_keys
        for group, keys, label, fn, _heavy in live_keys.bindings(app):
            add(label, keys, fn, group)
    except Exception:
        pass
    try:
        import r124_features
        for title, keys, fn in r124_features.commands(app):
            add(title, keys, fn, "Science & Live")
    except Exception:
        pass
    try:
        from PyQt6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w is not app and w.windowTitle():
                add(f"Window: {w.windowTitle()}", "", (lambda w=w: (w.raise_(), w.activateWindow())), "Windows")
    except Exception:
        pass
    try:  # every visible button in every window (the former accessibility palette's source)
        from PyQt6.QtWidgets import QApplication, QAbstractButton
        for top in QApplication.topLevelWidgets():
            if not top.isVisible() or top.property("grooveboxTouchKeyboard"):
                continue
            for b in top.findChildren(QAbstractButton):
                try:
                    t = (b.text() or b.toolTip() or "").strip().replace("&", "").replace("\n", " ")
                    if t and b.isVisible() and b.isEnabled():
                        add(t[:90], b.shortcut().toString() if hasattr(b, "shortcut") else "", b.click,
                            "Button · " + (top.windowTitle() or "main")[:40])
                except RuntimeError:
                    pass
    except Exception:
        pass
    for a in app.findChildren(QAction):
        if a.shortcut().toString() and a.text():
            add(a.text(), a.shortcut().toString(), a.trigger, "Shortcuts")
    return out


def match(items, query):
    words = [w for w in query.lower().split() if w]
    if not words:
        return items
    scored = []
    for it in items:
        hay = f"{it['title']} {it['keys']} {it['group']}".lower()
        if all(w in hay for w in words):
            score = (0 if it["title"].lower().startswith(words[0]) else 1, len(it["title"]))
            scored.append((score, it))
    return [it for _s, it in sorted(scored, key=lambda p: p[0])]


def show(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel
    dlg = getattr(app, "_r124_palette", None)
    if dlg is None:
        dlg = QDialog(app); dlg.setWindowTitle("Command palette"); dlg.setProperty("gb_no_auto_scroll", True)
        dlg.resize(760, 520)
        v = QVBoxLayout(dlg)
        edit = QLineEdit(); edit.setPlaceholderText("Type a command, window or setting…  (Enter runs · Esc closes)")
        lst = QListWidget(); hint = QLabel(""); hint.setStyleSheet("color:#8fa6bc;")
        v.addWidget(edit); v.addWidget(lst, 1); v.addWidget(hint)
        dlg._edit, dlg._list, dlg._hint = edit, lst, hint

        def refill():
            lst.clear()
            rows = match(dlg._items, edit.text())[:300]
            for it in rows:
                li = QListWidgetItem(f"{it['title']}" + (f"      [{it['keys']}]" if it["keys"] else "") + f"      · {it['group']}")
                li.setData(Qt.ItemDataRole.UserRole, it); lst.addItem(li)
            if lst.count():
                lst.setCurrentRow(0)
            hint.setText(f"{lst.count()} of {len(dlg._items)} commands")

        def run(item=None):
            item = item or lst.currentItem()
            if item is None:
                return
            it = item.data(Qt.ItemDataRole.UserRole); dlg.hide()
            try:
                it["fn"]()
            except Exception as exc:
                print(f"[palette] {it['title']}: {exc}")

        def keys(ev, base=edit.keyPressEvent):
            k = ev.key()
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                r = lst.currentRow() + (1 if k == Qt.Key.Key_Down else -1)
                lst.setCurrentRow(max(0, min(lst.count() - 1, r))); return
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                run(); return
            base(ev)
        edit.keyPressEvent = keys
        edit.textChanged.connect(lambda _t: refill())
        lst.itemActivated.connect(run)
        dlg._refill = refill
        app._r124_palette = dlg
    dlg._items = entries(app)
    dlg._edit.clear(); dlg._refill()
    dlg.show(); dlg.raise_(); dlg.activateWindow(); dlg._edit.setFocus()
    return dlg
