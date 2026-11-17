"""Task-pad editor for directional canonical/seed/user ownership rules.

The dialog edits a project-level policy object. Engine writers can consume the
same normalized policy through canonical_ownership; this UI never mutates
sequence/user data by itself.
"""
from __future__ import annotations

from copy import deepcopy

from canonical_ownership import default_policy, normalize_policy, policy_summary


def open_dialog(host, parent=None):
    try:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QCheckBox, QDoubleSpinBox, QPushButton,
                                     QComboBox, QGroupBox, QFormLayout)
    except Exception as exc:
        if hasattr(host, "_task_pad_say"):
            host._task_pad_say(f"Canonical Rules UI unavailable: {exc}")
        return None

    dlg = QDialog(parent or host)
    dlg.setWindowTitle("Canonical Rules · Ownership & Modes")
    dlg.setMinimumWidth(520)
    dlg.setStyleSheet("QDialog{background:#111a27;color:#d9efff;} QGroupBox{border:1px solid #42617a;border-radius:7px;margin-top:8px;padding:8px;color:#9fe5ff;font-weight:800;} QLabel{color:#d9efff;} QCheckBox{color:#d9efff;} QDoubleSpinBox,QComboBox{background:#17283a;color:#e6f7ff;border:1px solid #52758e;padding:4px;}")
    root = QVBoxLayout(dlg)
    intro = QLabel("Incoming-writer policy: each writer decides whether it blends with the value already present. Strength is 0–100%. Step gates use weighted active/inactive votes when blending is enabled.")
    intro.setWordWrap(True)
    root.addWidget(intro)
    policy = normalize_policy(getattr(host, "canonical_ownership_policy", None))
    controls = {}
    group = QGroupBox("Directional overwrite / blend policy")
    form = QFormLayout(group)
    for source in ("canonical", "seed", "user"):
        line = QHBoxLayout()
        blend = QCheckBox("Allow incoming blend")
        blend.setChecked(policy[source]["blend"])
        strength = QDoubleSpinBox()
        strength.setRange(0.0, 100.0); strength.setDecimals(1); strength.setSingleStep(5.0)
        strength.setSuffix(" %"); strength.setValue(policy[source]["strength"] * 100.0)
        line.addWidget(blend); line.addStretch(1); line.addWidget(QLabel("Strength")); line.addWidget(strength)
        form.addRow(source.title(), line)
        controls[source] = (blend, strength)
    root.addWidget(group)

    modes = QGroupBox("Canonical operation mode")
    mform = QFormLayout(modes)
    mode = QComboBox()
    mode.addItems(["Seeded Baseline → Canonical Control", "Canonical First", "Userdata First", "Diagnostic Only"])
    current = str(getattr(host, "canonical_operation_mode", "Seeded Baseline → Canonical Control"))
    if mode.findText(current) >= 0:
        mode.setCurrentText(current)
    mform.addRow("Mode", mode)
    mode.setToolTip("Seeded Baseline remains a fallback layer; it never replaces canonical generation.")
    root.addWidget(modes)

    summary = QLabel(policy_summary(policy)); summary.setWordWrap(True)
    root.addWidget(summary)
    buttons = QHBoxLayout()
    reset = QPushButton("Restore defaults")
    save = QPushButton("Apply")
    close = QPushButton("Close")
    buttons.addWidget(reset); buttons.addStretch(1); buttons.addWidget(save); buttons.addWidget(close)
    root.addLayout(buttons)

    def collect():
        return normalize_policy({s: {"blend": controls[s][0].isChecked(),
                                    "strength": controls[s][1].value() / 100.0}
                                 for s in controls})

    def update_summary(*_):
        summary.setText(policy_summary(collect()))
    for blend, strength in controls.values():
        blend.toggled.connect(update_summary); strength.valueChanged.connect(update_summary)

    def restore():
        defaults = default_policy()
        for s, (blend, strength) in controls.items():
            blend.setChecked(defaults[s]["blend"])
            strength.setValue(defaults[s]["strength"] * 100.0)
        mode.setCurrentText("Seeded Baseline → Canonical Control")
        update_summary()

    def apply():
        host.canonical_ownership_policy = collect()
        host.canonical_operation_mode = mode.currentText()
        try:
            if hasattr(host, "_push_undo"):
                host._push_undo("Canonical ownership rules")
            if hasattr(host, "_on_live_source_changed"):
                host._on_live_source_changed()
            if hasattr(host, "_task_pad_say"):
                host._task_pad_say("Canonical rules applied · " + policy_summary(host.canonical_ownership_policy))
        except Exception:
            pass
        dlg.accept()

    reset.clicked.connect(restore); save.clicked.connect(apply); close.clicked.connect(dlg.reject)
    dlg.exec()
    return deepcopy(getattr(host, "canonical_ownership_policy", policy))
