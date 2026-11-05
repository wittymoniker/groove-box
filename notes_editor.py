"""Notes & diary editor for Mathematician's Groovebox.

GROOVEBOX_R23R_NOTES_EDITOR_20261101

Plain-text notes (.txt / .md) live in <Groovebox data>/notes as ordinary files,
so they can be opened, backed up or shared (Nearby) like anything else on the
file system. Deleting moves a note to notes/.trash (restorable); nothing is
erased without a second, explicit "Empty trash".
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
                             QVBoxLayout, QWidget)

NOTE_EXT = (".txt", ".md")


def notes_dir() -> Path:
    try:
        import groovebox_paths
        root = Path(groovebox_paths.base_dir())
    except Exception:
        root = Path.home() / ".groovebox"
    d = root / "notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_title(title: str) -> str:
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(title or "")).strip().strip(".")
    return (t or "Untitled")[:120]


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, ext = path.stem, path.suffix
    n = 2
    while True:
        cand = path.with_name(f"{stem} ({n}){ext}")
        if not cand.exists():
            return cand
        n += 1


class NotesWidget(QWidget):
    """List + editor. Autosaves 1.5 s after typing stops, on switching notes and on close."""

    def __init__(self, parent=None, folder=None):
        super().__init__(parent)
        self.folder = Path(folder) if folder else notes_dir()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.current: Path | None = None
        self._dirty = False
        self._loading = False
        root = QHBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(split)

        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search notes…")
        self.search.textChanged.connect(self.reload)
        lv.addWidget(self.search)
        self.list = QListWidget(); self.list.currentItemChanged.connect(self._open_selected)
        lv.addWidget(self.list, 1)
        r1 = QHBoxLayout()
        for text, fn, tip in (("＋ Note", self.new_note, "New blank note"),
                              ("📅 Diary", self.new_diary, "New diary entry for today"),
                              ("Rename", self.rename_note, "Rename the selected note"),
                              ("Delete", self.delete_note, "Move the selected note to notes/.trash")):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(fn); r1.addWidget(b)
        lv.addLayout(r1)
        r2 = QHBoxLayout()
        b = QPushButton("Restore…"); b.setToolTip("Restore a note from the trash"); b.clicked.connect(self.restore_note); r2.addWidget(b)
        b = QPushButton("Empty trash"); b.clicked.connect(self.empty_trash); r2.addWidget(b)
        lv.addLayout(r2)
        self.lbl_folder = QLabel(str(self.folder)); self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setStyleSheet("color:#7f93a6; font-size:8pt;")
        self.lbl_folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lv.addWidget(self.lbl_folder)
        split.addWidget(left)

        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.lbl_title = QLabel("No note selected"); self.lbl_title.setStyleSheet("font-weight:700; font-size:11pt;")
        top.addWidget(self.lbl_title, 1)
        b = QPushButton("🕒 Insert time"); b.clicked.connect(self.insert_time); top.addWidget(b)
        self.btn_save = QPushButton("💾 Save"); self.btn_save.clicked.connect(self.save); top.addWidget(self.btn_save)
        rv.addLayout(top)
        self.editor = QPlainTextEdit(); self.editor.setPlaceholderText("Select or create a note…")
        f = QFont("monospace"); f.setStyleHint(QFont.StyleHint.Monospace); f.setPointSize(11)
        self.editor.setFont(f)
        self.editor.setEnabled(False)
        self.editor.textChanged.connect(self._changed)
        rv.addWidget(self.editor, 1)
        self.lbl_status = QLabel(""); self.lbl_status.setStyleSheet("color:#8aa0b4;")
        rv.addWidget(self.lbl_status)
        split.addWidget(right)
        split.setSizes([260, 640])

        self._autosave = QTimer(self); self._autosave.setSingleShot(True); self._autosave.setInterval(1500)
        self._autosave.timeout.connect(self.save)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_note)
        self.reload()

    # ------------------------------------------------------------------ files
    def _files(self):
        q = self.search.text().strip().casefold()
        rows = []
        for p in self.folder.iterdir():
            if not p.is_file() or p.suffix.lower() not in NOTE_EXT:
                continue
            if q:
                try:
                    hay = (p.stem + "\n" + p.read_text(encoding="utf-8", errors="replace")).casefold()
                except Exception:
                    hay = p.stem.casefold()
                if q not in hay:
                    continue
            rows.append(p)
        return sorted(rows, key=lambda p: p.stat().st_mtime, reverse=True)

    def reload(self, *_a):
        keep = self.current
        self.list.blockSignals(True)
        self.list.clear()
        sel = None
        for p in self._files():
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
            it = QListWidgetItem(f"{p.stem}\n{when}")
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            self.list.addItem(it)
            if keep is not None and p == keep:
                sel = it
        self.list.blockSignals(False)
        if sel is not None:
            self.list.setCurrentItem(sel)
        elif self.current is None and self.list.count():
            self.list.setCurrentRow(0)

    def _open_selected(self, item, _prev=None):
        if self._dirty:
            self.save()
        if item is None:
            return
        self.open_path(Path(item.data(Qt.ItemDataRole.UserRole)))

    def open_path(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            QMessageBox.warning(self, "Notes", f"Could not open {path.name}: {e}")
            return
        self._loading = True
        self.current = path
        self.editor.setEnabled(True)
        self.editor.setPlainText(text)
        self._loading = False
        self._dirty = False
        self.lbl_title.setText(path.stem)
        self._update_status("Opened")

    def _changed(self):
        if self._loading or self.current is None:
            return
        self._dirty = True
        self._update_status("Editing…")
        self._autosave.start()

    def _update_status(self, prefix=""):
        text = self.editor.toPlainText()
        words = len(text.split())
        self.lbl_status.setText(f"{prefix} · {words} words · {len(text)} characters"
                                + (f" · {self.current.name}" if self.current else ""))

    def save(self):
        if self.current is None or not self._dirty:
            return True
        try:
            tmp = self.current.with_name(self.current.name + ".tmp")
            tmp.write_text(self.editor.toPlainText(), encoding="utf-8")
            os.replace(tmp, self.current)
            self._dirty = False
            self._update_status("Saved " + time.strftime("%H:%M:%S"))
            return True
        except Exception as e:
            QMessageBox.warning(self, "Notes", f"Save failed: {e}")
            return False

    # ---------------------------------------------------------------- actions
    def _create(self, title, body=""):
        self.save()
        path = _unique(self.folder / (_safe_title(title) + ".md"))
        path.write_text(body, encoding="utf-8")
        self.current = path
        self.search.blockSignals(True); self.search.clear(); self.search.blockSignals(False)
        self.reload()
        self.editor.setFocus()
        cur = self.editor.textCursor(); cur.movePosition(cur.MoveOperation.End); self.editor.setTextCursor(cur)
        return path

    def new_note(self):
        title, ok = QInputDialog.getText(self, "New note", "Title:", text="Untitled")
        if ok:
            self._create(title)

    def new_diary(self):
        day = time.strftime("%Y-%m-%d")
        path = self.folder / f"{day} Diary.md"
        if path.exists():
            self.save(); self.current = path; self.reload()
            self.editor.appendPlainText(f"\n## {time.strftime('%H:%M')}\n")
        else:
            self._create(f"{day} Diary", f"# {time.strftime('%A %d %B %Y')}\n\n## {time.strftime('%H:%M')}\n")

    def insert_time(self):
        if self.current is not None:
            self.editor.insertPlainText(time.strftime("%Y-%m-%d %H:%M "))

    def rename_note(self):
        if self.current is None:
            return
        self.save()
        title, ok = QInputDialog.getText(self, "Rename note", "New title:", text=self.current.stem)
        if not ok:
            return
        new = _unique(self.current.with_name(_safe_title(title) + self.current.suffix))
        try:
            os.replace(self.current, new)
            self.current = new
            self.lbl_title.setText(new.stem)
            self.reload()
        except Exception as e:
            QMessageBox.warning(self, "Notes", f"Rename failed: {e}")

    def _trash(self) -> Path:
        t = self.folder / ".trash"; t.mkdir(exist_ok=True); return t

    def delete_note(self):
        if self.current is None:
            return
        if QMessageBox.question(self, "Delete note", f"Move “{self.current.stem}” to the notes trash?\n"
                                "You can restore it with Restore….") != QMessageBox.StandardButton.Yes:
            return
        self.save()
        try:
            shutil.move(str(self.current), str(_unique(self._trash() / self.current.name)))
        except Exception as e:
            QMessageBox.warning(self, "Notes", f"Delete failed: {e}"); return
        self.current = None; self._dirty = False
        self._loading = True; self.editor.clear(); self._loading = False
        self.editor.setEnabled(False); self.lbl_title.setText("No note selected")
        self.reload()

    def restore_note(self):
        items = sorted(p.name for p in self._trash().iterdir() if p.is_file())
        if not items:
            QMessageBox.information(self, "Restore note", "The notes trash is empty."); return
        name, ok = QInputDialog.getItem(self, "Restore note", "Note:", items, 0, False)
        if ok and name:
            dest = _unique(self.folder / name)
            shutil.move(str(self._trash() / name), str(dest))
            self.current = dest; self.reload()

    def empty_trash(self):
        files = [p for p in self._trash().iterdir() if p.is_file()]
        if not files:
            QMessageBox.information(self, "Empty trash", "The notes trash is already empty."); return
        if QMessageBox.question(self, "Empty trash", f"Permanently delete {len(files)} note(s) in the trash?") \
                != QMessageBox.StandardButton.Yes:
            return
        for p in files:
            try:
                p.unlink()
            except Exception:
                pass

    def closeEvent(self, e):
        self.save()
        super().closeEvent(e)

    def hideEvent(self, e):
        self.save()
        super().hideEvent(e)


class NotesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Groovebox Notes & Diary")
        self.resize(980, 640)
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6)
        self.notes = NotesWidget(self)
        lay.addWidget(self.notes)

    def closeEvent(self, e):
        self.notes.save()
        super().closeEvent(e)


def open_notes_dialog(parent=None):
    dlg = getattr(parent, "_gb_notes_dialog", None) if parent is not None else None
    if dlg is None:
        dlg = NotesDialog(parent)
        if parent is not None:
            parent._gb_notes_dialog = dlg
    dlg.setModal(False)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    return dlg


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
