# =============================================================================
# Groovebox Video-Game Generator — deterministic composition-to-game mapping
# =============================================================================
# Deterministic transducer:
#     canonical composition -> fingerprint -> cyclic-group coordinates -> game.
# GOAVA is part of the canonical state, so GOAVA changes music, scene and game.
# Finite genre labels cannot be globally injective over an unbounded seed domain;
# the fingerprint is therefore the canonical identity and the catalogue itself
# is made non-redundant by deterministic permutations.
# =============================================================================
from __future__ import annotations
import hashlib, json, math, socket, textwrap
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

MEUM = 1.1975807343385265
MEUM_INV = 1.0 / MEUM
MEUM_NORM = (MEUM - 1.0) / MEUM
PHI = 1.618033988749895

GENRES = ("arcade","fps","rpg","sandbox","survival","arena","dating_sim","platformer","strategy","racing","puzzle","adventure")
CAMERAS = ("first_person","second_person","third_person","top_down","isometric")
TOPOLOGIES = ("linear","open_world","hub_spoke","arena_loop","roguelike_deck")
SOCIAL = ("singleplayer","local_coop","online_multiplayer","asynchronous")
MOODS = ("neon_noir","pastoral","cosmic","industrial","mythic","glitch")
MODEL_1D = ("filament","wave_line","orbit","ray","ribbon","trace","rail","string")
MODEL_2D = ("panel","glyph","ring","tile","mandala","portal","map","mask")
MODEL_3D = ("polytope","orb","crystal","tower","arch","torus","field","shard")

def _safe_int_seed(value):
    try: x = float(value)
    except Exception: x = 0.0
    if not math.isfinite(x): x = 0.0
    if x == int(x) and abs(x) < 2**31: return int(x) & 0x7fffffff
    return int.from_bytes(hashlib.sha256(repr(x).encode()).digest()[:8],"big") & 0x7fffffff

def _canonical_number(value):
    try:
        x=float(value)
        return "0" if not math.isfinite(x) else format(x,".12g")
    except Exception: return str(value)

def _composition_fingerprint(seed,bpm,seq_length,playlist_rows,n_instruments,goava_active,live_parametrics=""):
    fields=(_canonical_number(seed),_canonical_number(bpm),str(int(seq_length)),
            str(int(playlist_rows)),str(int(n_instruments)),str(int(bool(goava_active))),
            str(live_parametrics or "")[:512])
    return hashlib.sha256("|".join(fields).encode()).hexdigest()

def _mix(seed,label,fingerprint=""):
    # Stateless labelled hashing is the processor syntax: each label is an
    # independent projection, so coordinate choices never depend on call order.
    d=hashlib.sha256(f"{int(seed)}|{label}|{fingerprint}|{MEUM:.15f}".encode()).digest()
    return int.from_bytes(d[:8],"big")

def _permutation(length,key):
    # p(i)=(a*i+b) mod n is a permutation whenever gcd(a,n)=1.
    n=max(1,int(length))
    if n==1:return [0]
    a=1+key%(n-1)
    while math.gcd(a,n)!=1:a=(a+1)%n or 1
    b=(key>>16)%n
    return [(a*i+b)%n for i in range(n)]

@dataclass
class GameIdentity:
    seed: float
    title: str
    genre: str
    camera: str
    topology: str
    social: str
    mood: str
    online: bool
    host_port: int
    model_sets_1d: List[str]
    model_sets_2d: List[str]
    model_sets_3d: List[str]
    ui_palette: Dict[str,str]
    gameplay_hooks: List[str]
    music_variation: str
    composition_fingerprint: str
    splash_bars: int=16
    goava_active: bool=False
    group_coordinates: Dict[str,int]=None
    variation_period: int=97
    def to_dict(self): return asdict(self)

def classify_from_composition(seed,*,bpm=120.0,seq_length=16,playlist_rows=32,
                              n_instruments=8,goava_active=False,live_parametrics=None):
    # Product-group coordinates make the classification explainable: each
    # coordinate is a residue in its own finite cyclic factor.
    s=_safe_int_seed(seed)
    fp=_composition_fingerprint(seed,bpm,seq_length,playlist_rows,n_instruments,goava_active,live_parametrics)
    coords={"genre":_mix(s,"genre",fp)%len(GENRES),
            "camera":_mix(s,"camera",fp)%len(CAMERAS),
            "topology":_mix(s,"topology",fp)%len(TOPOLOGIES),
            "social":_mix(s,"social",fp)%len(SOCIAL),
            "mood":_mix(s,"mood",fp)%len(MOODS)}
    genre,cam=GENRES[coords["genre"]],CAMERAS[coords["camera"]]
    top,soc=TOPOLOGIES[coords["topology"]],SOCIAL[coords["social"]]
    mood=MOODS[coords["mood"]]
    port=27015+_mix(s,"port",fp)%8000
    p1=_permutation(len(MODEL_1D),_mix(s,"m1",fp))
    p2=_permutation(len(MODEL_2D),_mix(s,"m2",fp))
    p3=_permutation(len(MODEL_3D),_mix(s,"m3",fp))
    n1=3+_mix(s,"n1",fp)%4; n2=3+_mix(s,"n2",fp)%4; n3=3+_mix(s,"n3",fp)%4
    m1=[f"{MODEL_1D[i]}_{j}" for j,i in enumerate(p1[:n1])]
    m2=[f"{MODEL_2D[i]}_{j}" for j,i in enumerate(p2[:n2])]
    m3=[f"{MODEL_3D[i]}_{j}" for j,i in enumerate(p3[:n3])]
    palette={"bg":f"#{_mix(s,'bg',fp)&0x202f3f:06x}",
             "accent":f"#{_mix(s,'ac',fp)&0xffffff:06x}",
             "accent2":f"#{_mix(s,'ac2',fp)&0xffffff:06x}","text":"#e8f0ff"}
    hooks=[f"score_{genre}",f"camera_{cam}",f"topology_{top}",f"orbit_{_mix(s,'orbit',fp)%11}",
           f"tempo_gate_{_mix(s,'tempo',fp)%13}"]
    if goava_active: hooks += ["goava_portal","goava_scene_commutation","goava_music_variation"]
    if soc=="online_multiplayer": hooks.append("network_session")
    return GameIdentity(float(seed),f"{mood.replace('_',' ').title()} {genre.replace('_',' ').title()} [{fp[:6]}]",
        genre,cam,top,soc,mood,soc=="online_multiplayer",int(port),m1,m2,m3,palette,hooks,
        "goava_commutated_longform" if goava_active else "seeded_group_orbit",fp[:32],
        max(4,min(64,int(seq_length))),bool(goava_active),coords,53+_mix(s,"period",fp)%211)

def generate_game_script(identity,composition_meta=None):
    meta=composition_meta or {}
    payload=json.dumps(identity.to_dict(),sort_keys=True)
    bpm=float(meta.get("bpm",120.0)); seq=int(meta.get("seq_length",identity.splash_bars))
    template = r'''#!/usr/bin/env python3
# Auto-generated deterministic Groovebox game.
# Composition fingerprint: __FP__
# Install: PyQt6; optional audio: numpy sounddevice.
import hashlib,json,math,socket,sys
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QPainter,QPen,QBrush,QColor,QFont
from PyQt6.QtWidgets import QApplication,QWidget,QMainWindow,QLabel,QPushButton,QVBoxLayout
try:
    import numpy as np,sounddevice as sd
except Exception:
    np=None;sd=None
MEUM=__MEUM__;PHI=__PHI__;BPM=__BPM__;SEQ=__SEQ__
IDENTITY=json.loads(__IDENTITY__)

def mix(seed,label,index=0):
    # Stateless hash selects a repeatable event/visual coordinate.
    d=hashlib.sha256(f"{int(seed)}|{label}|{int(index)}|{MEUM:.15f}".encode()).digest()
    return int.from_bytes(d[:8],"big")

def perm(n,key):
    n=max(1,int(n))
    if n==1:return [0]
    a=1+key%(n-1)
    while math.gcd(a,n)!=1:a=(a+1)%n or 1
    b=(key>>16)%n
    return [(a*i+b)%n for i in range(n)]

class Kernel:
    # Music, scene and gameplay share one phase; no subsystem invents a second seed.
    def __init__(self,ident):
        self.id=ident;self.seed=float(ident["seed"]);self.goava=bool(ident.get("goava_active"))
        self.t=0.;self.frame=0;self.score=0.;self.order=perm(64,mix(self.seed,"event"))
        self.scene=[{"id":k,"phase":(k*PHI*MEUM)%math.tau,
                      "depth":.7+(mix(self.seed,"depth",k)%1000)/1000.} for k in self.order[:24]]
    def sample(self,t):
        b=t*BPM/60.*math.tau
        x=.34*math.sin(b*MEUM+self.seed*.00001)+.16*math.sin(2*b+MEUM)
        if self.goava:x+=.10*math.sin(b/MEUM+self.seed*.000017)
        return x
    def tick(self,dt):
        self.t+=dt;self.frame+=1
        beat=self.t*BPM/60.;self.event=self.order[int(beat*4)%len(self.order)]
        cycle=self.frame//max(1,int(self.id.get("variation_period",97)))
        for j,o in enumerate(self.scene):
            o["phase"]=(o["phase"]+dt*(.4+.05*MEUM*(j+1)))%math.tau
            if self.goava:o["phase"]+=.01*math.sin(cycle*MEUM+j*PHI)
        self.score+=abs(self.sample(self.t))*.05
        return self.sample(self.t)

class Audio:
    # Optional bridge; failure to open an audio device never changes the kernel.
    def __init__(self,k):self.k=k;self.stream=None;self.phase=0.
    def start(self):
        if sd is None or np is None:return
        def cb(outdata,frames,time_info,status):
            t=(np.arange(frames)+self.phase)/48000.;b=t*BPM/60.*2*math.pi
            x=.24*np.sin(b*MEUM)+.11*np.sin(b*(2+MEUM))
            if self.k.goava:x+=.08*np.sin(b/MEUM+self.k.seed*1e-5)
            outdata[:,0]=x.astype(np.float32);self.phase+=frames
        try:
            self.stream=sd.OutputStream(samplerate=48000,channels=1,callback=cb,blocksize=512);self.stream.start()
        except Exception:self.stream=None
    def stop(self):
        if self.stream:
            try:self.stream.stop();self.stream.close()
            except Exception:pass
            self.stream=None

class Scene(QWidget):
    def __init__(self,k):
        super().__init__();self.k=k;self.keys=set();self.x=0.;self.y=0.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.timer=QTimer(self);self.timer.timeout.connect(self.step);self.timer.start(33)
    def keyPressEvent(self,e):self.keys.add(e.key())
    def keyReleaseEvent(self,e):self.keys.discard(e.key())
    def step(self):
        self.k.tick(1/30);v=.05
        if Qt.Key.Key_W in self.keys:self.y-=v
        if Qt.Key.Key_S in self.keys:self.y+=v
        if Qt.Key.Key_A in self.keys:self.x-=v
        if Qt.Key.Key_D in self.keys:self.x+=v
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);w,h=self.width(),self.height();p.fillRect(self.rect(),QColor(IDENTITY["ui_palette"]["bg"]))
        p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor(IDENTITY["ui_palette"]["accent"]),2))
        cx,cy=w/2+self.x*8,h/2+self.y*8
        for j,o in enumerate(self.k.scene):
            a=o["phase"]+self.k.t*(.25+.03*j);r=55+o["depth"]*min(w,h)*.22;z=1/(1+.35*math.sin(a))
            xx=cx+math.cos(a)*r*z;yy=cy+math.sin(a*MEUM)*r*z;rad=max(3,12*z)
            cam=IDENTITY["camera"]
            if cam=="first_person":xx+=math.sin(a)*w*.08
            elif cam=="second_person":xx=w-xx;yy=h-yy
            elif cam=="top_down":yy=cy+math.sin(a)*r*.55
            elif cam=="isometric":yy=cy+(math.sin(a)+math.cos(a))*r*.38
            p.setBrush(QBrush(QColor(IDENTITY["ui_palette"]["accent2"])));p.drawEllipse(xx-rad/2,yy-rad/2,rad,rad)
            if j%3==0:p.drawLine(cx,cy,xx,yy)
        p.setPen(QColor(IDENTITY["ui_palette"]["text"]));p.setFont(QFont("Sans",9))
        p.drawText(12,20,f"{IDENTITY['title']} | {IDENTITY['genre']} / {IDENTITY['camera']}")
        p.drawText(12,38,f"{IDENTITY['topology']} · {IDENTITY['social']} · GOAVA={self.k.goava} · score={self.k.score:.2f}")
        p.drawText(12,h-14,"WASD move · deterministic audiovisual composition kernel")

class Window(QMainWindow):
    def __init__(self,k,a):
        super().__init__();self.k=k;self.a=a;self.setWindowTitle(IDENTITY["title"]);self.resize(900,600)
        c=QWidget();self.setCentralWidget(c);lay=QVBoxLayout(c)
        lay.addWidget(QLabel("<h1>"+IDENTITY["title"]+"</h1>"))
        lay.addWidget(QLabel(f"Genre: {IDENTITY['genre']} · Camera: {IDENTITY['camera']} · Topology: {IDENTITY['topology']}<br>Social: {IDENTITY['social']} · Mood: {IDENTITY['mood']}"))
        lay.addWidget(QLabel("1D: "+", ".join(IDENTITY["model_sets_1d"])+"<br>2D: "+", ".join(IDENTITY["model_sets_2d"])+"<br>3D: "+", ".join(IDENTITY["model_sets_3d"])))
        b=QPushButton("▶ PLAY");b.clicked.connect(self.play);lay.addWidget(b)
        if IDENTITY.get("online"):
            h=QPushButton("HOST ONLINE · port "+str(IDENTITY["host_port"]));h.clicked.connect(self.host);lay.addWidget(h)
    def play(self):
        self.g=Scene(self.k);self.setCentralWidget(self.g);self.g.setFocus();self.a.start()
    def host(self):
        try:
            self.server=socket.socket();self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.server.bind(("0.0.0.0",int(IDENTITY["host_port"])));self.server.listen(4);self.server.setblocking(False)
            self.statusBar().showMessage("Hosting on port "+str(IDENTITY["host_port"]))
        except Exception as e:self.statusBar().showMessage("Host unavailable: "+str(e))

def main():
    app=QApplication(sys.argv);k=Kernel(IDENTITY);a=Audio(k)
    splash=QWidget();splash.setWindowTitle(IDENTITY["title"]);splash.resize(760,420);l=QVBoxLayout(splash)
    l.addWidget(QLabel("<h1>"+IDENTITY["title"]+"</h1>"));l.addWidget(QLabel(f"Composition splash · {IDENTITY['splash_bars']} bars @ {BPM:.1f} BPM"))
    splash.show();a.start()
    duration=min(12.,(60/max(BPM,1))*4*IDENTITY["splash_bars"])
    timer=QTimer();timer.setSingleShot(True)
    def begin():
        a.stop();splash.close();w=Window(k,a);w.show();w.activateWindow()
    timer.timeout.connect(begin);timer.start(int(duration*1000))
    return app.exec()
if __name__=="__main__":main()
'''
    return (template.replace("__FP__",identity.composition_fingerprint)
            .replace("__MEUM__",repr(MEUM)).replace("__PHI__",repr(PHI))
            .replace("__BPM__",repr(bpm)).replace("__SEQ__",repr(seq))
            .replace("__IDENTITY__",repr(payload)))

def export_game_files(identity,out_dir,composition_meta=None):
    os.makedirs(out_dir,exist_ok=True)
    script=os.path.join(out_dir,f"game_{identity.composition_fingerprint}.py")
    with open(script,"w",encoding="utf-8") as f:f.write(generate_game_script(identity,composition_meta))
    with open(os.path.join(out_dir,f"game_{identity.composition_fingerprint}.json"),"w",encoding="utf-8") as f:
        json.dump(identity.to_dict(),f,indent=2)
    return script
