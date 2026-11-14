"""Current seed fingerprint and the stamp on the last finished export."""
from __future__ import annotations

def open_window(app, parent=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QApplication
    win = QDialog(None)
    win.setWindowTitle("Seed inspector")
    win.resize(480, 220)
    lay = QVBoxLayout(win)
    try:
        import seed_media_bridge as smb
        pkt = smb.identity_packet(app)
        fp = str(pkt.get("fingerprint", ""))
    except Exception as exc:
        fp = "unavailable (%s)" % exc
    last = "no finished export yet"
    try:
        sch = getattr(app, "_export_scheduler_obj", None)
        done = [j for j in getattr(sch, "jobs", []) if j.state == "done"]
        if done:
            j = done[-1]
            last = "%s\n%s" % (j.label, j.result.get("file_path") or j.out_file)
    except Exception:
        pass
    lab = QLabel("fingerprint  %s\n\nlast export\n%s" % (fp, last))
    lab.setWordWrap(True)
    lay.addWidget(lab)
    b = QPushButton("Copy fingerprint")
    b.clicked.connect(lambda: QApplication.clipboard().setText(fp))
    lay.addWidget(b)
    win.show(); win.raise_(); return win


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)
