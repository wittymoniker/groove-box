"""clip_edit_ops.py (R132): edits for the Multitrack Clip Studio — split, snap to beat, layer up/down.

Records are the studio's row dicts: start (timeline s), in / out (source s), track, …  Originals are never touched.
"""
from __future__ import annotations

import copy


def split_record(rec, at):
    """Split one clip at timeline time `at` → (left, right). Raises ValueError when `at` is not inside the clip."""
    length = rec["out"] - rec["in"]
    if not (rec["start"] < at < rec["start"] + length):
        raise ValueError(f"{at:.3f} s is not inside this clip ({rec['start']:.3f}–{rec['start'] + length:.3f} s)")
    cut = rec["in"] + (at - rec["start"])
    left, right = copy.deepcopy(rec), copy.deepcopy(rec)
    left["out"] = cut
    right["in"] = cut; right["start"] = at
    fx = right.get("fx") or {}
    if "fade_in" in fx:                 # a fade-in belongs to the first half only, a fade-out to the second
        fx.pop("fade_in", None)
    if "fade_out" in (left.get("fx") or {}):
        left["fx"].pop("fade_out", None)
    return left, right


def snap_records(recs, bpm, division=4):
    """Move every clip start to the nearest 1/division of a beat at `bpm` (division 4 = sixteenth notes)."""
    grid = 60.0 / max(1e-6, float(bpm)) / max(1, int(division))
    out = []
    for r in recs:
        r = dict(r); r["start"] = round(round(r["start"] / grid) * grid, 6); out.append(r)
    return out


def move_layer(rec, delta):
    r = dict(rec); r["track"] = max(1, int(r.get("track", 1)) + int(delta)); return r


def install(studio, actions_layout):
    """Buttons on the Clip Studio action row."""
    from PyQt6.QtWidgets import QPushButton, QInputDialog, QMessageBox

    def rows():
        return sorted({x.row() for x in studio.table.selectedIndexes()})

    def replace(r, recs):
        studio.table.removeRow(r)
        for rec in recs:
            studio._add_row(rec)

    def split():
        sel = rows()
        if not sel:
            QMessageBox.information(studio, "Split", "Select a clip first."); return
        rec = studio._row_data(sel[0]); mid = rec["start"] + (rec["out"] - rec["in"]) / 2
        at, ok = QInputDialog.getDouble(studio, "Split clip", "Split at timeline time (s):", mid, rec["start"],
                                        rec["start"] + rec["out"] - rec["in"], 3)
        if ok:
            try:
                replace(sel[0], split_record(rec, at))
            except ValueError as exc:
                QMessageBox.warning(studio, "Split", str(exc))

    def snap():
        host = studio.parent()
        bpm0 = 120.0
        try:
            bpm0 = float(host.spin_bpm.value())
        except Exception:
            pass
        bpm, ok = QInputDialog.getDouble(studio, "Snap to beat", "Tempo (BPM) — starts snap to 1/16 notes:", bpm0, 20, 400, 2)
        if not ok:
            return
        recs = snap_records(studio._records(), bpm, 4)
        studio.table.setRowCount(0)
        for r in recs:
            studio._add_row(r)

    def layer(delta):
        for r in rows():
            rec = move_layer(studio._row_data(r), delta)
            studio.table.item(r, 5).setText(str(rec["track"]))
        studio._update_estimate()

    for cap, tip, fn in (("✂ Split…", "Split the selected clip in two at a timeline time", split),
                         ("🧲 Snap to beat", "Move every clip start to the nearest 1/16 note at the project tempo", snap),
                         ("⬆ Layer", "Selected clips one layer higher (drawn on top)", lambda: layer(1)),
                         ("⬇ Layer", "Selected clips one layer lower", lambda: layer(-1))):
        b = QPushButton(cap); b.setToolTip(tip); b.clicked.connect(lambda _c=False, f=fn: f()); actions_layout.addWidget(b)
