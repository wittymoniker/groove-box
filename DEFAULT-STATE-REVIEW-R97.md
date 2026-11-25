# Default-state review — R97

This pass distinguishes three categories rather than making blanket numeric changes:

1. **Canonical-owned project data** — values produced by Canonical / Seed / User ownership are resolved by the project provenance system. Compatibility-setting migrations must not rewrite those values. The migration helper supports an explicit `canonical_owned` exclusion list and the current display migration applies only to a non-canonical app preference.
2. **Hardware-dependent operating values** — worker count (`threads=0`), audio block size (`0`), audio latency (`auto`), scene size (`auto`), hardware class (`auto`), and adaptive worker mode remain automatic. A single machine-independent numeric optimum would be scientifically unsound across different cores, memory limits, audio devices, screens, and output clocks.
3. **Safe factory-default migration** — old untouched UI scale 100% migrates to the existing display-aware Auto value (0). Explicitly changed values are tracked and preserved; canonical-owned values are excluded. New default remains Auto.

Other defaults were reviewed but not changed in this pass because there is no parameter-specific benchmark, perceptual/functional acceptance criterion, or cross-device evidence for a replacement. In particular, audio block sizes, processing thread counts, carrier mix, tile sizing, memory budgets, and export settings remain adaptive or existing defaults. Future migrations should add one setting at a time with a recorded rationale, provenance exclusion, deterministic test, and reversible boundary.

R97 additionally restores the persisted `party_feel` setting (`calm`, `classic`, `rave`), which was defined in defaults and used by the UI but not read back from stored settings. Party Mode remains ON for new profiles, while an existing profile with `party_defaults_r6=True` keeps its explicitly saved ON/OFF bit; the redundant final migration that previously forced it ON was removed.
