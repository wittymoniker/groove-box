#!/usr/bin/env python3
from __future__ import annotations
import json, math, os, tempfile, threading, time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,
    QDoubleSpinBox,QSpinBox,QFileDialog,QMessageBox,QPlainTextEdit,QTabWidget,QLineEdit,QGroupBox,QTableWidget,QTableWidgetItem,QScrollArea,QSizePolicy)
from media_layer_engine import render_layers, write_wav, spectrum_peaks
import groovebox_paths

class LayerCanvas(QWidget):
    changed=pyqtSignal()
    def __init__(self,parent=None,points=None):
        super().__init__(parent); self.setMinimumHeight(230); self._drawing=False
        self._pts=[]; self.set_points(points or [(i/63.0,.5-.38*math.sin(2*math.pi*i/63.0)) for i in range(64)],emit=False)
    def normalized_points(self): return [(float(p.x()),float(p.y())) for p in self._pts]
    def set_points(self,pts,emit=True):
        out=[]
        for x,y in pts: out.append(QPointF(max(0,min(1,float(x))),max(0,min(1,float(y)))))
        self._pts=sorted(out,key=lambda p:p.x()) or [QPointF(0,.5),QPointF(1,.5)]; self.update()
        if emit:self.changed.emit()
    def clear_wave(self): self.set_points([(0,.5),(1,.5)])
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); w=max(1,self.width()); h=max(1,self.height())
        p.fillRect(self.rect(),QColor('#0b0f14')); p.setPen(QPen(QColor('#29313a'),1))
        for i in range(1,8): p.drawLine(int(i*w/8),0,int(i*w/8),h)
        p.drawLine(0,h//2,w,h//2)
        if self._pts:
            path=QPainterPath(); q=self._pts[0]; path.moveTo(q.x()*w,q.y()*h)
            for q in self._pts[1:]: path.lineTo(q.x()*w,q.y()*h)
            p.setPen(QPen(QColor('#5ee7d8'),2.5)); p.drawPath(path)
    def _add(self,pos):
        x=max(0,min(1,pos.x()/max(1,self.width()))); y=max(0,min(1,pos.y()/max(1,self.height()))); eps=1.7/max(1,self.width())
        self._pts=[p for p in self._pts if abs(p.x()-x)>eps]; self._pts.append(QPointF(x,y)); self._pts.sort(key=lambda p:p.x()); self.update(); self.changed.emit()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:self._drawing=True;self._add(e.position())
        elif e.button()==Qt.MouseButton.RightButton:self.clear_wave()
    def mouseMoveEvent(self,e):
        if self._drawing:self._add(e.position())
    def mouseReleaseEvent(self,e): self._drawing=False

class SpectrumWidget(QWidget):
    def __init__(self,parent=None): super().__init__(parent); self.setMinimumHeight(120); self._peaks=[]
    def set_peaks(self,peaks): self._peaks=list(peaks); self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#070b10')); w=max(1,self.width()); h=max(1,self.height())
        p.setPen(QPen(QColor('#5ee7d8'),2))
        if not self._peaks:return
        mh=max(20.0,max((x[0] for x in self._peaks),default=20000.0))
        for hz,a in self._peaks:
            x=int(min(1.0,hz/mh)*(w-10)); y=int((1-max(0,min(1,a)))*(h-18)); p.drawLine(x,h-4,x,y); p.drawText(max(0,x-22),max(12,y-3),f'{hz:.0f}')

class LayeredSignalLab(QWidget):
    record_ready=pyqtSignal(str,str)
    def __init__(self,host=None,parent=None):
        super().__init__(parent); self.host=host; self.layers:List[Dict[str,Any]]=[]; self.canvases=[]; self.last_generated=None
        self.record_ready.connect(self._record_finished)
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        whole_scroll=QScrollArea(); whole_scroll.setWidgetResizable(True)
        whole_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_body=QWidget(); whole_body.setMinimumWidth(700)
        root=QVBoxLayout(whole_body); root.setContentsMargins(6,6,6,6); root.setSpacing(6)
        whole_scroll.setWidget(whole_body); outer.addWidget(whole_scroll)
        intro=QLabel('Layered Draw/Record/Sample reconstruction. Relative time scalars divide the final duration; each interval morphs one layer into the next deterministically.'); intro.setWordWrap(True); root.addWidget(intro)
        indev=QGroupBox('Record Sound · input device')
        idl=QHBoxLayout(indev)
        idl.addWidget(QLabel('Microphone / input'))
        self.cmb_record_input=QComboBox(); idl.addWidget(self.cmb_record_input,1)
        self.btn_refresh_record_inputs=QPushButton('↻ Refresh'); self.btn_refresh_record_inputs.clicked.connect(self._refresh_record_inputs); idl.addWidget(self.btn_refresh_record_inputs)
        root.addWidget(indev)
        ctl=QHBoxLayout();
        for text,fn in [('＋ Draw Layer',self._add_draw_layer),('＋ Sample Layer…',self._add_sample_layer),('● Record Layer',self._record_layer),('− Layer',self._remove_layer)]:
            b=QPushButton(text); b.clicked.connect(fn); ctl.addWidget(b)
        ctl.addStretch(1); root.addLayout(ctl)
        recbox=QGroupBox('Recordings Table · project/session references')
        rbl=QVBoxLayout(recbox)
        self.recordings_table=QTableWidget(0,3); self.recordings_table.setHorizontalHeaderLabels(['Layer','Type','File']); rbl.addWidget(self.recordings_table)
        rr=QHBoxLayout()
        self.btn_append_recording=QPushButton('＋ Append Recording Layer…'); self.btn_append_recording.clicked.connect(self._append_recording_layer); rr.addWidget(self.btn_append_recording)
        self.btn_remove_recording=QPushButton('− Remove Recording Layer Tab'); self.btn_remove_recording.clicked.connect(self._remove_recording_layer_tab); rr.addWidget(self.btn_remove_recording)
        self.btn_clear_recordings=QPushButton('Clear Recordings Table'); self.btn_clear_recordings.clicked.connect(self._clear_recordings_table); rr.addWidget(self.btn_clear_recordings)
        self.btn_remove_project_recording=QPushButton('Remove from Project'); self.btn_remove_project_recording.clicked.connect(lambda: self._delete_selected_recording(False)); rr.addWidget(self.btn_remove_project_recording)
        self.btn_delete_recording_file=QPushButton('Delete File + Entry'); self.btn_delete_recording_file.clicked.connect(lambda: self._delete_selected_recording(True)); rr.addWidget(self.btn_delete_recording_file)
        rbl.addLayout(rr); root.addWidget(recbox)
        self.tabs=QTabWidget(); self.tabs.setMinimumHeight(300); self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding); self.tabs.currentChanged.connect(self._sync_controls_from_layer); root.addWidget(self.tabs,1)
        cfg=QGroupBox('Selected layer / reconstruction'); f=QFormLayout(cfg)
        self.edit_name=QLineEdit(); self.edit_name.editingFinished.connect(self._pull_controls); f.addRow('Layer name',self.edit_name)
        self.scalar=QDoubleSpinBox(); self.scalar.setRange(.000001,1000000); self.scalar.setDecimals(6); self.scalar.setValue(1); self.scalar.valueChanged.connect(self._pull_controls); f.addRow('Relative time scalar',self.scalar)
        self.gain=QDoubleSpinBox(); self.gain.setRange(0,8); self.gain.setDecimals(5); self.gain.setValue(1); self.gain.valueChanged.connect(self._pull_controls); f.addRow('Layer gain',self.gain)
        self.cycles=QDoubleSpinBox(); self.cycles.setRange(.000001,4096); self.cycles.setDecimals(7); self.cycles.setValue(1); self.cycles.valueChanged.connect(self._pull_controls); f.addRow('Layer cycles',self.cycles)
        self.duration=QDoubleSpinBox(); self.duration.setRange(.02,3600); self.duration.setDecimals(4); self.duration.setValue(4); self.duration.valueChanged.connect(self._state_changed); f.addRow('Total output time (s)',self.duration)
        self.sr=QSpinBox(); self.sr.setRange(8000,192000); self.sr.setValue(48000); self.sr.valueChanged.connect(self._state_changed); f.addRow('Sample rate',self.sr)
        self.blend_mode=QComboBox(); self.blend_mode.addItems(['Morph Between Layers','Pooled Overlay']); self.blend_mode.currentTextChanged.connect(self._state_changed); f.addRow('Layer composition',self.blend_mode)
        self.heur=QComboBox(); self.heur.addItems(['Linear','Equal Power','Smoothstep','Nearest','Co-fractal Meum','Parametric']); self.heur.currentTextChanged.connect(self._state_changed); f.addRow('Between-layer heuristic',self.heur)
        self.expr=QLineEdit('u'); self.expr.setToolTip('For Parametric mode: alpha expression using u/t, MEUM, PHI, pi, sin, cos, sqrt, abs.'); self.expr.editingFinished.connect(self._state_changed); f.addRow('Parametric alpha',self.expr)
        cfg.setMinimumHeight(300)
        cfg.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
        bind=QGroupBox('Bind All Layers to Instrument')
        bl=QHBoxLayout(bind); bl.addWidget(QLabel('Bind as'))
        self.cmb_bind_all=QComboBox(); self.cmb_bind_all.addItems(['Audio','Video','Both','Unbound']); bl.addWidget(self.cmb_bind_all)
        self.btn_bind_all=QPushButton('Bind All Layers to Selected Instrument'); self.btn_bind_all.clicked.connect(self._bind_all_layers_to_instrument); bl.addWidget(self.btn_bind_all,1)
        self.btn_bind_carrier=QPushButton('Bind All Layers to Carrier'); self.btn_bind_carrier.clicked.connect(self._bind_all_layers_to_carrier); bl.addWidget(self.btn_bind_carrier,1)
        bind.setMinimumHeight(90)
        bind.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
        mon=QGroupBox('Rendered sample monitor'); ml=QVBoxLayout(mon); self.spec=SpectrumWidget(); ml.addWidget(self.spec)
        self.lbl_peaks=QLabel('Peaks: —'); self.lbl_peaks.setWordWrap(True); ml.addWidget(self.lbl_peaks)
        row=QHBoxLayout();
        for text,fn in [('Render Preview',self._render_preview),('▶ Play Sample',self._play_sample),('Save WAV…',self._save),('Send Global',lambda:self._send(False)),('Send → Selected',lambda:self._send(True))]:
            b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        ml.addLayout(row)
        mon.setMinimumHeight(245)
        mon.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
        for _b in mon.findChildren(QPushButton):
            _b.setMinimumHeight(32)
        self.report=QPlainTextEdit(); self.report.setReadOnly(True); self.report.setMinimumHeight(90); self.report.setMaximumHeight(140)
        # AUDIO_LAYOUT_20260907: protect Selected Layer / Reconstruction and
        # its action controls from splitter/fullscreen squeeze.  The layer tabs
        # remain the expanding editor; the lower reconstruction workstation
        # scrolls instead of allowing Qt to collapse or clip controls.
        recon_body=QWidget()
        recon_body.setMinimumWidth(620)
        recon_lay=QVBoxLayout(recon_body)
        recon_lay.setContentsMargins(4,4,4,4)
        recon_lay.addWidget(cfg)
        recon_lay.addWidget(bind)
        recon_lay.addWidget(mon)
        recon_lay.addWidget(self.report)
        recon_lay.addStretch(1)
        self.reconstruction_scroll=QScrollArea()
        self.reconstruction_scroll.setWidgetResizable(True)
        self.reconstruction_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.reconstruction_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.reconstruction_scroll.setMinimumHeight(360)
        self.reconstruction_scroll.setWidget(recon_body)
        root.addWidget(self.reconstruction_scroll,1)
        self._preview=None; self._preview_sr=48000; self._record_input_devices=[]
        self._refresh_record_inputs()
        self._restore_host_state()
        if not self.layers:self._add_draw_layer()
        self._refresh_recordings_table()
    def _layer_default(self,name='Draw',kind='draw',path=''): return {'name':name,'kind':kind,'path':path,'points':[(0,.5),(1,.5)],'time_scalar':1.0,'gain':1.0,'cycles':1.0,'phase':0.0,'provenance':kind}
    def _add_draw_layer(self): self._add_layer(self._layer_default(f'Draw {len(self.layers)+1}'))
    def _add_sample_layer(self):
        base=groovebox_paths.samples_dir(getattr(self.host,'_current_project_path',None))
        p,_=QFileDialog.getOpenFileName(self,'Import audio layer',base,'Audio (*.wav *.flac *.mp3 *.ogg *.opus *.aiff *.aif *.caf);;All files (*)')
        if p:
            p=groovebox_paths.ingest_file(p,'layer',getattr(self.host,'_current_project_path',None))
            self._add_layer(self._layer_default(Path(p).stem,'sample',os.path.abspath(p)))
    def _add_layer(self,rec):
        self.layers.append(rec); page=QWidget(); l=QVBoxLayout(page)
        if rec.get('kind')=='draw':
            c=LayerCanvas(points=rec.get('points')); c.changed.connect(lambda c=c:self._canvas_changed(c)); l.addWidget(c); self.canvases.append(c)
        else:
            q=QLabel(f"{rec.get('kind','audio').upper()}\n{rec.get('path','')}"); q.setWordWrap(True); q.setAlignment(Qt.AlignmentFlag.AlignCenter); l.addWidget(q,1); self.canvases.append(None)
        idx=self.tabs.addTab(page,str(rec.get('name','Layer'))); self.tabs.setCurrentIndex(idx); self._sync_controls_from_layer(); self._state_changed(); self._refresh_recordings_table()
    def _remove_layer(self):
        i=self.tabs.currentIndex()
        if i<0:return
        self.tabs.removeTab(i); self.layers.pop(i); self.canvases.pop(i); self._sync_controls_from_layer(); self._state_changed(); self._refresh_recordings_table()
    def _append_recording_layer(self):
        base=groovebox_paths.recordings_dir(getattr(self.host,'_current_project_path',None))
        p,_=QFileDialog.getOpenFileName(self,'Append recording layer',base,'Audio recordings (*.wav *.flac *.mp3 *.ogg *.opus *.aiff *.aif *.caf);;All files (*)')
        if not p:return
        try:p=groovebox_paths.ingest_file(p,'recording',getattr(self.host,'_current_project_path',None))
        except Exception:pass
        self._add_layer(self._layer_default(Path(p).stem,'record',os.path.abspath(p))); self._refresh_recordings_table()
    def _remove_recording_layer_tab(self):
        i=self.tabs.currentIndex()
        if i<0 or i>=len(self.layers):return
        if str(self.layers[i].get('kind',''))!='record':
            QMessageBox.information(self,'Remove Recording Layer','Select a Record layer tab first. Other layer types are left intact.'); return
        self._remove_layer()
    def _delete_selected_recording(self, delete_file: bool):
        rows=[(i,r) for i,r in enumerate(self.layers) if isinstance(r,dict) and str(r.get('kind',''))=='record']
        row=self.recordings_table.currentRow() if hasattr(self,'recordings_table') else -1
        idx=-1
        if 0 <= row < len(rows): idx=rows[row][0]
        elif 0 <= self.tabs.currentIndex() < len(self.layers) and str(self.layers[self.tabs.currentIndex()].get('kind',''))=='record': idx=self.tabs.currentIndex()
        if idx < 0:
            QMessageBox.information(self,'Recording','Select a recording row or Record layer tab first.'); return
        path=os.path.abspath(str(self.layers[idx].get('path') or ''))
        action='Delete the file from disk AND remove its project entry?' if delete_file else 'Remove this recording from the project but keep the file on disk?'
        if QMessageBox.question(self,'Delete recording',f'{action}\n\n{path}',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        try:
            import groovebox_paths; groovebox_paths.unindex_file(path,getattr(self.host,'_current_project_path',None))
        except Exception: pass
        self.tabs.removeTab(idx); self.layers.pop(idx); self.canvases.pop(idx)
        if delete_file:
            try:
                if path and os.path.isfile(path): os.remove(path)
            except Exception as e:
                QMessageBox.warning(self,'Delete file failed',str(e))
        self._sync_controls_from_layer(); self._state_changed(); self._refresh_recordings_table()
        self.report.setPlainText(('Deleted file + project entry: ' if delete_file else 'Removed project entry; file kept: ')+path)

    def _clear_recordings_table(self):
        self.recordings_table.setRowCount(0)
        self.report.setPlainText('Recordings Table cleared. Source files and layer tabs were not deleted.')
    def _refresh_recordings_table(self):
        if not hasattr(self,'recordings_table'):return
        rows=[(i,r) for i,r in enumerate(self.layers) if isinstance(r,dict) and str(r.get('kind',''))=='record']
        self.recordings_table.setRowCount(len(rows))
        for row,(idx,r) in enumerate(rows):
            vals=(str(r.get('name') or f'Record {idx+1}'),'record',str(r.get('path') or ''))
            for c,v in enumerate(vals):self.recordings_table.setItem(row,c,QTableWidgetItem(v))
    def _canvas_changed(self,c):
        try:i=self.canvases.index(c); self.layers[i]['points']=c.normalized_points(); self._state_changed()
        except Exception:pass
    def _sync_controls_from_layer(self,*_):
        i=self.tabs.currentIndex(); on=0<=i<len(self.layers)
        for w in (self.edit_name,self.scalar,self.gain,self.cycles):w.setEnabled(on)
        if not on:return
        r=self.layers[i]
        for w in (self.edit_name,self.scalar,self.gain,self.cycles):w.blockSignals(True)
        self.edit_name.setText(str(r.get('name','Layer'))); self.scalar.setValue(float(r.get('time_scalar',1))); self.gain.setValue(float(r.get('gain',1))); self.cycles.setValue(float(r.get('cycles',1)))
        for w in (self.edit_name,self.scalar,self.gain,self.cycles):w.blockSignals(False)
    def _pull_controls(self,*_):
        i=self.tabs.currentIndex()
        if 0<=i<len(self.layers):
            r=self.layers[i]; r.update(name=self.edit_name.text().strip() or f'Layer {i+1}',time_scalar=float(self.scalar.value()),gain=float(self.gain.value()),cycles=float(self.cycles.value())); self.tabs.setTabText(i,r['name']); self._state_changed()
    def export_state(self):
        return {'version':4,'duration':float(self.duration.value()),'sample_rate':int(self.sr.value()),'blend_mode':self.blend_mode.currentText(),'heuristic':self.heur.currentText(),'parametric':self.expr.text(),'record_input':self.cmb_record_input.currentText() if hasattr(self,'cmb_record_input') else '','bind_all_mode':self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Audio','layers':json.loads(json.dumps(self.layers,default=str))}
    def restore_state(self,state):
        if not isinstance(state,dict):return
        self.duration.setValue(float(state.get('duration',4))); self.sr.setValue(int(state.get('sample_rate',48000))); self.blend_mode.setCurrentText(str(state.get('blend_mode','Morph Between Layers'))); self.heur.setCurrentText(str(state.get('heuristic','Linear'))); self.expr.setText(str(state.get('parametric','u')))
        recdev=str(state.get('record_input') or '')
        if recdev and hasattr(self,'cmb_record_input'):
            i=self.cmb_record_input.findText(recdev)
            if i>=0:self.cmb_record_input.setCurrentIndex(i)
        mode=str(state.get('bind_all_mode') or 'Audio')
        if hasattr(self,'cmb_bind_all') and mode in ('Audio','Video','Both','Unbound'):self.cmb_bind_all.setCurrentText(mode)
        for r in state.get('layers',[]):
            if isinstance(r,dict):self._add_layer(dict(r))
    def _restore_host_state(self):
        try:self.restore_state((getattr(self.host,'media_workbench_state',{}) or {}).get('signal_lab',{}))
        except Exception:pass
    def _state_changed(self,*_):
        try:
            s=getattr(self.host,'media_workbench_state',None)
            if not isinstance(s,dict):s={};setattr(self.host,'media_workbench_state',s)
            s['signal_lab']=self.export_state()
        except Exception:pass
    def _render_preview(self):
        try:
            self._pull_controls()
            state=self.export_state()
            opt=getattr(self.host,'_scode_optimizer',None) if self.host is not None else None
            if opt is not None:
                # Include immutable file metadata in the sCode work identity so an
                # externally replaced recording/sample at the same path invalidates
                # the reconstruction cache automatically.
                source_sigs=[]
                for layer in state.get('layers',[]):
                    path=str(layer.get('path') or '') if isinstance(layer,dict) else ''
                    if path and os.path.isfile(path):
                        try:
                            st=os.stat(path); source_sigs.append((os.path.abspath(path),int(st.st_mtime_ns),int(st.st_size)))
                        except Exception: source_sigs.append((os.path.abspath(path),0,0))
                media_key=(state,tuple(source_sigs))
                # sCode work identity makes unchanged layered previews O(lookup)
                # instead of re-decoding/resampling every source and reconstructing
                # the same output buffer. Returned arrays are treated read-only here.
                x,sr=opt.memoized_result('media',media_key,lambda:render_layers(state),max_entries=12)
                peaks=opt.memoized_result('media_spectrum',(media_key,len(x),sr),lambda:spectrum_peaks(x,sr,10),max_entries=24)
            else:
                x,sr=render_layers(state); peaks=spectrum_peaks(x,sr,10)
            self._preview=x; self._preview_sr=sr
            self.spec.set_peaks(peaks)
            self.lbl_peaks.setText('Peaks: '+' · '.join(f'{hz:.1f} Hz/{amp:.2f}' for hz,amp in peaks[:8]))
            self.report.setPlainText(f'Rendered {len(x)} samples @ {sr} Hz from {len(self.layers)} layers.' + (' · sCode pooled' if opt is not None else ''))
        except Exception as e:QMessageBox.warning(self,'Render failed',str(e))
    def _play_sample(self):
        if self._preview is None:self._render_preview()
        if self._preview is None:return
        try:
            from audio_os_backend import sd; sd.play(self._preview,self._preview_sr,blocking=False)
        except Exception:
            p=os.path.join(tempfile.gettempdir(),'groovebox_layer_preview.wav'); write_wav(p,self._preview,self._preview_sr)
            import subprocess,shutil
            player=shutil.which('mpv') or shutil.which('ffplay')
            if player:subprocess.Popen([player,p])
    def _save(self):
        if self._preview is None:self._render_preview()
        if self._preview is None:return
        base=os.path.join(groovebox_paths.layers_dir(getattr(self.host,'_current_project_path',None)),'layered_wave.wav')
        p,_=QFileDialog.getSaveFileName(self,'Save layered wave',base,'WAV (*.wav)')
        if p:self.last_generated=write_wav(p,self._preview,self._preview_sr); self.report.setPlainText('Saved: '+self.last_generated)
    def _send(self,local):
        if self._preview is None:self._render_preview()
        if self._preview is None:return
        base=groovebox_paths.layers_dir(getattr(self.host,'_current_project_path',None)); p=os.path.join(base,f'groovebox_layered_{"local" if local else "global"}.wav'); write_wav(p,self._preview,self._preview_sr); groovebox_paths.index_file(p,'layer_render',getattr(self.host,'_current_project_path',None)); self.last_generated=p
        try:
            if local:
                name='selected'; combo=getattr(self.host,'instrument_selector_dropdown',None)
                if combo is not None:name=combo.currentText()
                store=getattr(self.host,'instrument_media_samples',None)
                if not isinstance(store,dict):store={};setattr(self.host,'instrument_media_samples',store)
                store[name]={'path':p,'sample_rate':self._preview_sr,'waveform':self._preview.copy(),'user_owned':True,'source_kind':'layered','layered_state':self.export_state()}
            else:
                setattr(self.host,'_global_carrier_path',p); setattr(self.host,'global_media_sample',{'path':p,'derived':True,'source':'layered','layered_state':self.export_state()})
            self._state_changed(); self.report.setPlainText(('Local' if local else 'Global')+' layered sample sent: '+p)
        except Exception as e:QMessageBox.warning(self,'Send failed',str(e))
    def _refresh_record_inputs(self):
        old=self.cmb_record_input.currentText() if hasattr(self,'cmb_record_input') and self.cmb_record_input.count() else ''
        self._record_input_devices=[]
        if hasattr(self,'cmb_record_input'):self.cmb_record_input.clear()
        try:
            from audio_os_backend import sd
            for idx,d in enumerate(sd.query_devices()):
                if int(d.get('max_input_channels',0) or 0)>0:
                    name=str(d.get('name') or f'Input {idx}')
                    self._record_input_devices.append((idx,name))
                    self.cmb_record_input.addItem(name,idx)
        except Exception:
            pass
        if hasattr(self,'cmb_record_input') and self.cmb_record_input.count()==0:self.cmb_record_input.addItem('Default input',None)
        if old and hasattr(self,'cmb_record_input'):
            i=self.cmb_record_input.findText(old)
            if i>=0:self.cmb_record_input.setCurrentIndex(i)

    def _selected_instrument_name(self):
        try:
            if self.host is not None and hasattr(self.host,'_current_instrument_name'):return str(self.host._current_instrument_name())
        except Exception:pass
        try:
            c=getattr(self.host,'instrument_selector_dropdown',None)
            if c is not None:return str(c.currentText())
        except Exception:pass
        return 'selected'

    def _bind_all_layers_to_instrument(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Audio'
        name=self._selected_instrument_name()
        store=getattr(self.host,'instrument_media_samples',None)
        if not isinstance(store,dict):store={};setattr(self.host,'instrument_media_samples',store)
        if mode=='Unbound':
            rec=store.get(name)
            if isinstance(rec,dict) and rec.get('binding_source')=='signal_lab_all_layers':store.pop(name,None)
            self._state_changed(); self.report.setPlainText(f'Unbound Draw/Record layers from {name}.'); return
        if mode=='Video':
            QMessageBox.information(self,'Bind All Layers','This Sound tab contains audio layers. Choose Audio or Both here; video layers can be bound from the Video tab.')
            return
        if self._preview is None:self._render_preview()
        if self._preview is None:return
        base=groovebox_paths.layers_dir(getattr(self.host,'_current_project_path',None))
        safe=''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in name)[:80] or 'instrument'
        p=os.path.join(base,f'{safe}_bound_all_layers.wav')
        write_wav(p,self._preview,self._preview_sr); groovebox_paths.index_file(p,'layer_render',getattr(self.host,'_current_project_path',None))
        prior=store.get(name) if isinstance(store.get(name),dict) else {}
        video_path=str(prior.get('video_path','')) if mode=='Both' else ''
        store[name]={'path':p,'sample_rate':int(self._preview_sr),'waveform':self._preview.copy(),'user_owned':True,'source_kind':'audio','video_path':video_path,'video_input_enabled':bool(video_path),'layered_state':self.export_state(),'binding_mode':mode.lower(),'binding_source':'signal_lab_all_layers','bound_layers_state':self.export_state()}
        self._state_changed(); self.report.setPlainText(f'Bound ALL sound layers → {name} as {mode}: {p}')
        try:
            if hasattr(self.host,'_refresh_operator_sample_ui'):self.host._refresh_operator_sample_ui()
            if hasattr(self.host,'_on_live_source_changed'):self.host._on_live_source_changed()
        except Exception:pass


    def _bind_all_layers_to_carrier(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Audio'
        if mode=='Unbound':
            try:
                setattr(self.host,'carrier_binding_source','')
                setattr(self.host,'carrier_binding_mode','unbound')
                setattr(self.host,'carrier_bound_layers_state',{})
            except Exception: pass
            self.report.setPlainText('Unbound Draw/Record layers from carrier provenance. Current carrier media is left intact.')
            self._state_changed(); return
        if mode=='Video':
            QMessageBox.information(self,'Bind All Layers to Carrier','This Sound tab has no video endpoint. Choose Audio, or use the Video tab for Carrier Video/Both.')
            return
        if self._preview is None:self._render_preview()
        if self._preview is None:return
        base=groovebox_paths.layers_dir(getattr(self.host,'_current_project_path',None))
        p=os.path.join(base,'carrier_bound_all_sound_layers.wav')
        write_wav(p,self._preview,self._preview_sr); groovebox_paths.index_file(p,'carrier_layer_render',getattr(self.host,'_current_project_path',None))
        old_video=str(getattr(self.host,'imported_video_path','') or '')
        old_meta=getattr(self.host,'imported_video_meta',{}) or {}
        if hasattr(self.host,'_load_wav_path'): self.host._load_wav_path(p)
        if mode=='Both':
            if old_video:
                self.host.imported_video_path=old_video; self.host.imported_video_meta=old_meta
            else:
                QMessageBox.information(self,'Bind All Layers to Carrier','Audio was bound to the carrier. No existing Carrier Video was present, so use the Video tab to create/bind the video half of Both.')
        setattr(self.host,'carrier_binding_source','signal_lab_all_layers')
        setattr(self.host,'carrier_binding_mode',mode.lower())
        setattr(self.host,'carrier_bound_layers_state',self.export_state())
        self._state_changed(); self.report.setPlainText(f'Bound ALL sound layers → Carrier {mode}: {p}')

    def _record_layer(self):
        dur=max(.1,min(600,float(self.duration.value()))); sr=int(self.sr.value()); recdir=groovebox_paths.recordings_dir(getattr(self.host,'_current_project_path',None)); path=os.path.join(recdir,f'groovebox_record_layer_{int(time.time()*1000)}.wav'); self.report.setPlainText(f'Recording {dur:.2f}s…')
        device=self.cmb_record_input.currentData() if hasattr(self,'cmb_record_input') else None
        def work():
            from audio_os_backend import sd
            kwargs={'samplerate':sr,'channels':1,'dtype':'float32'}
            if device is not None:kwargs['device']=int(device)
            arr=sd.rec(max(1,int(round(dur*sr))),**kwargs); sd.wait(); write_wav(path,np.asarray(arr,dtype=np.float32).reshape(-1),sr); return path
        opt=getattr(self.host,'_scode_optimizer',None)
        if opt is not None and hasattr(opt,'submit_pooled'):
            def done(result,error): self._record_finished(str(result or ''), '' if error is None else str(error))
            opt.submit_pooled('audio_record',(path,dur,sr),work,policy='side_effect',format_id='audio',side_effecting=True,callback=done,qt_callback=True)
        else:
            def legacy():
                try:self.record_ready.emit(work(),'')
                except Exception as e:self.record_ready.emit('',str(e))
            threading.Thread(target=legacy,daemon=True).start()
    def _record_finished(self,path,error):
        if error:QMessageBox.warning(self,'Record failed',error);return
        groovebox_paths.index_file(path,'recording',getattr(self.host,'_current_project_path',None)); self._add_layer(self._layer_default(f'Record {len(self.layers)+1}','record',path)); self._refresh_recordings_table(); self.report.setPlainText('Recorded layer: '+path)

SignalLab=LayeredSignalLab
