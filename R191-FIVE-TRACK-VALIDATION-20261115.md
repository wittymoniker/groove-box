# R191 five-track validation — 2026-11-15

| Gate | Result | Notes |
|---|---|---|
| Focused regression suite | PASS | 42 passed, 2 skipped |
| Changed Python syntax | PASS | `py_compile` |
| Runtime overlay parity | PASS | 427/427 files |
| Release marker consistency | PASS | refreshed with `scripts/stamp_release.py` |
| ISO source preflight | PASS | 697 Python, 127 shell, 13 contract commands |
| Synthetic hybrid ISO | PASS | bundled Limine host tool; not appliance image |
| Linux/macOS builder CLI | PASS | help/dispatch only |
| Top-level build orchestration | PASS | app and ISO explicitly skipped |
| Live Qt GUI | NOT RUN | PyQt6 unavailable |
| Julia runtime / parity | NOT RUN | Julia executable unavailable |
| Linux desktop packaging | BLOCKED | build venv, PyQt6, PyInstaller/codecs unavailable |
| Windows/macOS native packaging | NOT RUN | requires native hosts |
| Actual paired appliance ISOs | BLOCKED | Cargo/Rust, container, image/signing tools unavailable |
| QEMU/OVMF / USB / install / rollback | NOT RUN | required host tooling and VM/firmware acceptance absent |
| Physical hardware / certified safety | NOT RUN | requires actual devices and qualified fixtures |

The source preflight and synthetic fixture are not evidence that a real appliance ISO was built or booted.
