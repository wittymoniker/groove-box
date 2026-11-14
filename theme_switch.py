"""THEME_SWITCH_20261112: flip the color scheme without opening settings."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

SCHEMES = ["normal", "high contrast", "protan-safe", "deutan-safe", "tritan-safe", "grayscale", "warm night", "inverted"]

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Theme")
    w.setMinimumSize(240, 220)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("Color scheme. Applies immediately."))
    def apply(name):
        try:
            import compat_settings as cs
            s = cs.load(); s["color_scheme"] = name; cs.save(s)
        except Exception:
            pass
        try:
            import pathway_hub as hub
            hub.stamp(app, "theme", {"scheme": name})
        except Exception:
            pass
        try:
            import accessibility
            accessibility.apply_settings(app, {"color_scheme": name})
        except Exception:
            pass
    for name in SCHEMES:
        b = QPushButton(name)
        b.clicked.connect(lambda _=False, n=name: apply(n))
        lay.addWidget(b)
    lay.addStretch(1)
    w.show(); w.raise_()
    return w


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)
