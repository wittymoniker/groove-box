# R98 repair plan / handoff to Claude

## Priority 1 — validate the Python contract fix

Use the patched `runtime_contract.py` and `BUILD_ISO/stage_appliance_real_v35_22zz.py` in this archive. Do not copy only one of the duplicate contract files: the root source and `BUILD_ISO/app-overlay-v35.22zz/runtime_contract.py` are both updated.

Expected policy:
- Required: `numpy`, `scipy`, `cffi`, `PyQt6.QtCore`, `PyQt6.QtMultimedia`, `PyQt6.QtMultimediaWidgets`, `PIL`.
- Optional: `sounddevice`, `PyQt6.QtWebEngineWidgets`.

This mirrors the supplied `BUILD_KIT/build.py` policy: SciPy is directly imported by the build checker; sounddevice is conditional and the Qt/OS audio path is the fallback. Do not remove SciPy from the appliance contract just to suppress the failure. First establish whether the user's local build.py edit differs from the archived source.

## Priority 2 — inspect the actual failed import

On a rebuilt image, after a failed GUI start, collect:

```sh
cat /var/log/sos/python-runtime-probe.log
# fallback location if /var/log/sos was not writable:
cat /tmp/groovebox-python-runtime-probe.log
```

The log distinguishes missing Python modules from native shared-library load failures. If SciPy fails, inspect the exact exception and `ldd` the named extension module inside the rootfs. If PyQt6 fails, inspect which interpreter was selected, its `sys.path`, Debian `python3-pyqt6` packages and Qt shared libraries. If only sounddevice is unavailable, GUI startup should now continue and the app should use its supported native Qt/OS audio fallback.

## Priority 3 — ensure build/runtime parity

Check the final rootfs, not just the host venv:

```sh
chroot "$ROOTFS" /opt/pyvenv/bin/python3 -c 'import numpy, scipy, cffi, PIL; from PyQt6 import QtCore, QtMultimedia, QtMultimediaWidgets; print("required imports OK")'
chroot "$ROOTFS" /opt/pyvenv/bin/python3 -c 'import sounddevice; print(sounddevice.__version__)' || echo 'sounddevice unavailable: optional backend'
```

Only run these if `$ROOTFS` is a valid target rootfs and host architecture matches. Do not run chroot against an incomplete staging tree and interpret failure as a package regression.

`runtime_setup_v35_22q.sh` currently installs and directly imports `sounddevice` plus PortAudio as a Linux provisioning-time check. That is a stronger image-build policy than the generic desktop `BUILD_KIT/build.py` policy. Decide explicitly whether the Linux image must always ship PortAudio. If yes, keep that provisioning gate but keep the GUI import gate optional so a missing optional backend does not prevent the whole application from opening. If no, separately make the provisioning check optional and verify all audio fallback paths; do not silently delete the check.

## Priority 4 — separate D-Bus issue

A separate photograph showed `user D-Bus failed to start`, while a later one passed D-Bus/transport preflight and reached the GUI. Do not conflate the two. If it recurs, capture the full media log around the daemon launch and inspect `$GB_RUN` ownership, stale bus socket state, daemon stderr and `dbus-send` response. Do not mark readiness successful unless the session bus answers `ListNames`.

## Validation already performed for this patch

- Python compilation / AST parse for modified contract, stage script and tests.
- Focused runtime-contract policy test passed.
- Four stage/launcher fixture variants passed, including shell syntax and Python symlink checks.
- ZIP integrity check passed.

Not performed: full ISO build, boot, physical hardware, SSD installation or live audio test. Required pinned kernel/initramfs/Limine build inputs were not available. Preserve the known-good build and do not overwrite the working USB while testing.
