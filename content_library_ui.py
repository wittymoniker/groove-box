"""Content Library window: non-live browse, import, edit and launch workspace."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path


def open_window(app=None):
    from PyQt6.QtCore import Qt, QUrl, QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QTimer
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
        QListWidget, QListWidgetItem, QPushButton, QFileDialog, QMessageBox, QLabel)

    class _JobSignals(QObject):
        finished = pyqtSignal(int, object)

    class _UiReceiver(QObject):
        """QObject-affine receiver: worker results are marshalled onto the GUI thread."""
        def __init__(self, callback, parent=None):
            super().__init__(parent)
            self.callback = callback

        @pyqtSlot(int, object)
        def deliver(self, generation, result):
            try:
                self.callback(generation, result)
            finally:
                self.deleteLater()

    class _LibraryJob(QRunnable):
        def __init__(self, generation, function, *args, parent=None):
            super().__init__()
            self.generation = int(generation)
            self.function = function
            self.args = args
            self.signals = _JobSignals(parent)

        def run(self):
            try:
                result = (True, self.function(*self.args))
            except Exception as exc:
                result = (False, str(exc))
            self.signals.finished.emit(self.generation, result)
    d = getattr(app, "_content_library_dialog", None) if app is not None else None
    if d is None:
        d = QDialog(app); d.setWindowTitle("Content Library · manage, create, prepare and launch")
        d.resize(1040, 680); d.setProperty("gb_no_auto_scroll", True)
        layout = QVBoxLayout(d)
        intro = QLabel("Performance is for live play. Content Library is for projects, scripts, apps, presets, samples, sequences and everything else.")
        intro.setWordWrap(True); layout.addWidget(intro)
        bar = QHBoxLayout(); layout.addLayout(bar)
        search = QLineEdit(); search.setPlaceholderText("Search content…"); bar.addWidget(search, 1)
        category = QComboBox(); category.addItems(["All", "Projects", "Scripts", "Applications", "Instruments and presets", "Samples and audio", "Patterns and sequences", "Images and graphics", "Video", "Plugins and extensions", "Documents and configuration", "Archives", "Imported files"]); bar.addWidget(category)
        listing = QListWidget(); layout.addWidget(listing, 1)
        actions = QHBoxLayout(); layout.addLayout(actions)
        refresh = QPushButton("Refresh"); imp = QPushButton("Import files / archive…")
        imp_folder = QPushButton("Import folder…")
        edit = QPushButton("Edit as text…"); open_btn = QPushButton("Open selected")
        launch_btn = QPushButton("Launch application…")
        run_btn = QPushButton("Run selected script…"); close = QPushButton("Close")
        for b in (refresh, imp, imp_folder, edit, open_btn, launch_btn, run_btn): actions.addWidget(b)
        actions.addStretch(1); actions.addWidget(close)
        d._library = {"search": search, "category": category, "list": listing}
        d._library_buttons = (refresh, imp, imp_folder, edit, open_btn, launch_btn, run_btn)
        d._library_pool = QThreadPool(d)
        d._library_pool.setMaxThreadCount(2)
        d._scan_generation = 0

        def apply_scan(generation, result):
            if int(generation) != int(d._scan_generation):
                return  # discard stale results from earlier search text/category
            ok, payload = result
            listing.clear()
            if not ok:
                listing.addItem("Index failed · " + str(payload))
                return
            for row in payload:
                item = QListWidgetItem(f"{row['category']}  ·  {row['name']}  ·  {row['size']:,} bytes")
                item.setToolTip(row["path"]); item.setData(Qt.ItemDataRole.UserRole, row)
                listing.addItem(item)
            if not payload:
                listing.addItem("No matching content.")

        def refresh_rows(*_):
            import content_library
            generation = int(d._scan_generation)
            listing.clear(); listing.addItem("Indexing content in the background…")
            job = _LibraryJob(generation, content_library.scan, search.text(), category.currentText(), parent=d)
            receiver = _UiReceiver(apply_scan, d)
            job.signals.finished.connect(receiver.deliver)
            d._library_pool.start(job)

        def schedule_refresh(*_):
            d._scan_generation += 1
            d._library_debounce.start()
        def selected():
            item = listing.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None
        def import_files():
            paths, _ = QFileDialog.getOpenFileNames(d, "Import content", str(Path.home()), "All files (*)")
            if paths:
                start_import(paths)

        def import_folder():
            folder = QFileDialog.getExistingDirectory(d, "Import a folder", str(Path.home()))
            if folder:
                start_import([folder])

        def start_import(paths):
            from groovebox_paths import base_dir
            dest = Path(base_dir()) / "imports"
            imp.setEnabled(False); imp_folder.setEnabled(False); imp.setText("Importing…")

            def do_import(selected_paths, destination):
                import os
                import shutil
                import tarfile
                import tempfile
                import zipfile
                destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
                copied = 0; errors = []
                archive_suffixes = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
                for raw in selected_paths:
                    src = Path(raw).expanduser()
                    try:
                        if src.is_symlink():
                            raise ValueError("Symbolic links are not imported.")
                        if src.is_dir():
                            target = destination / src.name
                            if target.exists(): raise FileExistsError(str(target))
                            with tempfile.TemporaryDirectory(prefix=".folder-import-", dir=str(destination)) as tmp:
                                staged = Path(tmp) / src.name
                                staged.mkdir()
                                folder_copied = 0
                                for current, dirs, files in os.walk(src, followlinks=False):
                                    current_path = Path(current)
                                    linked_dirs = [name for name in dirs if (current_path / name).is_symlink()]
                                    if linked_dirs:
                                        raise ValueError("Folder contains a symbolic-link directory: " + str(current_path / linked_dirs[0]))
                                    rel = current_path.relative_to(src)
                                    out_dir = staged / rel
                                    out_dir.mkdir(parents=True, exist_ok=True)
                                    for name in files:
                                        source_file = current_path / name
                                        if source_file.is_symlink():
                                            raise ValueError(f"Folder contains a symbolic link: {source_file}")
                                        if not source_file.is_file():
                                            continue
                                        out_file = out_dir / name
                                        shutil.copy2(source_file, out_file)
                                        folder_copied += 1
                                os.replace(staged, target)
                                copied += folder_copied
                        elif src.is_file() and (zipfile.is_zipfile(src) or tarfile.is_tarfile(src)):
                            import content_import
                            lower = src.name.lower()
                            folder_name = next((src.name[:-len(ext)] for ext in archive_suffixes if lower.endswith(ext)), src.stem)
                            if not folder_name:
                                folder_name = src.stem or "Imported archive"
                            report = content_import.import_archive(src, destination / folder_name)
                            copied += report["count"]
                        elif src.is_file():
                            target = destination / src.name
                            if target.exists(): raise FileExistsError(str(target))
                            try:
                                shutil.copy2(src, target)
                                copied += 1
                            except Exception:
                                try: target.unlink()
                                except OSError: pass
                                raise
                        else:
                            raise ValueError("Select a regular file, folder, ZIP, or TAR archive.")
                    except Exception as exc:
                        errors.append(f"{src.name}: {exc}")
                return copied, errors

            job = _LibraryJob(d._scan_generation, do_import, tuple(paths), str(dest), parent=d)
            def imported(_generation, result):
                imp.setEnabled(True); imp_folder.setEnabled(True); imp.setText("Import files / archive…")
                ok, payload = result
                if not ok:
                    QMessageBox.warning(d, "Import failed", str(payload)); return
                copied, errors = payload
                msg = f"Imported {copied} file(s). Imported scripts and applications were not executed."
                if errors: msg += "\n\n" + "\n".join(errors[:12])
                QMessageBox.information(d, "Import complete", msg)
                schedule_refresh()
            receiver = _UiReceiver(imported, d)
            job.signals.finished.connect(receiver.deliver)
            d._library_pool.start(job)
        def edit_file():
            row = selected()
            path = row["path"] if row else QFileDialog.getOpenFileName(d, "Edit text file", str(Path.home()), "All files (*)")[0]
            if not path: return
            import text_editor_ui
            text_editor_ui.open_file(path, d)
        def open_file():
            row = selected()
            if not row: return
            path = row["path"]; suffix = Path(path).suffix.lower()
            if suffix in (".mcc", ".mgpr", ".gbproj") and app is not None and hasattr(app, "open_project_path"):
                app.open_project_path(path); return
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        def launch_application():
            import shutil
            row = selected()
            if not row or row["category"] != "Applications":
                QMessageBox.information(d, "Launch application", "Select an application first.")
                return
            path = Path(row["path"])
            if QMessageBox.question(d, "Launch imported application?",
                    f"This starts the selected application as your normal desktop user:\n\n{path}\n\nOnly continue if you trust this file.") != QMessageBox.StandardButton.Yes:
                return
            try:
                suffix = path.suffix.lower()
                argv = None
                cwd = str(path.parent)
                if suffix == ".appimage":
                    if not os.access(path, os.X_OK):
                        raise PermissionError("This AppImage is not marked executable. Review its source and permissions before launching it.")
                    argv = [str(path)]
                elif suffix == ".desktop":
                    import shlex
                    raw = ""
                    desktop_cwd = ""
                    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                        if line.startswith("Exec=") and not raw:
                            raw = line.split("=", 1)[1].strip()
                        elif line.startswith("Path=") and not desktop_cwd:
                            desktop_cwd = line.split("=", 1)[1].strip()
                    if not raw:
                        raise ValueError("Desktop launcher has no Exec command.")
                    argv = [part for part in shlex.split(raw) if not (part.startswith("%") and len(part) == 2)]
                    if not argv:
                        raise ValueError("Desktop launcher has no executable command.")
                    if desktop_cwd:
                        candidate = Path(desktop_cwd).expanduser()
                        if candidate.is_dir(): cwd = str(candidate)
                elif suffix == ".exe" and os.name == "nt":
                    argv = [str(path)]
                elif suffix == ".app" and sys.platform == "darwin":
                    argv = ["open", str(path)]
                elif suffix == ".exe" and shutil.which("wine"):
                    argv = [shutil.which("wine"), str(path)]
                else:
                    raise ValueError("This application format is not directly launchable on this operating system.")
                subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=(os.name != "nt"), close_fds=(os.name != "nt"))
            except Exception as exc:
                QMessageBox.warning(d, "Launch failed", str(exc))

        def run_script():
            row = selected()
            if not row or row["category"] != "Scripts":
                QMessageBox.information(d, "Run script", "Select a script first."); return
            path = row["path"]
            if QMessageBox.question(d, "Run imported script?", f"This explicitly runs the selected program:\n\n{path}\n\nOnly continue if you trust its contents.") != QMessageBox.StandardButton.Yes: return
            try:
                if Path(path).suffix.lower() in (".py", ".pyw"):
                    subprocess.Popen([sys.executable, path], cwd=str(Path(path).parent))
                elif Path(path).suffix.lower() in (".sh", ".bash"):
                    subprocess.Popen(["/bin/sh", path], cwd=str(Path(path).parent))
                else:
                    QMessageBox.warning(d, "Run script", "This script type is not enabled for direct execution here.")
                    return
            except Exception as exc: QMessageBox.warning(d, "Run failed", str(exc))
        d._library_debounce = QTimer(d); d._library_debounce.setSingleShot(True); d._library_debounce.setInterval(180)
        d._library_debounce.timeout.connect(refresh_rows)
        refresh.clicked.connect(schedule_refresh); search.textChanged.connect(schedule_refresh); category.currentTextChanged.connect(schedule_refresh)
        imp.clicked.connect(import_files); imp_folder.clicked.connect(import_folder)
        edit.clicked.connect(edit_file); open_btn.clicked.connect(open_file)
        launch_btn.clicked.connect(launch_application); run_btn.clicked.connect(run_script)
        listing.itemDoubleClicked.connect(lambda *_: open_file()); close.clicked.connect(d.hide)
        d._refresh_library = schedule_refresh
        if app is not None: app._content_library_dialog = d
    d._refresh_library(); d.show(); d.raise_(); d.activateWindow()
    return d
