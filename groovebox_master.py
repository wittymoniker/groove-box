import sys
import json
import os
import numpy as np
from qt_painting import owned_painter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFrame, QLabel, QSlider, QGroupBox, QMenuBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QPen, QColor, QAction

# --- 1. Parametric Visualizer Component ---
class ParametricVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(400, 180)
        
        self.phase = 0.0
        self.waveform_data = np.zeros(200)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16) # ~60 FPS

    def set_waveform_data(self, data: np.ndarray):
        if len(data) > 0:
            self.waveform_data = np.interp(
                np.linspace(0, len(data), 200),
                np.arange(len(data)),
                data
            )

    def update_animation(self):
        self.phase += 0.05
        self.update()

    def paintEvent(self, event):
        with owned_painter(self) as painter:
            if painter is None:
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
            width = self.width()
            height = self.height()
        
            # Deep Background Fill
            painter.fillRect(0, 0, width, height, QColor(25, 20, 35))
        
            # Parametric Grid Lines
            grid_pen = QPen(QColor(80, 50, 120, 100), 1, Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)
            step_x, step_y = width / 10, height / 10
            for i in range(11):
                painter.drawLine(int(i * step_x), 0, int(i * step_x), height)
                painter.drawLine(0, int(i * step_y), width, int(i * step_y))
            
            # Parametric Waveform Waves
            math_pen = QPen(QColor(186, 85, 211, 200), 1.5)
            painter.setPen(math_pen)
            path_points = []
            for x_idx in range(width):
                nx = x_idx / width * 4 * np.pi
                ny = height / 2 + (height / 4) * np.sin(nx + self.phase) * np.cos(nx * 0.5 - self.phase * 0.3)
                path_points.append((x_idx, ny))
            
            for i in range(len(path_points) - 1):
                painter.drawLine(
                    int(path_points[i][0]), int(path_points[i][1]),
                    int(path_points[i+1][0]), int(path_points[i+1][1])
                )

            # Live Audio Buffer Overlay
            wave_pen = QPen(QColor(163, 230, 53, 230), 2)
            painter.setPen(wave_pen)
            if len(self.waveform_data) > 0:
                bin_width = width / len(self.waveform_data)
                for i in range(len(self.waveform_data) - 1):
                    x1 = int(i * bin_width)
                    y1 = int((height / 2) - (self.waveform_data[i] * (height / 3)))
                    x2 = int((i + 1) * bin_width)
                    y2 = int((height / 2) - (self.waveform_data[i+1] * (height / 3)))
                    painter.drawLine(x1, y1, x2, y2)

# --- 2. Synth Voice Channel & Routing Logic ---
class SynthVoiceChannel(QObject):
    parameter_changed = pyqtSignal(str, float)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.local_volume = 0.8
        self.sidechain_source = None
        self.sidechain_depth = 0.0
        self.eq_params = {"low": 0.0, "mid": 0.0, "high": 0.0}

    def set_local_volume(self, val_int: int):
        self.local_volume = val_int / 100.0
        self.parameter_changed.emit("volume", self.local_volume)

    def set_sidechain_depth(self, val_int: int):
        self.sidechain_depth = val_int / 100.0
        self.parameter_changed.emit("sidechain_depth", self.sidechain_depth)

    def set_sidechain_source(self, source_channel):
        self.sidechain_source = source_channel

    def get_peak_level(self) -> float:
        return 0.75

# --- 3. Master Application Window ---
class GrooveboxMasterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Groovebox Experimental Synth Suite (Fedora Linux)")
        self.resize(1000, 750)

        # Initialize Channels
        self.channels = {
            "PanelSynth": SynthVoiceChannel("Panel Synth"),
            "GeometricSynth": SynthVoiceChannel("Geometric Synth")
        }
        self.channels["GeometricSynth"].set_sidechain_source(self.channels["PanelSynth"])

        self.init_ui()
        self.setup_menus()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # --- Purple Top Pane (Global DJ Controls & Visualizer) ---
        self.purple_top_pane = QFrame()
        self.purple_top_pane.setObjectName("PurpleTopPane")
        self.purple_top_pane.setStyleSheet("""
            #PurpleTopPane {
                background-color: #4A154B;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel { color: #FFFFFF; font-weight: bold; }
        """)
        top_layout = QVBoxLayout(self.purple_top_pane)
        top_layout.addWidget(QLabel("Global DJ Panel & Real-Time Signal Visualizer"))
        
        # Embed Visualizer inside Top Pane
        self.visualizer = ParametricVisualizerWidget()
        top_layout.addWidget(self.visualizer)
        main_layout.addWidget(self.purple_top_pane, stretch=3)

        # --- Green Container (Synth Settings & Routing) ---
        self.green_container = QFrame()
        self.green_container.setObjectName("GreenContainer")
        self.green_container.setStyleSheet("""
            #GreenContainer {
                background-color: #143D23;
                border-radius: 12px;
                padding: 12px;
            }
            QGroupBox {
                color: #A3E635; font-weight: bold; font-size: 13px;
                border: 1px solid #2E8B57; border-radius: 8px; margin-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLabel { color: #E2E8F0; }
        """)
        green_layout = QHBoxLayout(self.green_container)

        # Panel Synth Box
        panel_box = QGroupBox("Panel Synth Controls")
        panel_layout = QVBoxLayout(panel_box)
        self.panel_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.panel_vol_slider.setRange(0, 100)
        self.panel_vol_slider.setValue(80)
        panel_layout.addWidget(QLabel("Local Volume"))
        panel_layout.addWidget(self.panel_vol_slider)
        green_layout.addWidget(panel_box)

        # Geometric Synth Box
        geo_box = QGroupBox("Geometric Synth Controls")
        geo_layout = QVBoxLayout(geo_box)
        self.sidechain_slider = QSlider(Qt.Orientation.Horizontal)
        self.sidechain_slider.setRange(0, 100)
        self.sidechain_slider.setValue(50)
        geo_layout.addWidget(QLabel("Independent Sidechain Depth"))
        geo_layout.addWidget(self.sidechain_slider)
        green_layout.addWidget(geo_box)

        main_layout.addWidget(self.green_container, stretch=2)

        # Connect Sliders to Channels
        self.panel_vol_slider.valueChanged.connect(self.channels["PanelSynth"].set_local_volume)
        self.sidechain_slider.valueChanged.connect(self.channels["GeometricSynth"].set_sidechain_depth)

        # Demo Timer to feed random wave packets into visualizer
        self.audio_demo_timer = QTimer(self)
        self.audio_demo_timer.timeout.connect(self.feed_demo_audio)
        self.audio_demo_timer.start(50)

    def feed_demo_audio(self):
        t = np.linspace(0, 2 * np.pi, 200)
        wave = np.sin(t * 4 + np.random.uniform(0, 1)) * 0.7 + np.random.normal(0, 0.05, 200)
        self.visualizer.set_waveform_data(wave)

    def setup_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Project")

        save_action = QAction("&Save Project...", self)
        save_action.triggered.connect(self.save_project_file)
        file_menu.addAction(save_action)

        load_action = QAction("&Load Project...", self)
        load_action.triggered.connect(self.load_project_file)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def save_project_file(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filepath:
            data = {
                "version": "1.0",
                "channels": {
                    name: {
                        "local_volume": ch.local_volume,
                        "sidechain_depth": ch.sidechain_depth,
                        "eq_params": ch.eq_params
                    } for name, ch in self.channels.items()
                }
            }
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Success", f"Project successfully saved to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def load_project_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                ch_data = data.get("channels", {})
                if "PanelSynth" in ch_data:
                    vol = ch_data["PanelSynth"].get("local_volume", 0.8) * 100
                    self.panel_vol_slider.setValue(int(vol))
                if "GeometricSynth" in ch_data:
                    depth = ch_data["GeometricSynth"].get("sidechain_depth", 0.5) * 100
                    self.sidechain_slider.setValue(int(depth))
                    
                QMessageBox.information(self, "Success", f"Project loaded from:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GrooveboxMasterWindow()
    window.show()
    sys.exit(app.exec())
