# R191 service-routing integration draft — 2026-11-15

This pass routes the existing R56–R64/R191 service layer through one application-lifetime object and exposes operational controls in the Command Center. It is an integration draft, not a release acceptance record.

## Application wiring

- The main window already installs `groovebox_runtime.command_center.install_command_center(self)`.
- Command Center now creates/reuses one `ApplicationRuntimeServices` graph for the main-window lifetime. The graph owns notifications, the local resumable sync queue, task supervisor, read-only hardware discovery and hot-plug monitor, persistent device permissions, extension metadata/layout/debug services, project checkpoints, performance/memory services, Secure Boot diagnostics, and release acceptance ledger.
- The graph is stopped when the main window is destroyed or the Qt application exits.
- The toolbar status refreshes on a bounded GUI timer. Worker threads do not mutate Qt widgets.

## Routed panels

- **Overview:** service graph status, checkpoint action, read-only Secure Boot report export.
- **Notifications:** persisted notification listing, mark-read, dismiss.
- **Sync queue:** user-selected local source/destination, resumable background copy, pause/resume/retry/remove.
- **Hardware:** read-only inventory, recent hot-plug events, persistent per-device capability grants/revocation. Granting permission does not open a device or instantiate a driver.
- **Extensions:** shared metadata pool, declarative panel create/import/export with undo/redo, deterministic package creation, theme-pack validation, debugger event view, lifecycle/fault/trust status. Extension code is not executed by this UI.
- **Workspaces:** local immutable host-state checkpoints, JSON export, three-way conflict preview. Conflict cases are not auto-promoted; the UI requires explicit choice before saving.
- **Updates & release:** ZIP inspect/stage, fixed-chunk delta build/apply to a caller-selected regular file, release-gate evidence visibility.
- **Performance:** advisory scheduler/background status, latency/callback snapshots, memory-fabric status, memory profile and phrase-transition preview. Missing producer data remains visibly empty/unknown; this is not a live CPU/audio benchmark.
- **Diagnostics:** preview and export a redacted text-only runtime report with credential stores, key material and absolute state paths excluded.
- **GOAVA:** Autopilot panel now reuses the application service graph's `GoavaActivityController` rather than constructing a second controller on each panel instance.

## Safety and integration limits

- No connector provider is invented or registered without a real adapter. The dashboard reports that no provider is connected unless one is explicitly registered and authorized.
- Device grants are permission metadata only; they do not imply live device validation.
- Updates are staged in user space; no block device, EFI variable, bootloader, or system partition is written.
- Checkpoints are exported as JSON; they do not silently overwrite the active project or restart playback.
- Diagnostics are preview-first, credential-path filtered, text-only and redacted.
- Actual Qt rendering/lifecycle validation is not claimed because PyQt6 is unavailable in this environment. The source is compiled and the headless service contracts are covered separately.

## Files changed

- `groovebox_runtime/command_center.py`
- `groovebox_runtime/service_hub.py` (new)
- `groovebox_runtime/diagnostic_bundle.py`
- `tests/test_r191_service_hub_integration.py` (new)
- active ISO runtime overlay synchronized by `scripts/sync_runtime_payload.py`

## Next acceptance steps

1. Run the focused Python tests and then the supported full suite.
2. Run the app on a PyQt6/display-capable host and walk every Command Center panel, including repeated open/close and main-window shutdown.
3. Exercise local sync cancellation/resume and device permission revocation with disposable test fixtures.
4. Continue the separate release-host ISO, QEMU/OVMF, firmware, installer, rollback, USB and physical-hardware gates.
