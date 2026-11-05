# GROOVEBOX_V35_22ZZ_R23P_BOOT_HARDWARE_INIT_20261004
# GROOVEBOX_V35_22ZZ_R23L_FIXED_PERFORMANCE_DEVICES_SOF_SDMMC_20261003
# GROOVEBOX_V35_22ZZ_R23J_UNIVERSAL_AUDIO_MIC_WATCHDOG_20261003
# GROOVEBOX_V35_22ZZ_R23H_LINKED_HARDWARE_VOLUME_20261002
"""Small linked sOS hardware-volume control.

The sOS helper owns the real ALSA + PipeWire/Pulse state.  UI instances only
write through that helper and read its tiny state file, so Main and Performance
stay synchronized with Dell media-key changes without polling hardware.
"""
from __future__ import annotations
import os, subprocess, time
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider

STATE_PATH = Path(os.environ.get('GROOVEBOX_HARDWARE_VOLUME_STATE','/var/lib/groovebox/hardware-volume.state'))
HELPER = os.environ.get('GROOVEBOX_HARDWARE_VOLUME_HELPER','/usr/bin/sos-hardware-volume')

def read_hardware_volume_state():
    state={'volume':72,'muted':False,'card':'','control':''}
    try:
        for line in STATE_PATH.read_text(errors='replace').splitlines():
            if '=' not in line: continue
            k,v=line.split('=',1); k=k.strip(); v=v.strip()
            if k=='volume': state['volume']=max(0,min(100,int(float(v))))
            elif k=='muted': state['muted']=v.lower() in ('1','yes','true','on')
            elif k in ('card','control'): state[k]=v
    except Exception:
        pass
    return state

def request_hardware_volume(action, value=None):
    if not (os.path.isfile(HELPER) and os.access(HELPER,os.X_OK)):
        return False
    cmd=[HELPER,str(action)]
    if value is not None: cmd.append(str(int(value)))
    try:
        subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return True
    except Exception:
        return False

class HardwareVolumeWidget(QWidget):
    """Compact hardware-backed volume control shared by Main/Performance."""
    _late_sync_scheduled = False
    def __init__(self,parent=None,compact=True):
        super().__init__(parent)
        self._syncing=False
        self._pending_value=None
        self._pending_until=0.0
        row=QHBoxLayout(self); row.setContentsMargins(0,0,0,0); row.setSpacing(4)
        self.title=QLabel('Hardware Volume')
        self.title.setToolTip('Actual sOS speaker volume. Linked to ALSA hardware, PipeWire/Pulse and Dell Latitude media keys.')
        # Compact Main UI hides the explicit label; Performance no longer hosts a
        # duplicate hardware/system volume widget (synth Master Volume is used).
        if compact:
            self.title.hide()
        else:
            self.title.setText('Hardware Volume')
            self.title.show()
        row.addWidget(self.title)
        self.slider=QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0,100)
        self.slider.setSingleStep(2); self.slider.setPageStep(5); self.slider.setFixedWidth(95 if compact else 180)
        self.slider.setToolTip('Actual hardware/system output volume')
        self.slider.setValue(72)
        row.addWidget(self.slider)
        self.value_label=QLabel('72%'); self.value_label.setMinimumWidth(34); row.addWidget(self.value_label)
        self._send=QTimer(self); self._send.setSingleShot(True); self._send.setInterval(120)
        self._send.timeout.connect(self._commit_slider)
        self.slider.valueChanged.connect(self._slider_changed)
        self._poll=QTimer(self); self._poll.setInterval(350); self._poll.timeout.connect(self.sync_from_state); self._poll.start()
        # GROOVEBOX_R23R_LATITUDE_ALL_DEVICES_JACK_20261102: the 3.5 mm jack can be plugged in at any time.
        # The helper's `jack` command does nothing unless the jack state changed; on a change it re-prepares the
        # route (Speaker/Headphones UCM, Auto-Mute off) and re-levels every playback card.
        self._jack=QTimer(self); self._jack.setInterval(3000)
        self._jack.timeout.connect(lambda: request_hardware_volume('jack'))
        if os.path.isfile(HELPER): self._jack.start()
        QTimer.singleShot(0,self.sync_from_state)
        # Reconcile the persisted hardware state with the current ALSA/PipeWire
        # session once on UI startup. This is intentionally a single helper call,
        # not a recurring hardware probe on the GUI thread.
        QTimer.singleShot(80, lambda: request_hardware_volume('sync'))
        # GROOVEBOX_R23R_HWVOL_LATE_SYNC_20261101: on the Dell Latitude the first
        # sync can land before PipeWire/UCM finish bringing the speaker route up,
        # leaving the mixer muted until a slider is moved. Re-assert the desired
        # level a few times while the session settles (once per app, not per widget).
        if not HardwareVolumeWidget._late_sync_scheduled:
            HardwareVolumeWidget._late_sync_scheduled = True
            for _ms in (2500, 8000, 20000):
                QTimer.singleShot(_ms, lambda: request_hardware_volume('sync'))
    def _slider_changed(self,value):
        self.value_label.setText(f'{int(value)}%')
        if not self._syncing:
            # Claim the pending value as soon as a drag begins, before the 350ms
            # state poll can repaint an older mixer value over the moving slider.
            self._pending_value=int(value)
            self._pending_until=0.0
            self._send.start()
    def _commit_slider(self):
        value=int(self.slider.value())
        # Hold the user's selected value until the privileged helper's state file
        # actually confirms it. A wall-clock timeout used to make the UI jump back
        # to stale persisted volume during a delayed helper response on slower/failed helper updates.
        self._pending_value=value
        self._pending_until=0.0
        ok = request_hardware_volume('set',value)
        self.slider.setToolTip('Actual hardware/system output volume' if ok else
                               'Requested volume is shown; hardware-volume helper is unavailable or not executable.')
    def sync_from_state(self):
        st=read_hardware_volume_state()
        pending=self._pending_value
        if pending is not None:
            if int(st['volume']) == int(pending):
                self._pending_value=None
            else:
                # State can lag during ALSA/UCM reinitialization. Never replace an
                # explicit user request with an older persisted value.
                st=dict(st); st['volume']=int(pending)
        self._syncing=True
        try:
            self.slider.blockSignals(True); self.slider.setValue(int(st['volume'])); self.slider.blockSignals(False)
            self.value_label.setText(f"{int(st['volume'])}%")
            tip=f"Hardware card {st.get('card') or '?'} · {st.get('control') or 'playback control'}"
            self.value_label.setToolTip(tip)
        finally:
            self._syncing=False
