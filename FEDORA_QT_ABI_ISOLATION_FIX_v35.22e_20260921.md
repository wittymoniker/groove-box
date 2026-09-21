# Fedora Qt ABI isolation fix — v35.22e

Fedora desktop launchers now isolate Groovebox from user-site pip PyQt6 wheels and PYTHONPATH.
This prevents ~/.local PyQt6 from being loaded against Fedora /lib64 Qt6 libraries, which caused:
`Qt_6_PRIVATE_API not found`.

The project .venv is also forced to expose system-site-packages on Fedora so the matched RPM
`python3-pyqt6-base` and `python3-pyqt6-webengine` bindings are used.
