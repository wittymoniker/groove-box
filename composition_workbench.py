"""Composition workflow helpers and non-modal inspector/editor.

This module extends the existing sequencer, playlist, canonical and synth state;
it does not create a second playback or render engine. All transforms are
explicit and deterministic. The PKP PROB response coefficient is never used as
an event gate or probability.
"""
from __future__ import annotations
import copy, hashlib, json, math
from typing import Any

LANES = ("steps", "pitches", "amplitudes", "gates", "probabilities", "offsets")


def _length(sequence: dict) -> int:
    for key in LANES:
        value = sequence.get(key)
        if isinstance(value, list) and value:
            return len(value)
    return 0


def copy_step(sequence: dict, index: int) -> dict:
    n = _length(sequence)
    if not 0 <= int(index) < n:
        raise IndexError("step index outside sequence")
    return {key: copy.deepcopy(sequence[key][int(index)]) for key in LANES
            if isinstance(sequence.get(key), list) and int(index) < len(sequence[key])}


def paste_step(sequence: dict, index: int, payload: dict, *, lanes=None) -> dict:
    """Paste authored step fields; return changed fields without altering other lanes."""
    n = _length(sequence)
    i = int(index)
    if not 0 <= i < n:
        raise IndexError("step index outside sequence")
    allowed = set(lanes or LANES)
    changed = {}
    for key, value in payload.items():
        if key not in LANES or key not in allowed:
            continue
        lane = sequence.get(key)
        if isinstance(lane, list) and i < len(lane):
            lane[i] = copy.deepcopy(value)
            changed[key] = copy.deepcopy(value)
    return changed


def ghost_notes(sequence: dict, *, active_step: int | None = None) -> list[dict]:
    """Build a read-only ghost-note overlay from authored pitch/velocity lanes."""
    n = _length(sequence)
    steps = sequence.get("steps", [])
    pitches = sequence.get("pitches", [])
    amplitudes = sequence.get("amplitudes", [])
    gates = sequence.get("gates", [])
    out = []
    for i in range(n):
        active = bool(steps[i]) if i < len(steps) else False
        gate = bool(gates[i]) if i < len(gates) else True
        if not active or not gate:
            continue
        pitch = pitches[i] if i < len(pitches) else 1.0
        velocity = amplitudes[i] if i < len(amplitudes) else 1.0
        try:
            pitch = float(pitch); velocity = float(velocity)
            if not math.isfinite(pitch) or not math.isfinite(velocity):
                continue
        except Exception:
            continue
        out.append({"step": i, "pitch_ratio": pitch, "velocity": velocity,
                    "is_ghost": active_step is not None and i != int(active_step)})
    return out


def playlist_row_report(rows: list) -> list[dict]:
    """Return stable row identities, bounds and mute/solo state for playlist UI."""
    report=[]
    for i,row in enumerate(rows or []):
        if not isinstance(row,dict):
            continue
        try: start=max(0,int(row.get("start",row.get("start_step",0)) or 0))
        except (TypeError,ValueError,OverflowError): start=0
        try: length=max(0,int(row.get("length",row.get("steps",0)) or 0))
        except (TypeError,ValueError,OverflowError): length=0
        report.append({"index":i,"id":str(row.get("id",row.get("uuid",i))),
                       "name":str(row.get("name",row.get("title",f"Row {i+1}"))),
                       "start":start,"end":start+length,"length":length,
                       "muted":bool(row.get("muted",row.get("mute",False))),
                       "solo":bool(row.get("solo",False)),
                       "cue":row.get("cue",row.get("cue_marker"))})
    return report


def canonical_decision_report(state: Any) -> dict:
    """Preserve raw canonical decisions while providing stable content identity."""
    raw=state if isinstance(state,(dict,list,tuple,str,int,float,bool)) or state is None else repr(state)
    encoded=json.dumps(raw,sort_keys=True,ensure_ascii=False,default=str,separators=(",",":"))
    return {"decision_state":raw,"sha256":hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "principle":"inspect authored decisions; do not infer statistical meaning"}


def synth_ab_snapshot(parameters: dict) -> dict:
    """Create a typed, detached A/B snapshot of synth-panel parameters."""
    snapshot=copy.deepcopy(parameters if isinstance(parameters,dict) else {})
    canonical=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,default=str,separators=(",",":"))
    return {"parameters":snapshot,"sha256":hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def stable_sequence_name(seed_text: str, index: int, prefix="Seed") -> str:
    digest=hashlib.sha256(str(seed_text).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{int(index)+1:02d}-{digest}"


def normalize_sequence_lanes(sequence: dict, length: int | None = None) -> dict:
    """Align supported lanes to a chosen length, preserving authored values."""
    result=copy.deepcopy(sequence if isinstance(sequence,dict) else {})
    n=max(1,min(4096,int(length if length is not None else (_length(result) or 16))))
    defaults={"steps":False,"pitches":1.0,"amplitudes":1.0,"gates":True,
              "probabilities":100,"offsets":0.0}
    for key,default in defaults.items():
        lane=result.get(key)
        lane=list(lane) if isinstance(lane,(list,tuple)) else []
        result[key]=(lane[:n]+[copy.deepcopy(default) for _ in range(max(0,n-len(lane)))])
    result["sequence_length"]=n
    # The native PKP PROB control is separate from per-step authored lane data.
    # Preserve it as a finite 0..2 response coefficient without renaming it into
    # a trigger probability or using it to drop/insert steps.
    if "boost_responsiveness" in result:
        try: value=float(result["boost_responsiveness"])
        except Exception: value=1.0
        result["boost_responsiveness"]=max(0.0,min(2.0,value)) if math.isfinite(value) else 1.0
    return result


def open_window(app):
    from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTabWidget,QWidget,
        QLabel,QPlainTextEdit,QPushButton,QComboBox,QSpinBox,QMessageBox)
    window=getattr(app,"_composition_workbench",None)
    try:
        if window is not None: window.show(); window.raise_(); return window
    except RuntimeError: pass
    window=QDialog(app); window.setWindowTitle("Composition Workbench · Sequencer / Playlist / Canonical / Synth")
    window.resize(980,720); root=QVBoxLayout(window); tabs=QTabWidget(); root.addWidget(tabs)

    seq_tab=QWidget(); sl=QVBoxLayout(seq_tab); tabs.addTab(seq_tab,"Step tools & ghost notes")
    inst=QComboBox(); names=list(getattr(app,"instrument_names_48",[]) or [])
    inst.addItems(names); current=str(getattr(app,"current_instrument",names[0] if names else ""))
    if current in names: inst.setCurrentText(current)
    sl.addWidget(inst)
    idx=QSpinBox(); idx.setRange(0,4095); sl.addWidget(idx)
    seq_out=QPlainTextEdit(); seq_out.setReadOnly(True); sl.addWidget(seq_out)
    clip={"step":None}
    def memory():
        bank=getattr(app,"instrument_sequencer_memory",{}) or {}
        return bank.get(inst.currentText(),{}) if isinstance(bank,dict) else {}
    def refresh_seq():
        mem=memory(); seq_out.setPlainText(json.dumps({"sequence":normalize_sequence_lanes(mem),
            "ghost_notes":ghost_notes(mem,active_step=idx.value()),"clipboard":clip["step"]},indent=2,ensure_ascii=False,default=str))
    def copy_current():
        try: clip["step"]=copy_step(memory(),idx.value()); refresh_seq()
        except Exception as e: QMessageBox.warning(window,"Copy step",str(e))
    def paste_current():
        try:
            mem=memory()
            if hasattr(app,"_push_undo"):
                app._push_undo("Composition Workbench · Paste step")
            changed=paste_step(mem,idx.value(),clip["step"] or {})
            refresh_seq()
            for fn in ("reload_active_instrument_sequencer_ui", "refresh_sequencer_view", "_on_live_source_changed"):
                try:
                    callback=getattr(app,fn,None)
                    if callable(callback): callback()
                except Exception:
                    pass
        except Exception as e: QMessageBox.warning(window,"Paste step",str(e))
    row=QHBoxLayout(); b=QPushButton("Copy step"); b.clicked.connect(copy_current); row.addWidget(b)
    b=QPushButton("Paste step"); b.clicked.connect(paste_current); row.addWidget(b)
    b=QPushButton("Refresh / preview ghosts"); b.clicked.connect(refresh_seq); row.addWidget(b); sl.addLayout(row)
    inst.currentTextChanged.connect(refresh_seq); idx.valueChanged.connect(refresh_seq); refresh_seq()

    playlist_tab=QWidget(); pl=QVBoxLayout(playlist_tab); tabs.addTab(playlist_tab,"Playlist & cues")
    playlist_out=QPlainTextEdit(); playlist_out.setReadOnly(True); pl.addWidget(playlist_out)
    def refresh_playlist():
        rows=getattr(app,"playlist_rows",None)
        if rows is None: rows=getattr(app,"playlist",[])
        playlist_out.setPlainText(json.dumps(playlist_row_report(rows if isinstance(rows,list) else []),indent=2,ensure_ascii=False,default=str))
    pb=QPushButton("Refresh row lengths, mute/solo and cue markers"); pb.clicked.connect(refresh_playlist); pl.addWidget(pb); refresh_playlist()

    canonical_tab=QWidget(); cl=QVBoxLayout(canonical_tab); tabs.addTab(canonical_tab,"Canonical decisions")
    canonical_out=QPlainTextEdit(); canonical_out.setReadOnly(True); cl.addWidget(canonical_out)
    def refresh_canonical():
        state={}
        for key in ("canonical_mode","canonical_active","canonical_decision_log","_canonical_decision_log","canonical_levels","canonical_profile"):
            try:
                value=getattr(app,key,None)
                if value is not None: state[key]=value if isinstance(value,(dict,list,tuple,str,int,float,bool)) else repr(value)
            except Exception: pass
        canonical_out.setPlainText(json.dumps(canonical_decision_report(state),indent=2,ensure_ascii=False,default=str))
    cb=QPushButton("Capture canonical decision state"); cb.clicked.connect(refresh_canonical); cl.addWidget(cb); refresh_canonical()

    synth_tab=QWidget(); yl=QVBoxLayout(synth_tab); tabs.addTab(synth_tab,"Synth A/B")
    synth_out=QPlainTextEdit(); synth_out.setReadOnly(True); yl.addWidget(synth_out)
    ab={"A":None,"B":None}
    def capture(which):
        values={}
        for key in ("synth_parameters","synth_state","multidim_synth_state","instrument_sequencer_memory"):
            value=getattr(app,key,None)
            if value is not None: values[key]=value if isinstance(value,(dict,list,tuple,str,int,float,bool)) else repr(value)
        ab[which]=synth_ab_snapshot(values)
        synth_out.setPlainText(json.dumps({"A":ab["A"],"B":ab["B"],"equal":bool(ab["A"] and ab["B"] and ab["A"]["sha256"]==ab["B"]["sha256"])},indent=2,ensure_ascii=False,default=str))
    row=QHBoxLayout()
    for label,key in (("Capture A","A"),("Capture B","B")):
        b=QPushButton(label); b.clicked.connect(lambda _=False,k=key:capture(k)); row.addWidget(b)
    yl.addLayout(row)
    window.setModal(False); window.show(); app._composition_workbench=window
    return window
