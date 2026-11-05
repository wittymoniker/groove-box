#!/usr/bin/env python3
"""Optional multitrack audio/video clip timeline for Groovebox.

Independent, non-destructive timeline editor. Source files are never modified;
clip boundaries are stored as timeline start + source in/out points. Rendering
uses the Groovebox-local FFmpeg resolver and publishes via a temporary file.
"""
from __future__ import annotations
import json, os, subprocess, tempfile
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QGroupBox, QHeaderView,
    QProgressBar, QLineEdit)
from groovebox_media_tools import resolve_local_tool

MEDIA_FILTER = ('Media files (*.wav *.wave *.mp3 *.flac *.ogg *.m4a *.aac *.opus '
                '*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.mpeg *.mpg *.ogv *.wmv *.obj);;'
                '3D models (*.obj);;All files (*)')
# GROOVEBOX_R23R_OBJ_SCENE_20261103: OBJ rows are 3D layers; per-row settings live in the Kind cell.
OBJ_TEXTURES = ('mtl', 'none', 'image', 'video', 'scene')

class ClipTimelineStudio(QWidget):
    """A compact timeline/mixer with arbitrary clip regions and layer order."""
    COLS = ['Media', 'Kind', 'Timeline start (s)', 'Source in (s)', 'Source out (s)',
            'Track / layer', 'Gain (dB)', 'Opacity', 'Mute', 'Pan (-1..1)', 'Width (0..1)', 'Video blend']
    # GROOVEBOX_R23R_CLIP_STUDIO_MIX_20261101
    BLENDS = ('over', 'screen', 'add', 'multiply', 'difference', 'lighten', 'darken', 'average')
    TIPS = {'Pan (-1..1)': 'Stereo position: -1 left · 0 centre · 1 right (equal-power).',
            'Width (0..1)': 'Stereo width: 0 = mono fold-down · 1 = full source stereo.',
            'Video blend': 'How this video layer combines with the layers below: ' + ', '.join(('over', 'screen', 'add', 'multiply', 'difference', 'lighten', 'darken', 'average')),
            'Opacity': '0 = invisible · 1 = fully opaque video layer.',
            'Track / layer': 'Higher layers are composited on top (video) — audio mixes all tracks.'}
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Groovebox · Multitrack Clip Studio')
        self.setMinimumSize(1050, 620)
        self._build_ui()

    def _build_ui(self):
        root=QVBoxLayout(self)
        intro=QLabel('MULTITRACK CLIP STUDIO  ·  Arrange audio and video on independent layers. '
                     'Set any source in/out region and timeline start; originals remain untouched.')
        intro.setWordWrap(True); root.addWidget(intro)
        actions=QHBoxLayout()
        badd=QPushButton('＋ Add audio/video…'); badd.clicked.connect(self.add_media); actions.addWidget(badd)
        bremove=QPushButton('Remove selected'); bremove.clicked.connect(self.remove_selected); actions.addWidget(bremove)
        bclone=QPushButton('Duplicate selected'); bclone.clicked.connect(self.duplicate_selected); actions.addWidget(bclone)
        bsave=QPushButton('Save timeline…'); bsave.clicked.connect(self.save_timeline); actions.addWidget(bsave)
        bload=QPushButton('Load timeline…'); bload.clicked.connect(self.load_timeline); actions.addWidget(bload)
        bobj=QPushButton('🧊 OBJ settings…'); bobj.setToolTip('Texture (MTL / image / video / the scene below), spin, tilt and size of the selected OBJ layer.')
        bobj.clicked.connect(self.edit_obj_settings); actions.addWidget(bobj)
        actions.addStretch(1); root.addLayout(actions)
        hint=QLabel('Double-click a cell to edit · Pan/Width shape each clip\'s stereo image · Video blend mixes video '
                    'layers independently of audio · render audio, video or both.')
        hint.setWordWrap(True); hint.setStyleSheet('color:#8fb4d8;'); root.addWidget(hint)
        self.table=QTableWidget(0,len(self.COLS)); self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for c in range(1,len(self.COLS)): self.table.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents)
        for c,name in enumerate(self.COLS):
            if name in self.TIPS:
                hi=self.table.horizontalHeaderItem(c)
                if hi is not None: hi.setToolTip(self.TIPS[name])
        root.addWidget(self.table,1)
        opts=QGroupBox('Timeline / render settings'); grid=QGridLayout(opts)
        self.duration=QDoubleSpinBox(); self.duration.setRange(.1,86400); self.duration.setDecimals(3); self.duration.setValue(30); self.duration.setSuffix(' s')
        self.fps=QSpinBox(); self.fps.setRange(1,120); self.fps.setValue(30)
        self.width=QSpinBox(); self.width.setRange(160,3840); self.width.setSingleStep(160); self.width.setValue(1920)
        self.height=QSpinBox(); self.height.setRange(90,2160); self.height.setSingleStep(90); self.height.setValue(1080)
        self.audio_rate=QComboBox(); self.audio_rate.addItems(['44100','48000','96000']); self.audio_rate.setCurrentText('48000')
        self.keep_audio=QCheckBox('Mix audio from video sources'); self.keep_audio.setChecked(True)
        self.fade_edges=QCheckBox('Apply short anti-click audio fades'); self.fade_edges.setChecked(True)
        for c,(label,w) in enumerate([('Duration',self.duration),('FPS',self.fps),('Width',self.width),('Height',self.height),('Audio Hz',self.audio_rate)]):
            grid.addWidget(QLabel(label),0,c*2); grid.addWidget(w,0,c*2+1)
        grid.addWidget(self.keep_audio,1,0,1,3); grid.addWidget(self.fade_edges,1,3,1,3)
        root.addWidget(opts)
        bottom=QHBoxLayout(); self.status=QLabel('Ready · add media to create a timeline.'); self.status.setWordWrap(True); bottom.addWidget(self.status,1)
        self.audio_btn=QPushButton('Render audio mix…'); self.audio_btn.setToolTip('Audio only: every unmuted clip with its gain, pan and width (WAV / FLAC / lossless .MCC).')
        self.audio_btn.clicked.connect(self.export_audio); bottom.addWidget(self.audio_btn)
        self.video_only_btn=QPushButton('Render video only…'); self.video_only_btn.setToolTip('Video layers only (blend modes, opacity, layer order), no audio track.')
        self.video_only_btn.clicked.connect(lambda: self.export_video(video_only=True)); bottom.addWidget(self.video_only_btn)
        self.export_btn=QPushButton('Render timeline to MP4…'); self.export_btn.clicked.connect(self.export_video); bottom.addWidget(self.export_btn)
        root.addLayout(bottom)

    def _row_data(self, row):
        def cell(c): return self.table.item(row,c).text().strip() if self.table.item(row,c) else ''
        path=cell(0); kind=cell(1).lower()
        start=float(cell(2) or 0); src_in=float(cell(3) or 0); src_out=float(cell(4) or 0)
        track=int(float(cell(5) or 1)); gain=float(cell(6) or 0); opacity=float(cell(7) or 1)
        mute=cell(8).lower() in ('yes','true','1','muted')
        pan=float(cell(9) or 0) if self.table.columnCount()>9 else 0.0
        width=float(cell(10) or 1) if self.table.columnCount()>10 else 1.0
        blend=(cell(11) or 'over').lower() if self.table.columnCount()>11 else 'over'
        if not -1.0<=pan<=1.0: raise ValueError(f'Pan on row {row+1} must be between -1 and 1.')
        if not 0.0<=width<=1.0: raise ValueError(f'Width on row {row+1} must be between 0 and 1.')
        if blend not in self.BLENDS: raise ValueError(f'Video blend on row {row+1} must be one of: '+', '.join(self.BLENDS))
        if not os.path.isfile(path): raise ValueError(f'Media file is missing: {path}')
        if start<0 or src_in<0 or src_out<=src_in: raise ValueError(f'Invalid clip region on row {row+1}; source out must be greater than source in.')
        if track<1 or not 0<=opacity<=1: raise ValueError(f'Invalid track or opacity on row {row+1}.')
        rec={'path':path,'kind':kind,'start':start,'in':src_in,'out':src_out,'track':track,'gain':gain,'opacity':opacity,'mute':mute,
             'pan':pan,'width':width,'blend':blend}
        if kind=='obj':
            it=self.table.item(row,1)
            try: rec['obj']=json.loads(it.data(Qt.ItemDataRole.UserRole) or '{}') if it is not None else {}
            except Exception: rec['obj']={}
        return rec

    def _add_row(self, rec):
        r=self.table.rowCount(); self.table.insertRow(r)
        vals=[rec['path'],rec['kind'],rec.get('start',0),rec.get('in',0),rec.get('out',max(.1,rec.get('duration',10))),rec.get('track',1),rec.get('gain',0),rec.get('opacity',1),'Yes' if rec.get('mute',False) else 'No',
              rec.get('pan',0),rec.get('width',1),rec.get('blend','over')]
        for c,v in enumerate(vals):
            it=QTableWidgetItem(str(v)); it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            if c in (1,): it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if c==1 and str(rec.get('kind'))=='obj':
                it.setData(Qt.ItemDataRole.UserRole, json.dumps(rec.get('obj') or {'texture':'mtl','spin_deg_s':30.0,'tilt_deg':15.0,'scale':0.8}))
            self.table.setItem(r,c,it)
        self._update_estimate()

    def add_media(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Add audio/video media','',MEDIA_FILTER)
        if not paths:return
        ffprobe=resolve_local_tool('ffprobe')
        for p in paths:
            ext=Path(p).suffix.lower(); kind='obj' if ext=='.obj' else ('video' if ext in {'.mp4','.m4v','.mov','.mkv','.webm','.avi','.mpeg','.mpg','.ogv','.wmv'} else 'audio')
            dur=10.0
            if ffprobe and kind!='obj':
                try:
                    cp=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',p],capture_output=True,text=True,timeout=10)
                    if cp.returncode==0: dur=max(.1,float(cp.stdout.strip()))
                except Exception: pass
            self._add_row({'path':os.path.abspath(p),'kind':kind,'start':0,'in':0,'out':round(dur,3),'track':1,'gain':0,'opacity':1,'mute':False})
        self.status.setText(f'Added {len(paths)} media item(s). Edit start/in/out/track cells to define arbitrary boundaries.')

    def remove_selected(self):
        rows=sorted({x.row() for x in self.table.selectedIndexes()},reverse=True)
        for r in rows:self.table.removeRow(r)
        self._update_estimate()

    def duplicate_selected(self):
        rows=sorted({x.row() for x in self.table.selectedIndexes()})
        for r in rows:
            try:
                rec=self._row_data(r); rec['start']+=max(.05,rec['out']-rec['in']); self._add_row(rec)
            except Exception as e: QMessageBox.warning(self,'Duplicate clip',str(e)); return

    def _records(self): return [self._row_data(r) for r in range(self.table.rowCount())]

    def _update_estimate(self):
        try:
            end=max([float(self.table.item(r,2).text() or 0)+max(0,float(self.table.item(r,4).text() or 0)-float(self.table.item(r,3).text() or 0)) for r in range(self.table.rowCount())] or [0])
            self.status.setText(f'{self.table.rowCount()} clip(s) · estimated end {end:.3f} s · rows are editable; source files are not changed.')
        except Exception: pass

    def save_timeline(self):
        path,_=QFileDialog.getSaveFileName(self,'Save timeline','groovebox-timeline.json','Groovebox timeline (*.json)')
        if not path:return
        try:
            payload={'format':'groovebox-clip-timeline','version':1,'duration':self.duration.value(),'fps':self.fps.value(),'width':self.width.value(),'height':self.height.value(),'audio_rate':int(self.audio_rate.currentText()),'mix_video_audio':self.keep_audio.isChecked(),'anti_click_fades':self.fade_edges.isChecked(),'clips':self._records()}
            Path(path).write_text(json.dumps(payload,indent=2),encoding='utf-8'); self.status.setText('Timeline saved: '+path)
        except Exception as e: QMessageBox.warning(self,'Save timeline',str(e))

    def load_timeline(self):
        path,_=QFileDialog.getOpenFileName(self,'Load timeline','','Groovebox timeline (*.json);;JSON (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            if data.get('format')!='groovebox-clip-timeline' or not isinstance(data.get('clips'),list): raise ValueError('This is not a supported Groovebox clip timeline.')
            self.table.setRowCount(0)
            for rec in data['clips']: self._add_row(rec)
            for name,field in [('duration','duration'),('fps','fps'),('width','width'),('height','height')]:
                if field in data:getattr(self,name).setValue(data[field])
            if 'audio_rate' in data:self.audio_rate.setCurrentText(str(data['audio_rate']))
            self.keep_audio.setChecked(bool(data.get('mix_video_audio',True))); self.fade_edges.setChecked(bool(data.get('anti_click_fades',True)))
            self.status.setText(f'Loaded {len(data["clips"])} clip(s).')
        except Exception as e: QMessageBox.warning(self,'Load timeline',str(e))

    @staticmethod
    def _pan_width_filter(pan, width):
        """Exact stereo matrix: width (mid/side) then equal-power pan."""
        import math as _m
        w=max(0.0,min(1.0,float(width))); a=(1.0+w)/2.0; b=(1.0-w)/2.0
        th=(max(-1.0,min(1.0,float(pan)))+1.0)*_m.pi/4.0; gl=_m.cos(th)*_m.sqrt(2.0); gr=_m.sin(th)*_m.sqrt(2.0)
        return (f'aformat=channel_layouts=stereo,'
                f'pan=stereo|c0={gl*a:.6f}*c0+{gl*b:.6f}*c1|c1={gr*b:.6f}*c0+{gr*a:.6f}*c1')

    def _audio_graph(self, clips, duration, rate, input_offset):
        graph=[]; labels=[]
        for j,c in enumerate(clips):
            if c['mute'] or c['start']>=duration:continue
            idx=j+input_offset; has_audio=c['kind']=='audio'
            if not has_audio:
                probe=resolve_local_tool('ffprobe')
                if probe:
                    try:
                        pr=subprocess.run([probe,'-v','error','-select_streams','a:0','-show_entries','stream=index','-of','csv=p=0',c['path']],capture_output=True,text=True,timeout=10)
                        has_audio=bool(pr.stdout.strip())
                    except Exception:has_audio=False
            if not has_audio:continue
            dur=min(c['out']-c['in'],duration-c['start']); label=f'a{j}'; delay=int(round(c['start']*1000)); gain=10**(c['gain']/20)
            af=f'atrim=start={c["in"]:.6f}:duration={dur:.6f},asetpts=PTS-STARTPTS,{self._pan_width_filter(c.get("pan",0),c.get("width",1))},volume={gain:.7f}'
            if self.fade_edges.isChecked() and dur>.04:af+=f',afade=t=in:st=0:d={min(.015,dur/3):.6f},afade=t=out:st={max(0,dur-min(.02,dur/3)):.6f}:d={min(.02,dur/3):.6f}'
            af+=f',adelay={delay}|{delay}[{label}]'; graph.append(f'[{idx}:a]{af}'); labels.append(f'[{label}]')
        if labels:
            graph.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0,apad,atrim=duration={duration:.6f},aresample={rate}[outa]')
        else:
            graph.append(f'anullsrc=r={rate}:cl=stereo,atrim=duration={duration:.6f}[outa]')
        return graph

    def export_audio(self):
        ff=resolve_local_tool('ffmpeg')
        if not ff:
            QMessageBox.warning(self,'Render audio mix','Groovebox-local FFmpeg is not available.'); return
        try: clips=self._records()
        except Exception as e: QMessageBox.warning(self,'Render audio mix',str(e)); return
        if not clips: QMessageBox.information(self,'Render audio mix','Add at least one clip first.'); return
        path,flt=QFileDialog.getSaveFileName(self,'Render audio mix','groovebox-mix.wav','WAV audio (*.wav);;FLAC audio (*.flac);;MCC lossless audio (*.MCC)')
        if not path:return
        low=path.lower(); mcc=low.endswith('.mcc') or 'MCC' in flt
        if not (low.endswith('.wav') or low.endswith('.flac') or low.endswith('.mcc')): path+=('.MCC' if mcc else ('.flac' if 'FLAC' in flt else '.wav'))
        duration=self.duration.value(); rate=int(self.audio_rate.currentText())
        cmd=[ff,'-hide_banner','-y']
        for c in clips: cmd+=['-i',c['path']]
        graph=self._audio_graph(clips,duration,rate,0)
        tmp=path+'.part'+('.wav' if mcc else os.path.splitext(path)[1])
        if mcc:
            cmd+=['-filter_complex',';'.join(graph),'-map','[outa]','-t',f'{duration:.6f}','-f','f32le','-ac','2','-ar',str(rate),'pipe:1']
        else:
            cmd+=['-filter_complex',';'.join(graph),'-map','[outa]','-t',f'{duration:.6f}','-c:a',('flac' if path.lower().endswith('.flac') else 'pcm_s24le'),tmp]
        self.audio_btn.setEnabled(False); self.status.setText('Rendering audio mix…')
        try:
            cp=subprocess.run(cmd,capture_output=True,timeout=max(120,int(duration*10)))
            if cp.returncode!=0: raise RuntimeError((cp.stderr or b'FFmpeg audio render failed')[-3000:].decode('utf-8','replace'))
            if mcc:
                import numpy as _np
                import mcc_media as _mm
                x=_np.frombuffer(cp.stdout,dtype=_np.float32).reshape(-1,2)
                _mm.encode_audio(path,x,rate,extra={'source':'Multitrack Clip Studio'})
            else:
                os.replace(tmp,path)
            self.status.setText(f'Audio mix rendered: {path}')
        except Exception as e:
            try:
                if os.path.exists(tmp): os.remove(tmp)
            except OSError: pass
            QMessageBox.warning(self,'Render audio mix',str(e)); self.status.setText('Audio render failed; sources untouched.')
        finally: self.audio_btn.setEnabled(True)

    def edit_obj_settings(self):
        rows=sorted({x.row() for x in self.table.selectedIndexes()})
        rows=[r for r in rows if (self.table.item(r,1) and self.table.item(r,1).text().strip().lower()=='obj')]
        if not rows:
            QMessageBox.information(self,'OBJ settings','Select an OBJ row first (add a .obj with ＋ Add).'); return
        it=self.table.item(rows[0],1)
        try: cur=json.loads(it.data(Qt.ItemDataRole.UserRole) or '{}')
        except Exception: cur={}
        from PyQt6.QtWidgets import QDialog, QFormLayout
        dlg=QDialog(self); dlg.setWindowTitle('OBJ layer settings'); form=QFormLayout(dlg)
        tex=QComboBox(); tex.addItems(['mtl — the model\'s own texture','none — shaded colour','image — choose a picture',
                                         'video — a video wraps the model (follows time)','scene — the timeline layers below wrap the model'])
        tex.setCurrentIndex(OBJ_TEXTURES.index(cur.get('texture','mtl')) if cur.get('texture','mtl') in OBJ_TEXTURES else 0)
        path=QLineEdit(cur.get('texture_path','')); bpick=QPushButton('Choose…')
        def pick():
            p,_=QFileDialog.getOpenFileName(dlg,'Texture image or video','', 'Images / video (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.webm *.avi);;All files (*)')
            if p: path.setText(p)
        bpick.clicked.connect(pick)
        row=QHBoxLayout(); row.addWidget(path,1); row.addWidget(bpick)
        spin=QDoubleSpinBox(); spin.setRange(-720,720); spin.setValue(float(cur.get('spin_deg_s',30.0))); spin.setSuffix(' °/s')
        tilt=QDoubleSpinBox(); tilt.setRange(-90,90); tilt.setValue(float(cur.get('tilt_deg',15.0))); tilt.setSuffix(' °')
        scale=QDoubleSpinBox(); scale.setRange(0.05,4.0); scale.setSingleStep(0.05); scale.setValue(float(cur.get('scale',0.8)))
        res=QComboBox(); res.addItems(['Half resolution (fast)','Full resolution']); res.setCurrentIndex(1 if cur.get('full_res') else 0)
        form.addRow('Texture',tex); form.addRow('Texture file',row); form.addRow('Spin',spin); form.addRow('Tilt',tilt); form.addRow('Size',scale); form.addRow('Render',res)
        ok=QPushButton('Apply'); form.addRow(ok)
        def apply():
            d={'texture':OBJ_TEXTURES[tex.currentIndex()],'texture_path':path.text().strip(),'spin_deg_s':spin.value(),
               'tilt_deg':tilt.value(),'scale':scale.value(),'full_res':res.currentIndex()==1}
            for r in rows:
                self.table.item(r,1).setData(Qt.ItemDataRole.UserRole, json.dumps(d))
            self.status.setText(f'OBJ settings applied to {len(rows)} row(s): texture {d["texture"]}.'); dlg.accept()
        ok.clicked.connect(apply); dlg.show(); self._obj_dlg=dlg

    def _materialize_obj_layers(self, clips, duration, fps, w, h, rate, ff, work):
        """Render every OBJ row to an alpha .mov layer (parallel, chunked), then
        treat it as a normal video layer. 'scene' textures first render the
        non-OBJ layers BELOW that OBJ (lower track) and wrap them onto it."""
        import obj_scene
        out=[]
        for i,c in enumerate(clips):
            if c.get('kind')!='obj':
                out.append(c); continue
            cfg=dict(c.get('obj') or {})
            dur=max(0.1,c['out']-c['in'])
            ow,oh=(w,h) if cfg.get('full_res') else (max(2,(w//2)//2*2),max(2,(h//2)//2*2))
            tex_mode=cfg.get('texture','mtl'); tex_path=cfg.get('texture_path') or None
            if tex_mode=='scene':
                below=[x for x in clips if x.get('kind')=='video' and x['track']<=c['track']]
                if below:
                    scene=os.path.join(work,f'scene_{i}.mp4')
                    self.status.setText(f'OBJ {i+1}: rendering the scene below as its texture…')
                    self._ffmpeg_render(below, scene, duration, fps, 512, 512, rate, True, ff)
                    tex_path=scene
                else:
                    tex_mode='mtl'
            layer=os.path.join(work,f'obj_{i}.mov')
            def prog(done,n,_i=i):
                self.status.setText(f'OBJ {_i+1}: {done}/{n} frames (parallel chunks)')
                try:
                    from PyQt6.QtWidgets import QApplication; QApplication.processEvents()
                except Exception: pass
            obj_scene.render_clip(c['path'], layer, ow, oh, fps, dur, params=cfg, texture_mode=tex_mode,
                                  texture_path=tex_path, ffmpeg=ff, progress=prog)
            nc=dict(c); nc.update({'path':layer,'kind':'video','in':0.0,'out':dur}); out.append(nc)
        return out

    def _ffmpeg_render(self, clips, out_path, duration, fps, w, h, rate, video_only, ff):
        """Build + run the FFmpeg graph for these (already materialised) clips."""
        cmd=[ff,'-hide_banner','-y','-f','lavfi','-i',f'color=c=0x3e3f42:s={w}x{h}:r={fps}:d={duration}']
        for c in clips: cmd += ['-i',c['path']]
        graph=[f'[0:v]format=rgba[base]']; current='base'
        video_clips=[(i,c) for i,c in enumerate(clips) if c['kind']=='video']
        for j,(i,c) in enumerate(sorted(video_clips,key=lambda z:(z[1]['track'],z[1]['start']))):
            idx=i+1; dur=c['out']-c['in']; start=c['start']; end=min(duration,start+dur)
            if end<=start:continue
            v=f'v{j}'; nxt=f'base{j}'
            graph.append(f'[{idx}:v]trim=start={c["in"]:.6f}:duration={dur:.6f},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0,format=rgba,colorchannelmixer=aa={c["opacity"]:.4f}[{v}]')
            mode=c.get('blend','over')
            if mode=='over':
                graph.append(f'[{current}][{v}]overlay=0:0:eof_action=pass:enable=\'between(t,{start:.6f},{end:.6f})\'[{nxt}]')
            else:
                vd=f'vd{j}'
                graph.append(f'[{v}]setpts=PTS+{start:.6f}/TB,tpad=start_duration={start:.6f}:color=black@0,format=rgba[{vd}]')
                graph.append(f'[{current}][{vd}]blend=all_mode={mode}:all_opacity={c["opacity"]:.4f}:shortest=0:repeatlast=1:enable=\'between(t,{start:.6f},{end:.6f})\'[{nxt}]')
            current=nxt
        graph.append(f'[{current}]trim=duration={duration:.6f},setpts=PTS-STARTPTS[outv]')
        if not video_only:
            graph += self._audio_graph(clips, duration, rate, 1)
        maps=['-map','[outv]'] + ([] if video_only else ['-map','[outa]'])
        acodec=['-an'] if video_only else ['-c:a','aac','-b:a','192k']
        cmd += ['-filter_complex',';'.join(graph),*maps,'-t',f'{duration:.6f}','-r',str(fps),'-c:v','libx264','-pix_fmt','yuv420p',*acodec,'-movflags','+faststart',out_path]
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
        if cp.returncode!=0 and 'libx264' in (cp.stderr or ''):
            i=cmd.index('libx264'); cmd[i:i+1]=['mpeg4','-q:v','2']
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
        if cp.returncode!=0:raise RuntimeError((cp.stderr or cp.stdout or 'FFmpeg render failed')[-3500:])
        return out_path

    def export_video(self, video_only=False):
        ff=resolve_local_tool('ffmpeg')
        if not ff:
            QMessageBox.warning(self,'Render timeline','Groovebox-local FFmpeg is not available. Run the normal first-launch dependency provisioning step.'); return
        try: clips=self._records()
        except Exception as e: QMessageBox.warning(self,'Render timeline',str(e)); return
        if not clips: QMessageBox.information(self,'Render timeline','Add at least one audio or video clip first.'); return
        path,_=QFileDialog.getSaveFileName(self,'Render timeline','groovebox-timeline.mp4','MP4 video (*.mp4)')
        if not path:return
        if not path.lower().endswith('.mp4'):path+='.mp4'
        duration=self.duration.value(); fps=self.fps.value(); w=self.width.value(); h=self.height.value(); rate=int(self.audio_rate.currentText())
        if any(c['start']>=duration for c in clips):
            QMessageBox.warning(self,'Render timeline','A clip starts at or after the selected timeline duration. Increase duration or adjust its start.'); return
        tmp=path+'.part.mp4';
        try:
            if os.path.exists(tmp):os.remove(tmp)
        except OSError:pass
        if any(c.get('kind')=='obj' for c in clips):
            # GROOVEBOX_R23R_OBJ_SCENE_20261103: OBJ rows → alpha video layers (parallel chunked render).
            work=tempfile.mkdtemp(prefix='gb_obj_')
            self.export_btn.setEnabled(False)
            try:
                clips=self._materialize_obj_layers(clips, duration, fps, w, h, rate, ff, work)
                self.status.setText('Compositing the timeline…')
                self._ffmpeg_render(clips, tmp, duration, fps, w, h, rate, video_only, ff)
                os.replace(tmp,path); self.status.setText(f'Render complete: {path}')
                QMessageBox.information(self,'Render timeline','Finished rendering:\n'+path)
            except Exception as e:
                try:
                    if os.path.exists(tmp):os.remove(tmp)
                except OSError:pass
                QMessageBox.warning(self,'Render timeline',str(e)); self.status.setText('Render failed; source media and timeline were preserved.')
            finally:self.export_btn.setEnabled(True)
            return
        cmd=[ff,'-hide_banner','-y','-f','lavfi','-i',f'color=c=0x3e3f42:s={w}x{h}:r={fps}:d={duration}']
        for c in clips: cmd += ['-i',c['path']]
        graph=[f'[0:v]format=rgba[base]']; current='base'
        video_clips=[(i,c) for i,c in enumerate(clips) if c['kind']=='video']
        for j,(i,c) in enumerate(sorted(video_clips,key=lambda z:(z[1]['track'],z[1]['start']))):
            idx=i+1; dur=c['out']-c['in']; start=c['start']; end=min(duration,start+dur)
            if end<=start:continue
            v=f'v{j}'; nxt=f'base{j}'
            graph.append(f'[{idx}:v]trim=start={c["in"]:.6f}:duration={dur:.6f},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=rgba,colorchannelmixer=aa={c["opacity"]:.4f}[{v}]')
            mode=c.get('blend','over')
            if mode=='over':
                graph.append(f'[{current}][{v}]overlay=0:0:eof_action=pass:enable=\'between(t,{start:.6f},{end:.6f})\'[{nxt}]')
            else:
                # Independent video blend: the layer is delayed to its timeline start and
                # blended over the running composite only while the clip is on.
                vd=f'vd{j}'
                graph.append(f'[{v}]setpts=PTS+{start:.6f}/TB,tpad=start_duration={start:.6f}:color=black@0,format=rgba[{vd}]')
                graph.append(f'[{current}][{vd}]blend=all_mode={mode}:all_opacity={c["opacity"]:.4f}:shortest=0:repeatlast=1:enable=\'between(t,{start:.6f},{end:.6f})\'[{nxt}]')
            current=nxt
        graph.append(f'[{current}]trim=duration={duration:.6f},setpts=PTS-STARTPTS[outv]')
        if not video_only:
            graph += self._audio_graph(clips, duration, rate, 1)
        maps=['-map','[outv]'] + ([] if video_only else ['-map','[outa]'])
        acodec=['-an'] if video_only else ['-c:a','aac','-b:a','192k']
        cmd += ['-filter_complex',';'.join(graph),*maps,'-t',f'{duration:.6f}','-r',str(fps),'-c:v','libx264','-pix_fmt','yuv420p',*acodec,'-movflags','+faststart',tmp]
        self.export_btn.setEnabled(False); self.status.setText('Rendering timeline… this can take a while for large projects.')
        try:
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
            if cp.returncode!=0 and 'libx264' in (cp.stderr or ''):
                # FFmpeg builds without x264: fall back to the built-in MPEG-4 encoder.
                i=cmd.index('libx264'); cmd[i:i+1]=['mpeg4','-q:v','2']
                cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
            if cp.returncode!=0:raise RuntimeError((cp.stderr or cp.stdout or 'FFmpeg render failed')[-3500:])
            if not os.path.isfile(tmp) or os.path.getsize(tmp)<1024:raise RuntimeError('Render produced no usable output file.')
            os.replace(tmp,path); self.status.setText(f'Render complete: {path}')
            QMessageBox.information(self,'Render timeline','Finished rendering:\n'+path)
        except Exception as e:
            try:
                if os.path.exists(tmp):os.remove(tmp)
            except OSError:pass
            QMessageBox.warning(self,'Render timeline',str(e)); self.status.setText('Render failed; source media and timeline were preserved.')
        finally:self.export_btn.setEnabled(True)


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
