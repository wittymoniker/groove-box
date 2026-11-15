# R64 clock telemetry and smoothness diagnostics — FIX4

This patch builds on the FIX3 source archive. It adds read-only CPU clock-state diagnostics to the existing sOS appliance tuning path.

## Implemented
- `appliance_tuning.clock_snapshot()` reads per-core current frequency, active cpufreq governor, Intel EPP preference, generic cpufreq boost state, Intel `no_turbo` state, and available thermal-zone temperatures from Linux sysfs.
- The existing sOS policy still requests the supported `performance` governor and `performance` EPP hint where those controls are exposed. It does not raise firmware frequency limits, alter voltage, write MSRs, bypass thermal protections, or change BIOS settings.
- `run_groovebox.py` emits a compact `[sOS clock]` startup diagnostic after appliance tuning, so a real device can show whether firmware boost is enabled and what frequencies/thermal readings Linux exposes.
- The diagnostic explicitly treats missing sysfs nodes as unavailable rather than assuming a particular CPU vendor or firmware implementation.
- Added `test_appliance_clock_snapshot.py` for populated and absent sysfs cases, including a check that the snapshot function is read-only.

## Checks performed
- Python byte-compilation: changed Python files.
- Bash syntax: Secure Boot script, ISO master script, overlay sync script.
- Two clock telemetry regression checks passed.
- Synthetic repeated-entry Limine config test passed: kernel and initramfs receive exactly one 128-hex-character BLAKE2b pin per entry, and rerunning is idempotent.
- ZIP archive integrity and SHA-256 sidecars are generated for both archive formats.

## Limits / not claimed
- No ISO build, signing, firmware enrollment, physical boot, or physical hardware benchmark was performed here.
- CPU clock ceiling remains controlled by CPU firmware/BIOS, silicon capability, power delivery, and thermal limits. The application does not perform an unsafe overclock.
- A real smoothness assessment still requires the target machine's audio underrun/xrun counters, CPU frequency/thermal telemetry under load, and measured frame/audio latency.
