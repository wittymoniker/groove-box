# Patch notes — R98 Python runtime import gate

- Resolved contract mismatch: `sounddevice` is optional in the canonical runtime gate, consistent with the supplied BUILD_KIT checker and lazy audio backend. `scipy` remains required.
- Added per-interpreter import diagnostics and traceback logging; retained venv -> system Python fallback and fatal status 70 for missing required modules.
- Mirrored runtime contract change into the appliance overlay copy.
- Added regression test `BUILD_ISO/test_runtime_contract_diagnostics.py`.
- Updated launcher stage regression test to require visible diagnostics.
- No Secure Boot, ACPI, D-Bus, kernel, input, or installer boot parameters changed.
