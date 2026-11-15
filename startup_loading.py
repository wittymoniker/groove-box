"""Minimal staged startup splash; does not move application construction off Qt's UI thread."""
from __future__ import annotations

import os


def show_startup_loading(app):
    """Show a small splash progress window. Set GROOVEBOX_NO_STARTUP_LOADING=1 to disable."""
    if os.environ.get("GROOVEBOX_NO_STARTUP_LOADING", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    current = getattr(app, "_groovebox_startup_splash", None)
    if current is not None:
        return current
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

        class _Splash(QWidget):
            def __init__(self):
                super().__init__(None, Qt.WindowType.SplashScreen |
                                 Qt.WindowType.FramelessWindowHint |
                                 Qt.WindowType.WindowStaysOnTopHint)
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                self.setFixedSize(440, 146)
                self.setStyleSheet(
                    "QWidget{background:#101a2b;color:#eaf2ff;border:1px solid #37577c;border-radius:10px;}"
                    "QLabel{border:0;color:#dceaff;}"
                    "QProgressBar{border:1px solid #496b91;border-radius:5px;text-align:center;"
                    "background:#17263a;color:#eaf2ff;height:18px;}"
                    "QProgressBar::chunk{background:#49b6a0;border-radius:4px;}"
                )
                layout = QVBoxLayout(self)
                layout.setContentsMargins(22, 18, 22, 16)
                title = QLabel("MATGROOVEBOX")
                title.setStyleSheet("font-size:18px;font-weight:900;letter-spacing:2px;")
                self.detail = QLabel("Preparing application runtime…")
                self.detail.setStyleSheet("font-size:11px;color:#a9c0dd;")
                self.bar = QProgressBar(self)
                self.bar.setRange(0, 100)
                self.bar.setValue(4)
                layout.addWidget(title)
                layout.addWidget(self.detail)
                layout.addWidget(self.bar)
                screen = app.primaryScreen()
                if screen is not None:
                    geom = screen.availableGeometry()
                    self.move(geom.center().x() - self.width() // 2,
                              geom.center().y() - self.height() // 2)

            def set_stage(self, value, message):
                self.bar.setValue(max(0, min(100, int(value))))
                self.detail.setText(str(message))
                # repaint() paints this single splash synchronously and avoids
                # processEvents() re-entering startup QTimers during __init__.
                self.repaint()

        splash = _Splash()
        app._groovebox_startup_splash = splash
        splash.show()
        splash.raise_()
        splash.repaint()
        app.processEvents()
        return splash
    except Exception as exc:
        try:
            print(f"[StartupLoading] splash unavailable: {exc}")
        except Exception:
            pass
        return None


def update_startup_loading(app, value: int, message: str) -> None:
    splash = getattr(app, "_groovebox_startup_splash", None) if app is not None else None
    if splash is None:
        return
    try:
        splash.set_stage(value, message)
    except Exception:
        pass


def close_startup_loading(app) -> None:
    splash = getattr(app, "_groovebox_startup_splash", None) if app is not None else None
    if splash is None:
        return
    try:
        splash.set_stage(100, "Startup interface ready")
        splash.close()
        splash.deleteLater()
    except Exception:
        pass
    try:
        delattr(app, "_groovebox_startup_splash")
    except Exception:
        pass
