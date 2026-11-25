"""editors_hub.py (R132): one multi-tab launcher window for every editor and tool (task bar ▸ ✎ Editors / 🚀 Launcher).

Tabs: ✎ Create (clip, image, audio, 3D, music video, live player) · ⌨ Code (Lua, programs, plugin compiler, script
studio, console) · 🗂 Files & OS (file studio, ISO parts split/join, ISO builder, drives, burn) · 📡 Network & devices
(connections, network drives, phone files / update from phone, peer sharing). Each button opens the tool once
(a second click brings the open window forward).
"""
from __future__ import annotations

TABS = (
    ("✎ Create", (
        ("🎞 Clip Studio", "Multitrack clips: audio · video · images · text · OBJ", "@_r32_open_clip_editor", ""),
        ("🖌 Image Editor", "Layers, paint, 2D effects, canonical filter chain", "image_editor", "open_window"),
        ("🎚 Audio Editor", "Select · cut · soft FX · canonicalize", "audio_editor", "open_window"),
        ("🧊 3D Studio", "Shapes, mesh tools, keyframes, stereo video", "studio_3d", "open_window"),
        ("🎛 Live Player", "Perform, record and project the video live", "live_player", "open_live_player"),
        ("🌀 Multidim synth", "The master-dimensional synth and its panels", "multidim_ui", "open_multidim_window"),
        ("🧬 Mod Path Bay", "Any source × any method → any target", "mod_matrix", "open_window"),
        ("🧪 Media transmuter", "Sound ⇄ image ⇄ video ⇄ game ⇄ project", "media_transmuter", "open_window"),
    )),
    ("⌨ Code", (
        ("🌙 Lua", "LuaJIT scripting workspace", "lua_workspace", "open_window"),
        ("🛠 Programs", "C, C++, Rust, Go, Julia, Python, shell", "program_builder", "open_window"),
        ("🔧 Plugin Compiler", "Real LV2 audio plugins: build, test, install", "plugin_compiler_kit", "open_window"),
        ("🔌 Plugins", "The plugin library: create · inform · games · live tools", "plugin_library", "open_window"),
        ("◈ Fractal Dev Kit", "Scaffold, doctor, preview", "fractal_devkit", "open_window"),
        ("⌘ Command Console", "Commands · !shell · sudo · run · py", "command_console", "open_window"),
    )),
    ("🗂 Files & OS", (
        ("📂 File Studio", "Move and edit everything", "file_studio", "open_window"),
        ("🧩 Parts: split & join", "Slice big files into parts, stitch parts back (SHA-256 checked)", "iso_parts", "open_window"),
        ("🛠 ISO builder", "Rebuild / full zero-state build (unsigned or Secure Boot) to a drive", "@_r132_open_iso_builder", ""),
        ("💽 Drives", "Format, partition, write a bootable USB", "file_studio", "open_window|Drives"),
        ("🛟 Recovery", "Project checkpoints and recovery", "project_transactions", "open_window"),
        ("🖥 System settings", "sOS / desktop settings, scale, audio", "sos_system_settings", "open_window"),
    )),
    ("📡 Network & devices", (
        ("🔌 Connections", "Ethernet · Wi-Fi · speed test · status page", "network_lan", "open_network_window"),
        ("🗄 Network drives", "SMB / NFS on your LAN", "network_lan", "open_drives_window"),
        ("📱 Phone files", "iPhone and Android over USB", "network_lan", "open_iphone_window"),
        ("📲 Update from phone", "Send an update archive from a phone browser (PIN)", "network_hub", "open_window"),
        ("🔁 Peer sync", "Syncthing: keep folders in sync with your other devices", "network_lan", "open_peer_sync"),
        ("🌐 Web browser", "Browse (clock is synced first so certificates are valid)", "web_browser", "open_window"),
    )),
)


def _open(app, mod, fn):
    if mod.startswith("@"):
        m = getattr(app, mod[1:], None)
        if m is None:
            raise AttributeError(mod[1:])
        return m()
    import importlib
    fn, *extra = fn.split("|")
    m = importlib.import_module(mod)
    target = getattr(m, fn, None) or getattr(m, "open_window", None)
    if target is None:
        raise AttributeError(f"{mod}.{fn}")
    try:
        import window_registry as wr
        return wr.launch(f"{mod}.{fn}:hub:{','.join(extra)}", lambda: target(app, *extra))
    except ImportError:
        return target(app, *extra)


def open_window(app=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QGridLayout, QPushButton, QLabel
    old = getattr(app, "_r132_editors_hub", None) if app is not None else None
    try:
        if old is not None:
            old.show(); old.raise_(); old.activateWindow(); return old
    except RuntimeError:
        pass
    d = QDialog(app); d.setWindowTitle("✎ Editors & Tools"); d.resize(820, 460)
    v = QVBoxLayout(d); tabs = QTabWidget(); v.addWidget(tabs)
    msg = QLabel(""); msg.setWordWrap(True); v.addWidget(msg)
    for title, items in TABS:
        page = QWidget(); g = QGridLayout(page); g.setSpacing(8)
        for i, (cap, tip, mod, fn) in enumerate(items):
            b = QPushButton(cap + "\n" + tip); b.setMinimumHeight(64); b.setToolTip(tip)
            b.setStyleSheet("QPushButton{text-align:left;padding:8px 12px;font-weight:700;}")

            def go(_c=False, m=mod, f=fn, c=cap):
                try:
                    _open(app, m, f); msg.setText("opened " + c)
                except Exception as exc:
                    msg.setText(f"{c}: {exc}")
            b.clicked.connect(go); g.addWidget(b, i // 2, i % 2)
        tabs.addTab(page, title)
    if app is not None:
        app._r132_editors_hub = d
    d.show()
    return d
