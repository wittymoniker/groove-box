import sys
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from main_window import MainWindow

class SynthVoiceChannel(QObject):
    parameter_changed = pyqtSignal(str, float)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.local_volume = 1.0
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

    def process_audio(self, buffer: np.ndarray) -> np.ndarray:
        output = buffer.copy() * self.local_volume
        if self.sidechain_source and self.sidechain_depth > 0:
            peak = self.sidechain_source.get_peak_level()
            ducking = max(0.0, 1.0 - (peak * self.sidechain_depth))
            output *= ducking
        return output

    def get_peak_level(self) -> float:
        return 0.85

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()

    panel_voice = SynthVoiceChannel("Panel Synth")
    geo_voice = SynthVoiceChannel("Geometric Synth")

    # Establish independent sidechain link
    geo_voice.set_sidechain_source(panel_voice)

    # Bind UI Sliders to Synth Channel Parameters
    window.panel_vol_slider.valueChanged.connect(panel_voice.set_local_volume)
    window.sidechain_slider.valueChanged.connect(geo_voice.set_sidechain_depth)

    # Log parameter updates from signal feedback
    panel_voice.parameter_changed.connect(
        lambda param, val: print(f"[{panel_voice.name}] {param} updated -> {val:.2f}")
    )
    geo_voice.parameter_changed.connect(
        lambda param, val: print(f"[{geo_voice.name}] {param} updated -> {val:.2f}")
    )

    print("Executing full UI & routing integration test...")
    window.show()
    sys.exit(app.exec())
