# R64 Import Fabric — Core, sCode, User and Developer Applications

## Delivered source integration

- `import_fabric.py` provides a deterministic module-to-file map and AST import inventory.
- Startup initializes the cached map after thread-budget configuration and before importing the main UI/application tree.
- The cache is Python-ABI-specific, atomic-written, and invalidated when mapped source size/mtime signatures change.
- Core, user-app, and developer-overlay roots are represented separately; configurable roots use `GROOVEBOX_USER_APP_PATHS` and `GROOVEBOX_DEV_APP_PATHS`.
- `dev_overlay.import_map()` includes the active developer `src` tree and the user app directory without executing user code.
- `application_scope()` adds app-local paths temporarily and restores `sys.path` on exit.
- Exported/user scripts dispatched through `groovebox_subprocess.py` execute in their own child process and receive a scoped import path.
- `import_optional()` supports feature-triggered optional integrations; the map itself never imports all mapped modules.
- `timed_import()` and `import_timings()` expose requested-module load latency without triggering imports.
- Default user/developer roots follow the configured Groovebox data directory when available.

## Design boundaries

The import map is discovery metadata, not a sandbox. A module path being present does not grant permissions, make native extensions ABI-compatible, or make mutable Python module state safe to share. Untrusted apps remain subject to the existing child-process, extension permission, and hardware-access boundaries. Core imports are not copied into developer overlays. Native dependencies must still be declared in the selected runtime/package manifest.

## No-test rollout note

This update was packaged without running the project test suite, in accordance with the requested defer-until-R64 instruction. It has not yet been performance-benchmarked; startup cost and cold/warm cache behavior belong in the R64 acceptance pass.
