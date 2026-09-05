#!/usr/bin/env python3
"""Interactive Draw/Analyze/Reference signal lab for Mathematician's Groovebox.
Derived operations never overwrite canonical/userdata unless the user explicitly saves/sends them.
"""
from __future__ import annotations
import json, math, os, wave
from meum_constants import M, PHI, MEUM_MINUS_1, MEUM_INV, MEUM_TWO_MINUS, MEUM_NORM
from pathlib import Path
from typing import Optional
import numpy as np
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,
    QDoubleSpinBox,QSpinBox,QFileDialog,QMessageBox,QPlainTextEdit,QSlider,QGroupBox)

IRR_TRAVERSAL_DEFAULT = MEUM_MINUS_1
IRR_PHASE_DEFAULT = math.sqrt(2.0) - 1.0

class DrawSignalCanvas(QWidget):
    changed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self._pts=[QPointF(i/63.0, 0.5-0.38*math.sin(2*math.pi*i/63.0)) for i in range(64)]
        self._drawing=False
    def normalized_points(self):
        return [(float(p.x()), float(p.y())) for p in self._pts]
    def set_points(self, pts):
        out=[]
        for x,y in pts:
            out.append(QPointF(max(0.0,min(1.0,float(x))),max(0.0,min(1.0,float(y)))))
        self._pts=sorted(out,key=lambda p:p.x()) or [QPointF(0,.5),QPointF(1,.5)]
        self.update(); self.changed.emit()
    def clear_wave(self):
        self._pts=[QPointF(0,.5),QPointF(1,.5)]; self.update(); self.changed.emit()
    def paintEvent(self, _e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=max(1,self.width()); h=max(1,self.height())
        p.fillRect(self.rect(), QColor('#0b0f14'))
        p.setPen(QPen(QColor('#29313a'),1))
        for i in range(1,8):
            x=int(i*w/8); p.drawLine(x,0,x,h)
        p.drawLine(0,h//2,w,h//2)
        if self._pts:
            path=QPainterPath(); p0=self._pts[0]; path.moveTo(p0.x()*w,p0.y()*h)
            for q in self._pts[1:]: path.lineTo(q.x()*w,q.y()*h)
            p.setPen(QPen(QColor('#5ee7d8'),2.5)); p.drawPath(path)
    def _add(self,pos):
        x=max(0.0,min(1.0,pos.x()/max(1,self.width()))); y=max(0.0,min(1.0,pos.y()/max(1,self.height())))
        # Replace points in a narrow x-neighborhood so freehand drawing remains compact.
        eps=1.7/max(1,self.width())
        self._pts=[p for p in self._pts if abs(p.x()-x)>eps]
        self._pts.append(QPointF(x,y)); self._pts.sort(key=lambda p:p.x())
        self.update(); self.changed.emit()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self._drawing=True; self._add(e.position())
        elif e.button()==Qt.MouseButton.RightButton: self.clear_wave()
    def mouseMoveEvent(self,e):
        if self._drawing: self._add(e.position())
    def mouseReleaseEvent(self,e): self._drawing=False

class SignalLab(QWidget):
    def __init__(self, host=None, parent=None):
        super().__init__(parent); self.host=host; self.reference_path: Optional[str]=None; self.last_generated: Optional[str]=None
        root=QVBoxLayout(self)
        intro=QLabel('Draw a literal signal or an explicit control/tuning curve. Derived/reference transforms are reversible until you explicitly save/send them.')
        intro.setWordWrap(True); root.addWidget(intro)
        top=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(['Carrier','Sample','Program','Tuning'])
        top.addWidget(QLabel('Draw:')); top.addWidget(self.mode)
        bclear=QPushButton('Clear'); bclear.clicked.connect(self._clear); top.addWidget(bclear)
        bsine=QPushButton('Seed Sine'); bsine.clicked.connect(self._seed_sine); top.addWidget(bsine); top.addStretch(1); root.addLayout(top)
        self.canvas=DrawSignalCanvas(); root.addWidget(self.canvas)
        cfg=QGroupBox('Signal mapping'); f=QFormLayout(cfg)
        self.sr=QSpinBox(); self.sr.setRange(8000,192000); self.sr.setValue(48000); f.addRow('Sample rate',self.sr)
        self.duration=QDoubleSpinBox(); self.duration.setRange(.02,120.0); self.duration.setDecimals(3); self.duration.setValue(2.0); f.addRow('Duration (s)',self.duration)
        self.cycles=QDoubleSpinBox(); self.cycles.setRange(.01,4096.0); self.cycles.setDecimals(9); self.cycles.setValue(1.0); f.addRow('Cycles / traversal',self.cycles)
        self.traversal=QDoubleSpinBox(); self.traversal.setRange(0.000001,8.0); self.traversal.setDecimals(10); self.traversal.setValue(IRR_TRAVERSAL_DEFAULT); f.addRow('Derived traversal index',self.traversal)
        self.phase=QDoubleSpinBox(); self.phase.setRange(0.0,1.0); self.phase.setDecimals(10); self.phase.setValue(IRR_PHASE_DEFAULT); f.addRow('Derived phase index',self.phase)
        root.addWidget(cfg)
        row=QHBoxLayout(); bsave=QPushButton('Save Drawn Output…'); bsave.clicked.connect(self._save_drawn); row.addWidget(bsave)
        bglob=QPushButton('Send as Global Carrier'); bglob.clicked.connect(lambda:self._send_to_host(False)); row.addWidget(bglob)
        bloc=QPushButton('Send to Selected Instrument'); bloc.clicked.connect(lambda:self._send_to_host(True)); row.addWidget(bloc); root.addLayout(row)

        ref=QGroupBox('Reference / Reverse Engineer / Fundamental Loop'); rf=QVBoxLayout(ref)
        rr=QHBoxLayout(); self.ref_label=QLabel('No reference loaded'); self.ref_label.setWordWrap(True); rr.addWidget(self.ref_label,1)
        bload=QPushButton('Load Reference WAV…'); bload.clicked.connect(self._load_reference); rr.addWidget(bload); rf.addLayout(rr)
        tx=QHBoxLayout(); self.ref_mode=QComboBox(); self.ref_mode.addItems(['Sounds Like','Harmonic Complement','Opposite']); tx.addWidget(self.ref_mode)
        self.strength=QSlider(Qt.Orientation.Horizontal); self.strength.setRange(0,1000); self.strength.setValue(500); tx.addWidget(QLabel('Strength')); tx.addWidget(self.strength,1)
        btransform=QPushButton('Create Derived Reference Transform…'); btransform.clicked.connect(self._reference_transform); tx.addWidget(btransform); rf.addLayout(tx)
        ar=QHBoxLayout(); ban=QPushButton('Analyze / Reverse Engineer'); ban.clicked.connect(self._analyze); ar.addWidget(ban)
        bloop=QPushButton('Detect Fundamental Loop'); bloop.clicked.connect(self._detect_loop); ar.addWidget(bloop); ar.addStretch(1); rf.addLayout(ar)
        self.report=QPlainTextEdit(); self.report.setReadOnly(True); self.report.setMaximumBlockCount(4000); rf.addWidget(self.report)
        root.addWidget(ref,1)
    def _clear(self): self.canvas.clear_wave()
    def _seed_sine(self):
        pts=[(i/127.0,.5-.42*math.sin(2*math.pi*i/127.0)) for i in range(128)]; self.canvas.set_points(pts)
    def _curve(self,n):
        pts=self.canvas.normalized_points(); xs=np.array([p[0] for p in pts]); ys=np.array([1.0-2.0*p[1] for p in pts])
        order=np.argsort(xs); xs=xs[order]; ys=ys[order]
        # guarantee endpoints for stable interpolation
        if xs[0]>0: xs=np.r_[0.,xs]; ys=np.r_[ys[0],ys]
        if xs[-1]<1: xs=np.r_[xs,1.]; ys=np.r_[ys,ys[-1]]
        t=np.linspace(0,1,max(2,n),endpoint=False)
        cyc=max(.01,float(self.cycles.value())); phase=float(self.phase.value())
        q=np.mod(t*cyc+phase*float(self.traversal.value()),1.0)
        return np.interp(q,xs,ys).astype(np.float64)
    def _write_wav(self,path,x,sr):
        y=np.asarray(x,float); y=np.clip(y,-1.0,1.0); pcm=np.rint(y*32767.0).astype('<i2')
        with wave.open(path,'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    def _save_drawn(self):
        mode=self.mode.currentText(); base='drawn_'+mode.lower()
        if mode in ('Carrier','Sample'):
            p,_=QFileDialog.getSaveFileName(self,'Save drawn signal',base+'.wav','WAV (*.wav)')
            if not p:return
            n=int(round(self.sr.value()*self.duration.value())); self._write_wav(p,self._curve(n),self.sr.value())
        else:
            p,_=QFileDialog.getSaveFileName(self,'Save drawn control',base+'.json','JSON (*.json)')
            if not p:return
            payload={'format':'MathematiciansGrooveboxDrawn'+mode,'version':1,'userdata':False,'points':self.canvas.normalized_points(),
                     'traversal_index':self.traversal.value(),'phase_index':self.phase.value(),'cycles':self.cycles.value()}
            Path(p).write_text(json.dumps(payload,indent=2),encoding='utf-8')
        self.last_generated=os.path.abspath(p); self.report.setPlainText('Saved: '+self.last_generated)
    def _send_to_host(self,local):
        if self.mode.currentText() not in ('Carrier','Sample'):
            QMessageBox.information(self,'Draw Program/Tuning','Program and Tuning curves stay derived until explicitly saved/baked; they are not silently written into userdata.'); return
        out=os.path.join(tempfile_dir(),'groovebox_drawn_'+('local' if local else 'global')+'.wav'); n=int(round(self.sr.value()*self.duration.value())); self._write_wav(out,self._curve(n),self.sr.value())
        self.last_generated=out
        try:
            if local:
                name=''
                for attr in ('selected_instrument','current_instrument'):
                    v=getattr(self.host,attr,None)
                    if isinstance(v,str) and v: name=v; break
                if not name:
                    combo=getattr(self.host,'instrument_selector',None) or getattr(self.host,'instrument_combo',None)
                    if combo is not None and hasattr(combo,'currentText'): name=combo.currentText()
                store=getattr(self.host,'instrument_media_samples',None)
                if not isinstance(store,dict): store={}; setattr(self.host,'instrument_media_samples',store)
                store[name or 'selected']={'path':out,'derived':True,'userdata':False,'source':'draw'}
            else:
                setattr(self.host,'global_media_sample',{'path':out,'derived':True,'userdata':False,'source':'draw'})
                setattr(self.host,'_global_carrier_path',out)
            self.report.setPlainText(('Local' if local else 'Global')+' derived carrier sent: '+out)
        except Exception as e: QMessageBox.warning(self,'Send failed',str(e))
    def _load_reference(self):
        p,_=QFileDialog.getOpenFileName(self,'Load reference WAV','','WAV (*.wav)')
        if p: self.reference_path=p; self.ref_label.setText(p)
    def _analyze(self):
        if not self.reference_path:return
        try:
            from reverse_engineer import analyze
            r=analyze(self.reference_path,max_instruments=16); self.report.setPlainText(json.dumps(r,indent=2))
        except Exception as e: QMessageBox.warning(self,'Analyze failed',str(e))
    def _detect_loop(self):
        if not self.reference_path:return
        try:
            from reverse_engineer import load_wav_mono
            x,sr=load_wav_mono(self.reference_path); n=len(x)
            if n<128: raise ValueError('Reference too short')
            y=x-x.mean(); minlag=max(16,int(sr/2000)); maxlag=min(n//2,int(sr*8.0));
            # coarse-to-fine normalized correlation search
            lags=np.unique(np.linspace(minlag,maxlag,min(2048,maxlag-minlag+1),dtype=int)); den=float(np.dot(y,y))+1e-15
            scores=[]
            for lag in lags:
                a=y[:-lag]; b=y[lag:]; scores.append(float(np.dot(a,b)/(math.sqrt(np.dot(a,a)*np.dot(b,b))+1e-15)))
            lag=int(lags[int(np.argmax(scores))]); score=float(max(scores)); hz=sr/lag
            self.report.setPlainText(f'Fundamental loop estimate\nlag: {lag} samples\nduration: {lag/sr:.9f} s\nrepeat rate: {hz:.9f} Hz\nnormalized similarity: {score:.9f}')
        except Exception as e: QMessageBox.warning(self,'Loop detect failed',str(e))
    def _reference_transform(self):
        if not self.reference_path:return
        p,_=QFileDialog.getSaveFileName(self,'Save derived transform','reference_transform.wav','WAV (*.wav)')
        if not p:return
        try:
            from reverse_engineer import load_wav_mono
            ref,sr=load_wav_mono(self.reference_path); n=max(2,int(round(self.sr.value()*self.duration.value()))); src=self._curve(n)
            # Resample reference to source length without changing source state.
            ref=np.interp(np.linspace(0,1,n,endpoint=False),np.linspace(0,1,len(ref),endpoint=False),ref)
            S=np.fft.rfft(src); R=np.fft.rfft(ref); a=self.strength.value()/1000.0; mode=self.ref_mode.currentText()
            magS=np.abs(S); magR=np.abs(R); phase=np.angle(S)
            if mode=='Sounds Like': mag=(1-a)*magS+a*magR
            elif mode=='Harmonic Complement':
                scale=(np.mean(magS)+1e-15)/(np.mean(magR)+1e-15); mag=magS*(1-a)+a*np.maximum(0.0,magS-(magR*scale))
            else: # Opposite: invert normalized reference spectral emphasis around its mean
                nr=magR/(np.max(magR)+1e-15); mag=magS*((1-a)+a*(1.0-nr))
            out=np.fft.irfft(mag*np.exp(1j*phase),n=n); self._write_wav(p,out,self.sr.value()); self.last_generated=os.path.abspath(p)
            self.report.setPlainText(f'Derived {mode} transform saved:\n{self.last_generated}\nStrength {a:.3f}; canonical/userdata unchanged.')
        except Exception as e: QMessageBox.warning(self,'Transform failed',str(e))

def tempfile_dir():
    import tempfile
    d=os.path.join(tempfile.gettempdir(),'groovebox_signal_lab'); os.makedirs(d,exist_ok=True); return d
