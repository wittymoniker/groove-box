import sys
import numpy as np
from qt_painting import owned_painter
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush

class ParametricVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(400, 250)
        
        # Internal state for animation and waveform data
        self.phase = 0.0
        self.waveform_data = np.zeros(200)
        
        # Setup high-refresh render timer (~60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_waveform_data(self, data: np.ndarray):
        """Update buffer data safely from the audio thread or engine."""
        if len(data) > 0:
            # Normalize and resize data to fit display bins
            self.waveform_data = np.interp(
                np.linspace(0, len(data), 200),
                np.arange(len(data)),
                data
            )

    def update_animation(self):
        # Advance phase for background parametric wave calculation
        self.phase += 0.05
        self.update()  # Trigger paintEvent

    def paintEvent(self, event):
        with owned_painter(self) as painter:
            if painter is None:
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
            width = self.width()
            height = self.height()
        
            # 1. Paint Deep Background
            painter.fillRect(0, 0, width, height, QColor(15, 15, 23))
        
            # 2. Paint Parametric Math Background Grid / Waves
            grid_pen = QPen(QColor(50, 40, 80, 120), 1, Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)
        
            step_x = width / 10
            step_y = height / 10
            for i in range(11):
                painter.drawLine(int(i * step_x), 0, int(i * step_x), height)
                painter.drawLine(0, int(i * step_y), width, int(i * step_y))
            
            # Draw dynamic parametric Lissajous / Sine wave lines
            math_pen = QPen(QColor(138, 43, 226, 180), 1.5)
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

            # 3. Paint Live Audio Waveform Overlay
            wave_pen = QPen(QColor(163, 230, 53, 220), 2)
            painter.setPen(wave_pen)
        
            if len(self.waveform_data) > 0:
                bin_width = width / len(self.waveform_data)
                for i in range(len(self.waveform_data) - 1):
                    x1 = int(i * bin_width)
                    y1 = int((height / 2) - (self.waveform_data[i] * (height / 3)))
                    x2 = int((i + 1) * bin_width)
                    y2 = int((height / 2) - (self.waveform_data[i+1] * (height / 3)))
                    painter.drawLine(x1, y1, x2, y2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Standalone test window
    win = QWidget()
    win.setWindowTitle("Parametric Visualizer Test")
    win.resize(700, 450)
    
    layout = QVBoxLayout(win)
    vis = ParametricVisualizerWidget()
    layout.addWidget(vis)
    
    # Test button to feed random oscillator data into the visualizer
    btn_layout = QHBoxLayout()
    test_btn = QPushButton("Inject Test Sine Wave")
    test_btn.setStyleSheet("background-color: #4A154B; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
    
    def inject_wave():
        t = np.linspace(0, 2 * np.pi, 200)
        noise = np.random.normal(0, 0.1, 200)
        wave = np.sin(t * 3) + noise
        vis.set_waveform_data(wave)
        
    test_btn.clicked.connect(inject_wave)
    btn_layout.addWidget(test_btn)
    layout.addLayout(btn_layout)
    
    win.show()
    sys.exit(app.exec())
