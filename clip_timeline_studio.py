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
                '*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.mpeg *.mpg *.ogv *.wmv *.MCC *.mcc *.obj *.png *.jpg *.jpeg *.webp *.bmp *.gif);;'
                'MCC media (*.MCC *.mcc);;3D models (*.obj);;All files (*)')
# GROOVEBOX_R23R_OBJ_SCENE_20261103: OBJ rows are 3D layers; per-row settings live in the Kind cell.
OBJ_TEXTURES = ('mtl', 'none', 'image', 'video', 'scene')


class _ClipJob:
    """Immutable render snapshot; execution is owned by ui_runtime's shared lane."""
    def __init__(self, fn):
        self.fn = fn


def _clip_pan_width_filter(pan, width):
    import math
    w=max(0.0,min(1.0,float(width))); a=(1.0+w)/2.0; b=(1.0-w)/2.0
    th=(max(-1.0,min(1.0,float(pan)))+1.0)*math.pi/4.0
    gl=math.cos(th)*math.sqrt(2.0); gr=math.sin(th)*math.sqrt(2.0)
    return (f'aformat=channel_layouts=stereo,'
            f'pan=stereo|c0={gl*a:.6f}*c0+{gl*b:.6f}*c1|c1={gr*b:.6f}*c0+{gr*a:.6f}*c1')


def _clip_audio_graph(clips, duration, rate, input_offset, fade_edges, ffprobe, in_idx=None):
    graph=[]; labels=[]
    for j,c in enumerate(clips):
        if c.get('mute') or c['start']>=duration or c['kind'] in ('text','image','obj'): continue
        idx=(in_idx[j] if in_idx is not None and j in in_idx else j+input_offset); has_audio=c['kind']=='audio'
        if not has_audio and ffprobe:
            try:
                pr=subprocess.run([ffprobe,'-v','error','-select_streams','a:0','-show_entries','stream=index','-of','csv=p=0',c['path']],capture_output=True,text=True,timeout=10)
                has_audio=bool(pr.stdout.strip())
            except Exception: has_audio=False
        if not has_audio: continue
        dur=min(c['out']-c['in'],duration-c['start'])
        if dur<=0: continue
        label=f'a{j}'; delay=int(round(c['start']*1000)); gain=10**(c['gain']/20)
        af=f'atrim=start={c["in"]:.6f}:duration={dur:.6f},asetpts=PTS-STARTPTS,{_clip_pan_width_filter(c.get("pan",0),c.get("width",1))},volume={gain:.7f}'
        if fade_edges and dur>.04:
            af+=f',afade=t=in:st=0:d={min(.015,dur/3):.6f},afade=t=out:st={max(0,dur-min(.02,dur/3)):.6f}:d={min(.02,dur/3):.6f}'
        af+=f',adelay={delay}|{delay}[{label}]'
        graph.append(f'[{idx}:a]{af}'); labels.append(f'[{label}]')
    if labels:
        graph.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0,apad,atrim=duration={duration:.6f},aresample={rate}[outa]')
    else:
        graph.append(f'anullsrc=r={rate}:cl=stereo,atrim=duration={duration:.6f}[outa]')
    return graph


# R32.6 CLIP FX: essential video effects per clip (all optional; empty dict = unchanged).
FX_KEYS = (('speed','Speed ×',0.25,4.0,1.0),('brightness','Brightness',-1.0,1.0,0.0),('contrast','Contrast',0.0,3.0,1.0),
           ('saturation','Saturation',0.0,3.0,1.0),('hue','Hue shift °',-180.0,180.0,0.0),('blur','Blur',0.0,30.0,0.0),
           ('sharpen','Sharpen',0.0,3.0,0.0),('zoom','Zoom ×',1.0,4.0,1.0),('vignette','Vignette',0.0,1.0,0.0),
           ('fade_in','Fade in s',0.0,10.0,0.0),('fade_out','Fade out s',0.0,10.0,0.0),('rotate','Rotate °',-180.0,180.0,0.0))
FX_FLAGS = (('mirror','Mirror'),('flip','Flip'),('invert','Invert'),('grayscale','Grayscale'),('edges','Edge glow'))


def clip_fx_chain(fx, dur, width, height):
    f=[]
    sp=float(fx.get('speed',1.0) or 1.0)
    if abs(sp-1.0)>1e-6: f.append(f'setpts=PTS/{sp:.6f}')
    z=float(fx.get('zoom',1.0) or 1.0)
    if z>1.0001: f.append(f'crop=iw/{z:.4f}:ih/{z:.4f}')
    if fx.get('mirror'): f.append('hflip')
    if fx.get('flip'): f.append('vflip')
    rot=float(fx.get('rotate',0) or 0)
    if abs(rot)>0.01: f.append(f'rotate={rot*3.14159265/180:.6f}:fillcolor=black@0')
    b,c,sat=float(fx.get('brightness',0) or 0),float(fx.get('contrast',1) or 1),float(fx.get('saturation',1) or 1)
    if abs(b)>1e-6 or abs(c-1)>1e-6 or abs(sat-1)>1e-6: f.append(f'eq=brightness={b:.4f}:contrast={c:.4f}:saturation={sat:.4f}')
    h=float(fx.get('hue',0) or 0)
    if abs(h)>0.01: f.append(f'hue=h={h:.3f}')
    if fx.get('grayscale'): f.append('hue=s=0')
    bl=float(fx.get('blur',0) or 0)
    if bl>0.01: f.append(f'gblur=sigma={bl:.3f}')
    sh=float(fx.get('sharpen',0) or 0)
    if sh>0.01: f.append(f'unsharp=5:5:{sh:.3f}')
    if fx.get('edges'): f.append('edgedetect=mode=colormix:high=0.2')
    if fx.get('invert'): f.append('negate')
    vg=float(fx.get('vignette',0) or 0)
    if vg>0.01: f.append(f'vignette=angle={0.2+1.2*vg:.4f}')
    return ''.join(x+',' for x in f)


def clip_fade_chain(fx, dur):
    out=''
    fi=float(fx.get('fade_in',0) or 0); fo=float(fx.get('fade_out',0) or 0)
    if fi>0: out+=f',fade=t=in:st=0:d={fi:.4f}:alpha=1'
    if fo>0: out+=f',fade=t=out:st={max(0.0,dur-fo):.4f}:d={fo:.4f}:alpha=1'
    return out


def drawtext_filter(c, width, height):
    fx=c.get('fx') or {}
    def esc(t): return str(t).replace('\\','\\\\').replace(':','\\:').replace("'","\\'").replace('%','\\%')
    size=int(fx.get('font_size',64)); col=str(fx.get('color','white')); pos=str(fx.get('position','center'))
    xy={'center':('(w-text_w)/2','(h-text_h)/2'),'top':('(w-text_w)/2','h*0.08'),'bottom':('(w-text_w)/2','h*0.86-text_h'),
        'left':('w*0.05','(h-text_h)/2'),'right':('w*0.95-text_w','(h-text_h)/2')}.get(pos,('(w-text_w)/2','(h-text_h)/2'))
    start=c['start']; end=start+(c['out']-c['in'])
    alpha=f"if(lt(t-{start:.3f},0.4),(t-{start:.3f})/0.4,if(gt(t,{end-0.4:.3f}),({end:.3f}-t)/0.4,1))" if fx.get('fade',True) else '1'
    box=":box=1:boxcolor=black@0.45:boxborderw=18" if fx.get('box',True) else ''
    return (f"drawtext=text='{esc(fx.get('text','Title'))}':fontsize={size}:fontcolor={col}:x={xy[0]}:y={xy[1]}"
            f"{box}:alpha='{alpha}':enable='between(t,{start:.6f},{end:.6f})'")


def _clip_video_render(clips, out_path, duration, fps, width, height, rate, video_only, ffmpeg, ffprobe, fade_edges, progress):
    """Build and run a self-contained FFmpeg timeline job. No QWidget access."""
    cmd=[ffmpeg,'-hide_banner','-y','-f','lavfi','-i',f'color=c=0x3e3f42:s={width}x{height}:r={fps}:d={duration}']
    # R32.6: image clips loop a still; text clips have no input (drawn with drawtext).
    in_idx={}; n_in=1
    for i,c in enumerate(clips):
        if c['kind']=='text':
            continue
        if c['kind']=='image':
            cmd += ['-loop','1','-framerate',str(fps),'-t',f"{max(0.04,c['out']-c['in']):.6f}",'-i',c['path']]
        else:
            cmd += ['-i',c['path']]
        in_idx[i]=n_in; n_in+=1
    graph=[f'[0:v]format=rgba[base]']; current='base'
    video_clips=[(i,c) for i,c in enumerate(clips) if c['kind'] in ('video','image')]
    for j,(i,c) in enumerate(sorted(video_clips,key=lambda z:(z[1]['track'],z[1]['start']))):
        idx=in_idx[i]; dur=c['out']-c['in']; start=c['start']; end=min(duration,start+dur)
        if end<=start: continue
        v=f'v{j}'; nxt=f'base{j}'
        _trim='' if c['kind']=='image' else f'trim=start={c["in"]:.6f}:duration={dur:.6f},'
        graph.append(f'[{idx}:v]{_trim}setpts=PTS-STARTPTS,{clip_fx_chain(c.get("fx") or {}, dur, width, height)}scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=rgba,colorchannelmixer=aa={c["opacity"]:.4f}{clip_fade_chain(c.get("fx") or {}, dur)}[{v}]')
        mode=c.get('blend','over')
        if mode=='over':
            graph.append(f"[{current}][{v}]overlay=0:0:eof_action=pass:enable='between(t,{start:.6f},{end:.6f})'[{nxt}]")
        else:
            vd=f'vd{j}'
            graph.append(f'[{v}]setpts=PTS+{start:.6f}/TB,tpad=start_duration={start:.6f}:color=black@0,format=rgba[{vd}]')
            graph.append(f"[{current}][{vd}]blend=all_mode={mode}:all_opacity={c['opacity']:.4f}:shortest=0:repeatlast=1:enable='between(t,{start:.6f},{end:.6f})'[{nxt}]")
        current=nxt
    for k,(i,c) in enumerate([(i,c) for i,c in enumerate(clips) if c['kind']=='text']):
        nxt=f'txt{k}'; graph.append(f'[{current}]{drawtext_filter(c, width, height)}[{nxt}]'); current=nxt
    graph.append(f'[{current}]trim=duration={duration:.6f},setpts=PTS-STARTPTS[outv]')
    if not video_only:
        graph += _clip_audio_graph(clips,duration,rate,1,fade_edges,ffprobe,in_idx)
    maps=['-map','[outv]'] + ([] if video_only else ['-map','[outa]'])
    acodec=['-an'] if video_only else ['-c:a','aac','-b:a','192k']
    cmd += ['-filter_complex',';'.join(graph),*maps,'-t',f'{duration:.6f}','-r',str(fps),'-c:v','libx264','-pix_fmt','yuv420p',*acodec,'-movflags','+faststart',out_path]
    progress('Encoding video/audio timeline in background…')
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
    if cp.returncode!=0 and 'libx264' in (cp.stderr or ''):
        i=cmd.index('libx264'); cmd[i:i+1]=['mpeg4','-q:v','2']
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(duration*10)))
    if cp.returncode!=0:
        raise RuntimeError((cp.stderr or cp.stdout or 'FFmpeg render failed')[-3500:])


# R32.9 CLIP_EXPORT_FORMATS: the timeline renders once (high-quality H.264 master), then is written in the
# chosen container with codecs this FFmpeg build has (each format lists fallbacks, first that works wins).
VIDEO_FORMATS = {
    "mp4":  ("MP4 (H.264 + AAC)",           [["-c:v","libx264","-crf","18","-pix_fmt","yuv420p"],["-c:v","mpeg4","-q:v","2"]], [["-c:a","aac","-b:a","192k"]], ["-movflags","+faststart"]),
    "m4v":  ("M4V (H.264 + AAC)",           [["-c:v","libx264","-crf","18","-pix_fmt","yuv420p"],["-c:v","mpeg4","-q:v","2"]], [["-c:a","aac","-b:a","192k"]], ["-movflags","+faststart","-f","mp4"]),
    "mov":  ("QuickTime MOV",               [["-c:v","libx264","-crf","18","-pix_fmt","yuv420p"],["-c:v","mpeg4","-q:v","2"]], [["-c:a","aac","-b:a","192k"],["-c:a","pcm_s16le"]], []),
    "mkv":  ("Matroska MKV",                [["-c:v","libx264","-crf","18","-pix_fmt","yuv420p"],["-c:v","mpeg4","-q:v","2"]], [["-c:a","flac"],["-c:a","aac","-b:a","192k"]], []),
    "webm": ("WebM (VP9 + Opus)",           [["-c:v","libvpx-vp9","-crf","32","-b:v","0","-row-mt","1"],["-c:v","libvpx","-b:v","4M"]], [["-c:a","libopus","-b:a","160k"],["-c:a","libvorbis","-q:a","6"]], []),
    "avi":  ("AVI (MPEG-4)",                [["-c:v","mpeg4","-q:v","2"],["-c:v","mjpeg","-q:v","3"]], [["-c:a","libmp3lame","-b:a","192k"],["-c:a","pcm_s16le"]], []),
    "mpg":  ("MPEG-2 program stream",       [["-c:v","mpeg2video","-q:v","2"]], [["-c:a","mp2","-b:a","224k"]], ["-f","mpeg"]),
    "ogv":  ("Ogg Theora",                  [["-c:v","libtheora","-q:v","8"]], [["-c:a","libvorbis","-q:a","6"],["-c:a","flac"]], []),
    "wmv":  ("Windows Media WMV",           [["-c:v","wmv2","-q:v","2"]], [["-c:a","wmav2","-b:a","192k"]], []),
    "gif":  ("Animated GIF (no audio)",     [["-vf","split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer"]], [], ["-loop","0"]),
    "mcc":  ("Groovebox lossless .MCC",     [], [], []),
}


def _transcode(ffmpeg, src, dst, ext, video_only, progress):
    import subprocess
    if ext == "mp4":
        os.replace(src, dst); return dst
    if ext == "mcc":
        return _to_mcc(ffmpeg, src, dst, video_only, progress)
    _label, vopts, aopts, extra = VIDEO_FORMATS[ext]
    aopts = [["-an"]] if (video_only or not aopts) else aopts
    last = ""
    for v in vopts:
        for a in aopts:
            progress(f"Writing {_label}…")
            cmd = [ffmpeg, "-hide_banner", "-y", "-i", src, *v, *a, *extra, dst + ".part." + ext]
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            if cp.returncode == 0 and os.path.isfile(dst + ".part." + ext) and os.path.getsize(dst + ".part." + ext) > 256:
                os.replace(dst + ".part." + ext, dst); os.remove(src); return dst
            last = (cp.stderr or "")[-600:]
    try:
        os.remove(dst + ".part." + ext)
    except OSError:
        pass
    raise RuntimeError(f"this FFmpeg cannot write {_label}: {last}")


def _to_mcc(ffmpeg, src, dst, video_only, progress):
    """Decode the rendered master into Groovebox's lossless MCC video (+ audio)."""
    import subprocess, json as _j, numpy as _np, mcc_media as _mm
    pr = subprocess.run([ffmpeg.replace("ffmpeg", "ffprobe") if "ffmpeg" in os.path.basename(ffmpeg) else "ffprobe",
                         "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                         "-of", "json", src], capture_output=True, text=True)
    st = _j.loads(pr.stdout or "{}").get("streams", [{}])[0]
    w, h = int(st.get("width", 0)), int(st.get("height", 0)); num, den = (st.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
    fps = max(1, int(round(float(num) / float(den or 1))))
    if not w or not h:
        raise RuntimeError("could not read the rendered video size for MCC")
    rate = 48000
    vw = _mm.VideoWriter(dst + ".part", w, h, fps, keyframe=max(1, 2 * fps), audio_rate=rate, audio_channels=1)
    p = subprocess.Popen([ffmpeg, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = 0; fb = w * h * 3
    while True:
        b = p.stdout.read(fb)
        if len(b) < fb:
            break
        vw.write(_np.frombuffer(b, _np.uint8).reshape(h, w, 3)); n += 1
        if n % 60 == 0:
            progress(f"MCC: {n} frames")
    p.wait()
    if not video_only:
        a = subprocess.run([ffmpeg, "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"], capture_output=True)
        pcm = _np.frombuffer(a.stdout, _np.float32)
        if pcm.size:
            vw.write_audio(pcm[:, None])
    vw.close()
    os.replace(dst + ".part", dst); os.remove(src)
    return dst


def _format_filter():
    return ";;".join("%s (*.%s)" % (lab, ext.upper() if ext == "mcc" else ext) for ext, (lab, *_r) in VIDEO_FORMATS.items())


def _clip_video_job(snapshot, progress):
    import shutil
    ffmpeg=snapshot['ffmpeg']; ffprobe=snapshot.get('ffprobe')
    path=snapshot['path']; tmp=path+'.part.mp4'
    work=tempfile.mkdtemp(prefix='gb_clip_render_')
    try:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass
        clips=[dict(c) for c in snapshot['clips']]
        if any(c.get('kind')=='obj' for c in clips):
            import obj_scene
            material=[]
            for i,c in enumerate(clips):
                if c.get('kind')!='obj':
                    material.append(c); continue
                cfg=dict(c.get('obj') or {})
                dur=max(.1,c['out']-c['in'])
                w,h=snapshot['width'],snapshot['height']
                ow,oh=(w,h) if cfg.get('full_res') else (max(2,(w//2)//2*2),max(2,(h//2)//2*2))
                tex_mode=cfg.get('texture','mtl'); tex_path=cfg.get('texture_path') or None
                if tex_mode=='scene':
                    below=[x for x in clips if x.get('kind')=='video' and x['track']<=c['track']]
                    if below:
                        scene=os.path.join(work,f'scene_{i}.mp4')
                        progress(f'OBJ {i+1}: preparing underlying scene texture…')
                        _clip_video_render(below,scene,dur,snapshot['fps'],512,512,snapshot['rate'],True,ffmpeg,ffprobe,snapshot['fade_edges'],progress)
                        tex_path=scene
                    else: tex_mode='mtl'
                layer=os.path.join(work,f'obj_{i}.mov')
                progress(f'OBJ {i+1}: rendering model layer off the UI thread…')
                obj_scene.render_clip(c['path'],layer,ow,oh,snapshot['fps'],dur,params=cfg,texture_mode=tex_mode,
                                      texture_path=tex_path,ffmpeg=ffmpeg,
                                      progress=lambda done,n,_i=i: progress(f'OBJ {_i+1}: {done}/{n} frames'))
                nc=dict(c); nc.update({'path':layer,'kind':'video','in':0.0,'out':dur}); material.append(nc)
            clips=material
        _clip_video_render(clips,tmp,snapshot['duration'],snapshot['fps'],snapshot['width'],snapshot['height'],
                           snapshot['rate'],snapshot['video_only'],ffmpeg,ffprobe,snapshot['fade_edges'],progress)
        if not os.path.isfile(tmp) or os.path.getsize(tmp)<1024:
            raise RuntimeError('Render produced no usable output file.')
        ext=os.path.splitext(path)[1].lower().lstrip('.') or 'mp4'
        ext={'mpeg':'mpg'}.get(ext,ext)
        return _transcode(ffmpeg,tmp,path,ext if ext in VIDEO_FORMATS else 'mp4',snapshot['video_only'],progress)
    except Exception:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass
        raise
    finally:
        shutil.rmtree(work,ignore_errors=True)

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
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAcceptDrops(True)
        self._active_job = None
        self._job_generation = 0
        self._job_future = None
        self.setWindowTitle('Groovebox · Multitrack Clip Studio')
        self.setMinimumSize(1050, 620)
        from parametric_math_background import ParametricMathBackground
        self._math_background = ParametricMathBackground(self)
        self.setStyleSheet("QWidget{background:rgba(7,17,29,238);color:#d9edf7;} QGroupBox{border:1px solid #35627d;border-radius:8px;margin-top:8px;padding-top:8px;color:#f2d17a;font-weight:700;} QPushButton{background:#12334a;color:#e8faff;border:1px solid #39768e;border-radius:8px;padding:6px 10px;font-weight:650;} QPushButton:hover{background:#1a4c65;} QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:#091b2a;color:#e6f5ff;border:1px solid #35627d;border-radius:5px;padding:4px;} QTableWidget{background:#081522;alternate-background-color:#0d2132;gridline-color:#29475b;selection-background-color:#245d76;} QHeaderView::section{background:#14354b;color:#f0d07a;padding:5px;border:1px solid #2d566e;} QProgressBar{background:#07111b;border:1px solid #37647c;border-radius:5px;text-align:center;} QProgressBar::chunk{background:#35b8ad;}")
        self._build_ui()
        self._math_background.setGeometry(self.rect()); self._math_background.lower()

    def _build_ui(self):
        # CLIP_STUDIO_R31: Timeline tab (strip + inspector) and its own Performance tab.
        from PyQt6.QtWidgets import QTabWidget
        outer=QVBoxLayout(self); outer.setContentsMargins(6,6,6,6)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs)
        _page=QWidget(); root=QVBoxLayout(_page); self.tabs.addTab(_page,'🎞 Timeline')
        intro=QLabel('MULTITRACK CLIP STUDIO  ·  Arrange audio and video on independent layers. '
                     'Audio · video · images · text · OBJ 3D layers. Originals are never modified.')
        intro.setWordWrap(True); root.addWidget(intro)
        actions=QHBoxLayout()
        badd=QPushButton('＋ Add media…'); badd.clicked.connect(self.add_media); actions.addWidget(badd)
        bremove=QPushButton('Remove selected'); bremove.clicked.connect(self.remove_selected); actions.addWidget(bremove)
        bclone=QPushButton('Duplicate selected'); bclone.clicked.connect(self.duplicate_selected); actions.addWidget(bclone)
        bsave=QPushButton('Save timeline…'); bsave.clicked.connect(self.save_timeline); actions.addWidget(bsave)
        bload=QPushButton('Load timeline…'); bload.clicked.connect(self.load_timeline); actions.addWidget(bload)
        bobj=QPushButton('🧊 OBJ settings…'); bobj.setToolTip('Texture (MTL / image / video / the scene below), spin, tilt and size of the selected OBJ layer.')
        bobj.clicked.connect(self.edit_obj_settings); actions.addWidget(bobj)
        btxt=QPushButton('🔤 Add text…'); btxt.setToolTip('A title / caption layer (font size, colour, position, box, fade).')
        btxt.clicked.connect(self.add_text); actions.addWidget(btxt)
        bfx=QPushButton('🎨 Clip FX…'); bfx.setToolTip('Speed, colour, blur/sharpen, zoom, rotate, mirror/flip, invert, grayscale, edge glow, vignette, fades for the selected clip(s).')
        bfx.clicked.connect(self.edit_clip_fx); actions.addWidget(bfx)
        # R32.8: record a new camera / microphone clip straight onto the timeline
        from PyQt6.QtWidgets import QComboBox as _QCB
        self.rec_mode=_QCB(); self.rec_mode.addItems(['cam+mic','cam','mic'])
        self.rec_mode.setToolTip('What the new recording captures (camera from Hardware ▸ camera choice; default microphone).')
        self.rec_btn=QPushButton('⏺ New Cam/Mic recording'); self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip('Start a camera + microphone take; press again to stop. The finished clip is added to the timeline '
                                'and saved in the exports folder (FFmpeg writes straight to disk, the window stays smooth).')
        self.rec_btn.toggled.connect(self._toggle_cam_rec)
        actions.addWidget(self.rec_mode); actions.addWidget(self.rec_btn)
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
        from clip_studio_performance import TimelineStrip, ClipInspector, ClipPerformancePanel
        self.strip=TimelineStrip(self); root.addWidget(self.strip)
        _mid=QHBoxLayout(); _mid.addWidget(self.table,3)
        self.inspector=ClipInspector(self); self.inspector.setMinimumWidth(300); _mid.addWidget(self.inspector,1)
        root.addLayout(_mid,1)
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table, activated=self.remove_selected)
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
        self.export_btn=QPushButton('Render timeline (MP4 · MOV · MKV · WebM · AVI · MPEG · OGV · WMV · GIF · MCC)…'); self.export_btn.clicked.connect(self.export_video); bottom.addWidget(self.export_btn)
        root.addLayout(bottom)
        self.performance=ClipPerformancePanel(self)
        self.tabs.addTab(self.performance,'🎛 Performance')

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
        if kind!='text' and not os.path.isfile(path): raise ValueError(f'Media file is missing: {path}')
        if start<0 or src_in<0 or src_out<=src_in: raise ValueError(f'Invalid clip region on row {row+1}; source out must be greater than source in.')
        if track<1 or not 0<=opacity<=1: raise ValueError(f'Invalid track or opacity on row {row+1}.')
        rec={'path':path,'kind':kind,'start':start,'in':src_in,'out':src_out,'track':track,'gain':gain,'opacity':opacity,'mute':mute,
             'pan':pan,'width':width,'blend':blend}
        try:
            _fx=self.table.item(row,0).data(Qt.ItemDataRole.UserRole) if self.table.item(row,0) else None
            rec['fx']=json.loads(_fx) if _fx else {}
        except Exception:
            rec['fx']={}
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
            if c==0 and rec.get('fx'):
                it.setData(Qt.ItemDataRole.UserRole, json.dumps(rec['fx']))
            if c==1 and str(rec.get('kind'))=='obj':
                it.setData(Qt.ItemDataRole.UserRole, json.dumps(rec.get('obj') or {'texture':'mtl','spin_deg_s':30.0,'tilt_deg':15.0,'scale':0.8}))
            self.table.setItem(r,c,it)
        self._update_estimate()

    def add_text(self):
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getMultiLineText(self, 'Text layer', 'Text:', 'Title')
        if not ok or not text.strip():
            return
        start=float(getattr(getattr(self,'strip',None),'playhead',0) or 0)
        self._add_row({'path':'TEXT: '+text.strip().replace('\n',' ')[:60],'kind':'text','start':start,'in':0,'out':4.0,'track':99,
                       'gain':0,'opacity':1,'mute':True,'fx':{'text':text.strip(),'font_size':64,'color':'white','position':'center','box':True,'fade':True}})
        self.status.setText('Text layer added · edit start/out for its timing, 🎨 Clip FX for size, colour and position.')

    def edit_clip_fx(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        rows=sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            self.status.setText('Select one or more clips first.'); return
        it0=self.table.item(rows[0],0)
        try: fx=json.loads(it0.data(Qt.ItemDataRole.UserRole) or '{}')
        except Exception: fx={}
        kind=(self.table.item(rows[0],1).text() if self.table.item(rows[0],1) else '').lower()
        dlg=QDialog(self); dlg.setWindowTitle('Clip FX · %d clip(s)'%len(rows)); f=QFormLayout(dlg); w={}
        for key,cap,lo,hi,d in FX_KEYS:
            sp=QDoubleSpinBox(); sp.setRange(lo,hi); sp.setDecimals(3); sp.setSingleStep((hi-lo)/100); sp.setValue(float(fx.get(key,d))); f.addRow(cap,sp); w[key]=sp
        for key,cap in FX_FLAGS:
            cb=QCheckBox(cap); cb.setChecked(bool(fx.get(key))); f.addRow('',cb); w[key]=cb
        if kind=='text':
            te=QLineEdit(str(fx.get('text',''))); f.addRow('Text',te); w['text']=te
            fs=QSpinBox(); fs.setRange(8,400); fs.setValue(int(fx.get('font_size',64))); f.addRow('Font size',fs); w['font_size']=fs
            co=QLineEdit(str(fx.get('color','white'))); f.addRow('Colour (name or #rrggbb)',co); w['color']=co
            po=QComboBox(); po.addItems(['center','top','bottom','left','right']); po.setCurrentText(str(fx.get('position','center'))); f.addRow('Position',po); w['position']=po
            bx=QCheckBox('Background box'); bx.setChecked(bool(fx.get('box',True))); f.addRow('',bx); w['box']=bx
        bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Reset)
        f.addRow(bb)
        def _ok():
            new={}
            for k,x in w.items():
                if isinstance(x,QCheckBox): new[k]=x.isChecked()
                elif isinstance(x,(QDoubleSpinBox,QSpinBox)): new[k]=x.value()
                elif isinstance(x,QComboBox): new[k]=x.currentText()
                else: new[k]=x.text()
            for r in rows:
                it=self.table.item(r,0)
                if it is not None: it.setData(Qt.ItemDataRole.UserRole,json.dumps(new))
            self.status.setText('Clip FX set on %d clip(s).'%len(rows)); dlg.accept()
        bb.accepted.connect(_ok); bb.rejected.connect(dlg.reject)
        bb.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: ([self.table.item(r,0).setData(Qt.ItemDataRole.UserRole,'{}') for r in rows], dlg.reject(), self.status.setText('Clip FX cleared.')))
        dlg.setModal(False); dlg.show(); self._fx_dialog=dlg

    def add_media(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Add audio/video media','',MEDIA_FILTER)
        self._add_media_paths(paths)

    def _add_media_paths(self, paths):
        added=0
        for raw in paths or []:
            p=os.path.abspath(str(raw))
            if not os.path.isfile(p): continue
            ext=Path(p).suffix.lower()
            if ext=='.obj': kind='obj'
            elif ext in {'.png','.jpg','.jpeg','.bmp','.webp','.gif'}: kind='image'
            elif ext=='.mcc':
                try:
                    import mcc_media
                    kind='video' if mcc_media.media_kind(p)=='video' else 'audio'
                except Exception: kind='audio'
            else:
                kind='video' if ext in {'.mp4','.m4v','.mov','.mkv','.webm','.avi','.mpeg','.mpg','.ogv','.wmv'} else 'audio'
            # Duration probing is deferred to worker-side render preparation. A
            # conservative editable placeholder keeps drag/drop immediate.
            self._add_row({'path':p,'kind':kind,'start':0,'in':0,'out':10.0,'track':1,'gain':0,'opacity':1,'mute':False})
            added+=1
        if added:
            self.status.setText(f'Added {added} item(s) · duration defaults to 10 s until edited; source probing stays off the UI thread.')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self._add_media_paths(paths)
        event.acceptProposedAction()

    def _start_background_job(self, job, label, active_buttons):
        if self._active_job is not None:
            self.status.setText('A render is already running. The shared render lane is deliberately bounded to one active job per editor.')
            return
        from ui_runtime import submit_ui_task, post_to_ui
        self._job_generation += 1
        generation = self._job_generation
        self._active_job=job
        self._job_buttons=list(active_buttons)
        for b in self._job_buttons: b.setEnabled(False)
        self.status.setText(label)

        def worker():
            def progress(message):
                post_to_ui(self._job_progress, str(message), key=("clip-progress", id(self)))
            return job.fn(progress)

        def failed(exc):
            self._job_failed(f"{type(exc).__name__}: {exc}")

        try:
            self._job_future = submit_ui_task(
                self, worker, on_result=self._job_finished, on_error=failed,
                generation_attr="_job_generation", generation=generation,
                key="clip-render",
            )
        except Exception as exc:
            self._job_failed(f"{type(exc).__name__}: {exc}")

    def _job_progress(self, message):
        self.status.setText(str(message))

    def _restore_job_ui(self):
        for b in getattr(self,'_job_buttons',[]):
            try: b.setEnabled(True)
            except RuntimeError: pass
        self._job_buttons=[]
        self._active_job=None

    def _job_finished(self, result):
        self._restore_job_ui()
        self.status.setText(f'Render complete: {result}')
        box=QMessageBox(self); box.setWindowTitle('Groovebox render'); box.setText('Finished rendering:\n'+str(result))
        b_open=box.addButton('Open folder',QMessageBox.ButtonRole.ActionRole); box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is b_open:     # R32.9: jump straight to the result
            try:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(os.path.abspath(str(result)))))
            except Exception: pass

    def _job_failed(self, message):
        self._restore_job_ui()
        self.status.setText('Render failed; source media and timeline were preserved.')
        QMessageBox.warning(self,'Groovebox render',str(message))

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
        if not (low.endswith('.wav') or low.endswith('.flac') or low.endswith('.mcc')):
            path+=('.MCC' if mcc else ('.flac' if 'FLAC' in flt else '.wav'))
        duration=float(self.duration.value()); rate=int(self.audio_rate.currentText()); fade_edges=self.fade_edges.isChecked()
        ffprobe=resolve_local_tool('ffprobe')
        tmp=path+'.part.wav' if mcc else path+'.part'+os.path.splitext(path)[1]
        clips=[c for c in clips if c['kind'] not in ('text','image','obj')]   # R32.6: no audio in these kinds
        if not clips: QMessageBox.information(self,'Render audio mix','No audio-bearing clips on the timeline.'); return
        def work(progress):
            cmd=[ff,'-hide_banner','-y']
            for c in clips: cmd+=['-i',c['path']]
            graph=_clip_audio_graph(clips,duration,rate,0,fade_edges,ffprobe)
            if mcc:
                cmd+=['-filter_complex',';'.join(graph),'-map','[outa]','-t',f'{duration:.6f}','-f','f32le','-ac','2','-ar',str(rate),'pipe:1']
                progress('Rendering lossless MCC audio buffer in background…')
                cp=subprocess.run(cmd,capture_output=True,timeout=max(120,int(duration*10)))
                if cp.returncode!=0: raise RuntimeError((cp.stderr or b'FFmpeg audio render failed')[-3000:].decode('utf-8','replace'))
                import numpy as np, mcc_media
                if len(cp.stdout)%8: raise RuntimeError('FFmpeg returned an incomplete float32 stereo buffer.')
                x=np.frombuffer(cp.stdout,dtype=np.float32).reshape(-1,2)
                mcc_media.encode_audio(path,x,rate,extra={'source':'Multitrack Clip Studio'})
            else:
                cmd+=['-filter_complex',';'.join(graph),'-map','[outa]','-t',f'{duration:.6f}','-c:a',('flac' if path.lower().endswith('.flac') else 'pcm_s24le'),tmp]
                progress('Rendering audio mix in background…')
                cp=subprocess.run(cmd,capture_output=True,timeout=max(120,int(duration*10)))
                if cp.returncode!=0: raise RuntimeError((cp.stderr or b'FFmpeg audio render failed')[-3000:].decode('utf-8','replace'))
                if not os.path.isfile(tmp) or os.path.getsize(tmp)<44: raise RuntimeError('Audio render produced no usable output file.')
                os.replace(tmp,path)
            return path
        job=_ClipJob(work)
        self._start_background_job(job,'Rendering audio mix in background…',[self.audio_btn,self.export_btn,self.video_only_btn])

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

    def export_video(self, video_only=False):
        ff=resolve_local_tool('ffmpeg')
        if not ff:
            QMessageBox.warning(self,'Render timeline','Groovebox-local FFmpeg is not available. Run the normal first-launch dependency provisioning step.'); return
        try: clips=self._records()
        except Exception as e: QMessageBox.warning(self,'Render timeline',str(e)); return
        if not clips: QMessageBox.information(self,'Render timeline','Add at least one audio or video clip first.'); return
        path,flt=QFileDialog.getSaveFileName(self,'Render timeline','groovebox-timeline.mp4',_format_filter())
        if not path:return
        ext=os.path.splitext(path)[1].lower().lstrip('.')
        if ext not in VIDEO_FORMATS and ext!='mpeg':     # no / unknown extension: take the one the chosen filter names
            import re as _re
            m=_re.search(r'\*\.(\w+)',flt or ''); path+='.'+((m.group(1).lower()) if m else 'mp4')
        duration=float(self.duration.value()); fps=int(self.fps.value()); w=int(self.width.value()); h=int(self.height.value()); rate=int(self.audio_rate.currentText())
        if any(c['start']>=duration for c in clips):
            QMessageBox.warning(self,'Render timeline','A clip starts at or after the selected timeline duration. Increase duration or adjust its start.'); return
        snapshot={'clips':clips,'path':path,'duration':duration,'fps':fps,'width':w,'height':h,'rate':rate,
                  'video_only':bool(video_only),'ffmpeg':ff,'ffprobe':resolve_local_tool('ffprobe'),
                  'fade_edges':self.fade_edges.isChecked()}
        job=_ClipJob(lambda progress:_clip_video_job(snapshot,progress))
        buttons=[self.audio_btn,self.export_btn,self.video_only_btn]
        self._start_background_job(job,'Preparing video render in background…',buttons)

    def resizeEvent(self, event):
        try: self._math_background.setGeometry(self.rect()); self._math_background.lower()
        except Exception: pass
        super().resizeEvent(event)

    def _toggle_cam_rec(self, on):
        from PyQt6.QtCore import QTimer
        import threading
        host=self.parent() if self.parent() is not None else None
        if on:
            try:
                import cam_mic_recorder as _cmr
                self._cam_rec=_cmr.CamMicRecorder(host, self.rec_mode.currentText()).start()
            except Exception as exc:
                self._cam_rec=None; self.status.setText(f'Recording could not start: {exc}')
                self.rec_btn.blockSignals(True); self.rec_btn.setChecked(False); self.rec_btn.blockSignals(False); return
            self.rec_btn.setText('⏹ Stop recording (0:00)'); self.rec_mode.setEnabled(False)
            self._cam_rec_timer=QTimer(self); self._cam_rec_timer.setInterval(500)
            def _tick():
                r=getattr(self,'_cam_rec',None)
                if r is None: return
                if not r.running():
                    self.rec_btn.setChecked(False); return
                s=int(r.elapsed()); self.rec_btn.setText(f'⏹ Stop recording ({s//60}:{s%60:02d})')
            self._cam_rec_timer.timeout.connect(_tick); self._cam_rec_timer.start()
            self.status.setText('Recording… press ⏹ to stop.')
            return
        r=getattr(self,'_cam_rec',None); self._cam_rec=None
        try: self._cam_rec_timer.stop()
        except Exception: pass
        self.rec_btn.setText('⏺ New Cam/Mic recording'); self.rec_mode.setEnabled(True)
        if r is None: return
        self.status.setText('Finishing the recording…')
        def _fin():
            path=r.stop()
            def _done():
                if path:
                    self._add_media_paths([path]); self.status.setText(f'Recorded clip added: {os.path.basename(path)}')
                else:
                    self.status.setText(f'Recording failed: {r.error}')
            QTimer.singleShot(0, _done)
        threading.Thread(target=_fin, name='cam-rec-stop', daemon=True).start()

    def closeEvent(self, event):
        r=getattr(self,'_cam_rec',None)
        if r is not None:
            try: self.rec_btn.setChecked(False)     # finalise the take, never orphan ffmpeg
            except Exception: pass
        if self._active_job is not None:
            self.status.setText('A render is still running. Let it finish before closing this editor; the main Groovebox window remains responsive.')
            event.ignore(); return
        super().closeEvent(event)


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
