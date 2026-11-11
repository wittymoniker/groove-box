"""No window steals the user's input: every dialog is shown NON-MODAL.

GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103

Qt's exec() and the static helpers (QMessageBox.question, QFileDialog.get*,
QInputDialog.get*, QColorDialog.getColor) normally block every other window
until they close. install() replaces them, process-wide, with versions that
show the dialog non-modally and wait for its answer in a local event loop.
The calling code still receives the same return value, but the main window,
Performance, the playlist and every other window stay fully usable while a
dialog is open.

Set GROOVEBOX_MODAL_DIALOGS=1 to restore Qt's stock modal behaviour.
"""
from __future__ import annotations

import os

_INSTALLED = False


def _wait(dlg) -> int:
    """Show ``dlg`` non-modally and return its result once it closes."""
    from PyQt6.QtCore import QEventLoop, Qt
    try:
        dlg.setWindowModality(Qt.WindowModality.NonModal)
    except Exception:
        pass
    loop = QEventLoop()
    done = []

    def _quit(*_a):
        if not done:
            done.append(1)
            loop.quit()

    dlg.finished.connect(_quit)
    dlg.destroyed.connect(_quit)
    _ORIG["QWidget.show"](dlg)
    try:
        dlg.raise_(); dlg.activateWindow()
    except Exception:
        pass
    if not done:
        loop.exec()
    try:
        return int(dlg.result())
    except Exception:          # deleted while waiting (parent closed)
        return 0


_ORIG: dict = {}


def _patched_exec(self, *a, **k):
    return _wait(self)


def _patched_set_modal(self, modal):
    _ORIG["QDialog.setModal"](self, False)


def _patched_set_modality(self, modality):
    from PyQt6.QtCore import Qt
    _ORIG["QWidget.setWindowModality"](self, Qt.WindowModality.NonModal)


def _patched_open(self):
    # QDialog.open() is window-modal by definition; show it non-modally.
    from PyQt6.QtCore import Qt
    _ORIG["QWidget.setWindowModality"](self, Qt.WindowModality.NonModal)
    _ORIG["QWidget.show"](self)


# ----------------------------------------------------------------- QMessageBox
def _msgbox(icon_name, default_buttons):
    def fn(parent, title, text, buttons=None, defaultButton=None, **kw):
        from PyQt6.QtWidgets import QMessageBox
        buttons = kw.pop("buttons", buttons)
        if buttons is None:
            buttons = default_buttons()
        box = QMessageBox(getattr(QMessageBox.Icon, icon_name), str(title or ""), str(text or ""), buttons, parent)
        if defaultButton is not None:
            try:
                box.setDefaultButton(defaultButton)
            except Exception:
                pass
        _wait(box)
        try:
            clicked = box.clickedButton()
            if clicked is None:
                clicked = box.escapeButton()
            if clicked is None:
                return QMessageBox.StandardButton.NoButton
            sb = box.standardButton(clicked)
            try:
                return QMessageBox.StandardButton(int(getattr(sb, "value", sb)))
            except Exception:
                return sb
        except Exception:
            return QMessageBox.StandardButton.NoButton
    return staticmethod(fn)


def _about(parent, title, text):
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(QMessageBox.Icon.Information, str(title or ""), str(text or ""),
                      QMessageBox.StandardButton.Ok, parent)
    _wait(box)


# ----------------------------------------------------------------- QFileDialog
class _HideSystemProxy(object):
    """Built lazily (QSortFilterProxyModel) — hides Groovebox system files/folders."""
    _cls = None

    @classmethod
    def make(cls, dlg):
        if cls._cls is None:
            from PyQt6.QtCore import QSortFilterProxyModel

            class _P(QSortFilterProxyModel):
                """R32.9: hide Groovebox system entries ONLY inside the folder being shown. Qt also runs the filter
                on every ancestor of the current path (/, /run, /run/media …); hiding one of those made whole trees
                — including USB / SD drives under /run/media — vanish from the dialog. Results are cached so slow
                drives are not re-resolved on every repaint."""
                _cache = {}

                def filterAcceptsRow(self, row, parent):
                    try:
                        src = self.sourceModel()
                        idx = src.index(row, 0, parent)
                        path = src.filePath(idx)
                        dlg_ = self.parent()
                        cur = dlg_.directory().absolutePath() if dlg_ is not None else ""
                        if os.path.dirname(os.path.normpath(path)) != os.path.normpath(cur):
                            return True                              # an ancestor / sibling tree: never hidden
                        hit = self._cache.get(path)
                        if hit is None:
                            import groovebox_paths as _gp
                            hit = self._cache[path] = not _gp.is_system_path(path)
                            if len(self._cache) > 20000:
                                self._cache.clear()
                        return hit
                    except Exception:
                        return True
            cls._cls = _P
        p = cls._cls(dlg)
        try:   # re-filter when the user changes folder (the "current folder" rule depends on it)
            dlg.directoryEntered.connect(lambda *_a, _p=p: _p.invalidateFilter())
        except Exception:
            pass
        return p


def _file_dialog(parent, caption, directory, flt, selected, options, mode, accept):
    from PyQt6.QtWidgets import QFileDialog
    from PyQt6.QtCore import QUrl
    # GROOVEBOX_R23R_HIDE_SYSTEM_FILES_20261103: purpose-based default folders,
    # remembered per purpose, sidebar shortcuts, system files hidden.
    _kind = "any"
    try:
        import groovebox_paths as _gp
        _saving = accept == QFileDialog.AcceptMode.AcceptSave
        _kind = _gp.dialog_kind_for(caption, flt, _saving)
        _dir = str(directory or "")
        if not _dir or not (os.path.isdir(_dir) or os.path.isdir(os.path.dirname(_dir) or "/nonexistent")):
            _dir = os.path.join(_gp.default_dir(_kind), os.path.basename(_dir)) if _dir else _gp.default_dir(_kind)
        elif os.path.isdir(_dir) and _gp.is_system_path(_dir):
            _dir = _gp.default_dir(_kind)
        directory = _dir
    except Exception:
        _gp = None
    dlg = QFileDialog(parent, str(caption or ""), str(directory or ""), str(flt or ""))
    if _gp is not None:
        try:
            dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dlg.setProxyModel(_HideSystemProxy.make(dlg))
            _side = [p for _l, p in _gp.user_places() if os.path.isdir(p)]
            # GROOVEBOX_R23R_DIALOG_DRIVES_20261103: this dialog replaces drive_targets' wrapper,
            # so it lists the connected USB / SD drives itself (Save / Open / Export to a stick).
            try:
                import drive_targets as _dt
                _side += [str(r.get("path")) for r in _dt.removable_drives()
                          if r.get("path") and os.path.isdir(str(r.get("path"))) and str(r.get("path")) not in _side]
            except Exception:
                pass
            dlg.setSidebarUrls([QUrl.fromLocalFile(p) for p in _side])
        except Exception:
            pass
    dlg.setFileMode(mode)
    dlg.setAcceptMode(accept)
    try:
        if options is not None:
            dlg.setOptions(options)
    except Exception:
        pass
    if selected:
        try:
            dlg.selectNameFilter(selected)
        except Exception:
            pass
    if accept == QFileDialog.AcceptMode.AcceptSave and directory and not os.path.isdir(str(directory)):
        try:
            dlg.selectFile(os.path.basename(str(directory)))
        except Exception:
            pass
    ok = _wait(dlg)
    try:
        files = list(dlg.selectedFiles()) if ok else []
        if files and _gp is not None:
            _gp.remember_dir(_kind, files[0])
        return files, (dlg.selectedNameFilter() if ok else "")
    except Exception:
        return [], ""


def _fd_args(a, k):
    names = ("parent", "caption", "directory", "filter", "initialFilter", "options")
    v = dict(zip(names, a))
    v.update(k)
    if "selectedFilter" in v:
        v.setdefault("initialFilter", v.pop("selectedFilter"))
    return (v.get("parent"), v.get("caption", ""), v.get("directory", ""), v.get("filter", ""),
            v.get("initialFilter", ""), v.get("options"))


def _get_open(*a, **k):
    from PyQt6.QtWidgets import QFileDialog
    files, f = _file_dialog(*_fd_args(a, k), QFileDialog.FileMode.ExistingFile, QFileDialog.AcceptMode.AcceptOpen)
    return (files[0] if files else ""), f


def _get_opens(*a, **k):
    from PyQt6.QtWidgets import QFileDialog
    files, f = _file_dialog(*_fd_args(a, k), QFileDialog.FileMode.ExistingFiles, QFileDialog.AcceptMode.AcceptOpen)
    return files, f


def _get_save(*a, **k):
    from PyQt6.QtWidgets import QFileDialog
    files, f = _file_dialog(*_fd_args(a, k), QFileDialog.FileMode.AnyFile, QFileDialog.AcceptMode.AcceptSave)
    return (files[0] if files else ""), f


def _get_dir(*a, **k):
    from PyQt6.QtWidgets import QFileDialog
    names = ("parent", "caption", "directory", "options")
    v = dict(zip(names, a)); v.update(k)
    opts = v.get("options")
    if opts is None:
        opts = QFileDialog.Option.ShowDirsOnly
    files, _f = _file_dialog(v.get("parent"), v.get("caption", ""), v.get("directory", ""), "", "", opts,
                             QFileDialog.FileMode.Directory, QFileDialog.AcceptMode.AcceptOpen)
    return files[0] if files else ""


# ---------------------------------------------------------------- QInputDialog
def _input(parent, title, label):
    from PyQt6.QtWidgets import QInputDialog
    d = QInputDialog(parent)
    d.setWindowTitle(str(title or "")); d.setLabelText(str(label or ""))
    return d


def _get_text(*a, **k):
    from PyQt6.QtWidgets import QInputDialog, QLineEdit
    v = dict(zip(("parent", "title", "label", "echo", "text"), a)); v.update(k)
    d = _input(v.get("parent"), v.get("title"), v.get("label"))
    d.setInputMode(QInputDialog.InputMode.TextInput)
    d.setTextEchoMode(v.get("echo") or v.get("mode") or QLineEdit.EchoMode.Normal)
    d.setTextValue(str(v.get("text") or ""))
    ok = bool(_wait(d))
    return (d.textValue() if ok else ""), ok


def _get_multiline(*a, **k):
    from PyQt6.QtWidgets import QInputDialog
    v = dict(zip(("parent", "title", "label", "text"), a)); v.update(k)
    d = _input(v.get("parent"), v.get("title"), v.get("label"))
    d.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput, True)
    d.setTextValue(str(v.get("text") or ""))
    ok = bool(_wait(d))
    return (d.textValue() if ok else ""), ok


def _get_int(*a, **k):
    from PyQt6.QtWidgets import QInputDialog
    v = dict(zip(("parent", "title", "label", "value", "min", "max", "step"), a)); v.update(k)
    d = _input(v.get("parent"), v.get("title"), v.get("label"))
    d.setInputMode(QInputDialog.InputMode.IntInput)
    d.setIntRange(int(v.get("min", -2147483647)), int(v.get("max", 2147483647)))
    d.setIntStep(int(v.get("step", 1))); d.setIntValue(int(v.get("value", 0)))
    ok = bool(_wait(d))
    return (d.intValue() if ok else int(v.get("value", 0))), ok


def _get_double(*a, **k):
    from PyQt6.QtWidgets import QInputDialog
    v = dict(zip(("parent", "title", "label", "value", "min", "max", "decimals"), a)); v.update(k)
    d = _input(v.get("parent"), v.get("title"), v.get("label"))
    d.setInputMode(QInputDialog.InputMode.DoubleInput)
    d.setDoubleDecimals(int(v.get("decimals", 1)))
    d.setDoubleRange(float(v.get("min", -2147483647.0)), float(v.get("max", 2147483647.0)))
    if "step" in v:
        try:
            d.setDoubleStep(float(v["step"]))
        except Exception:
            pass
    d.setDoubleValue(float(v.get("value", 0.0)))
    ok = bool(_wait(d))
    return (d.doubleValue() if ok else float(v.get("value", 0.0))), ok


def _get_item(*a, **k):
    v = dict(zip(("parent", "title", "label", "items", "current", "editable"), a)); v.update(k)
    items = [str(x) for x in (v.get("items") or [])]
    d = _input(v.get("parent"), v.get("title"), v.get("label"))
    d.setComboBoxItems(items)
    d.setComboBoxEditable(bool(v.get("editable", True)))
    cur = int(v.get("current", 0) or 0)
    if items:
        d.setTextValue(items[max(0, min(cur, len(items) - 1))])
    ok = bool(_wait(d))
    return (d.textValue() if ok else (items[cur] if 0 <= cur < len(items) else "")), ok


# ---------------------------------------------------------------- QColorDialog
def _get_color(*a, **k):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QColorDialog
    v = dict(zip(("initial", "parent", "title", "options"), a)); v.update(k)
    d = QColorDialog(QColor(v.get("initial") or QColor(255, 255, 255)), v.get("parent"))
    if v.get("title"):
        d.setWindowTitle(str(v["title"]))
    if v.get("options") is not None:
        try:
            d.setOptions(v["options"])
        except Exception:
            pass
    ok = _wait(d)
    return d.selectedColor() if ok else QColor()


def install() -> bool:
    """Patch Qt process-wide. Safe to call more than once."""
    global _INSTALLED
    if _INSTALLED:
        return True
    if os.environ.get("GROOVEBOX_MODAL_DIALOGS", "").strip() in {"1", "true", "yes"}:
        return False
    from PyQt6.QtWidgets import (QColorDialog, QDialog, QFileDialog, QInputDialog, QMessageBox, QProgressDialog,
                                 QWidget)
    _ORIG["QWidget.show"] = QWidget.show
    _ORIG["QDialog.setModal"] = QDialog.setModal
    _ORIG["QWidget.setWindowModality"] = QWidget.setWindowModality
    for cls in (QDialog, QMessageBox, QFileDialog, QInputDialog, QColorDialog, QProgressDialog):
        cls.exec = _patched_exec
        cls.exec_ = _patched_exec
        cls.open = _patched_open
    QDialog.setModal = _patched_set_modal
    QWidget.setWindowModality = _patched_set_modality
    QMessageBox.information = _msgbox("Information", lambda: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = _msgbox("Warning", lambda: QMessageBox.StandardButton.Ok)
    QMessageBox.critical = _msgbox("Critical", lambda: QMessageBox.StandardButton.Ok)
    QMessageBox.question = _msgbox("Question", lambda: QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    QMessageBox.about = staticmethod(_about)
    QFileDialog.getOpenFileName = staticmethod(_get_open)
    QFileDialog.getOpenFileNames = staticmethod(_get_opens)
    QFileDialog.getSaveFileName = staticmethod(_get_save)
    QFileDialog.getExistingDirectory = staticmethod(_get_dir)
    QInputDialog.getText = staticmethod(_get_text)
    QInputDialog.getMultiLineText = staticmethod(_get_multiline)
    QInputDialog.getInt = staticmethod(_get_int)
    QInputDialog.getDouble = staticmethod(_get_double)
    QInputDialog.getItem = staticmethod(_get_item)
    QColorDialog.getColor = staticmethod(_get_color)
    _INSTALLED = True
    return True
