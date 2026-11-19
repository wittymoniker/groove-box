# R98 boot failure — technical diagnosis (17 Nov 2026)

## Confirmed from the supplied R98 source and boot photographs

The photographed GUI launch failure is the generated `/usr/bin/groovebox-appliance.real` runtime gate exiting with status 70. The launcher tried `/opt/pyvenv/bin/python3`, fell back to `/usr/bin/python3`, and suppressed both probes' stdout/stderr with `>/dev/null 2>&1`. Consequently the screen only showed the generic message:

`FAIL: no appliance Python runtime passed the required PyQt6/scientific/audio import probe`

The probe imports the modules in `runtime_contract.REQUIRED`. The source contract included `sounddevice` as required. In contrast, `BUILD_KIT/build.py::verify_python_runtime()` explicitly treats `sounddevice` as optional and says Qt Multimedia / OS audio remains usable without it. `audio_os_backend.py` also documents and implements a lazy optional sounddevice import and reports PortAudio unavailable rather than failing module import. This is a real contract mismatch and a credible cause if the appliance's PortAudio wheel or native library is missing.

`scipy` is different in the supplied archive: `BUILD_KIT/build.py` imports `scipy` directly as part of its required build-runtime check, `runtime_setup_v35_22q.sh` installs it, and the appliance runtime contract requires it. Do not demote SciPy to optional without proving the application no longer needs it. If a local edit removed its direct checker import, that edit is not present in the supplied R98 archive and must be reconciled with this contract.

## Separate boot state

One photograph reports `SYSTEM_MEDIA_READY|FAIL|user D-Bus failed to start`. Another shows `SYSTEM_MEDIA_READY|PASS`, Wayland ready, input ready and local transport preflight passed before the Python launcher failed. These are distinct observed states. This patch does not claim the Python change repairs D-Bus. Preserve the D-Bus failure log and investigate it separately if it recurs.

## Other evidence

- Missing optional kernel modules in the input/EGL logs are not proven causal; later readiness gates passed.
- Labwc's `NextWindowImmediate` / `PreviousWindowImmediate` messages are separate config warnings.
- No evidence supports changing Secure Boot, ACPI, or boot parameters to solve this Python import-gate failure.

## Patch included

1. `sounddevice` moves from `REQUIRED` to `OPTIONAL`, matching the supplied application/backend policy. `scipy`, NumPy, cffi, PyQt6 Multimedia and Pillow remain required.
2. The launcher runs a diagnostic validator and writes `/var/log/sos/python-runtime-probe.log` (fallback `/tmp/groovebox-python-runtime-probe.log`). It reports interpreter/version/sys.path, each required import, exception and traceback; it also records optional-module availability.
3. It still tries the venv first, then system Python, and still exits 70 if required imports fail. It does not turn a broken runtime into a false PASS.
4. A focused regression test checks that SciPy stays required and sounddevice is optional in the canonical runtime contract.

## Limits

This is a source-level patch. It was syntax-checked and the focused stage/launcher regression fixtures passed. A complete ISO build and physical Dell boot were not performed. The archive's pinned kernel/initramfs/Limine inputs were unavailable in the build workspace. The actual missing import on the photographed machine remains unproven until the new probe log is collected.
