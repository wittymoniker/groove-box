# MATH-GROOVEBOX R123 phase 5 — build fix for the CXXABI_1.3.15 failure (UNVERIFIED)

Status: source fix + local unit tests only. The full ISO build, GUI session, boot and
installer validation have NOT been run here (no container/KVM on the build host).
Treat as an unverified candidate until those acceptance steps pass.

## Fixed: release runner exit 46 (Julia libstdc++ shadowing Mesa/Z3)
Log: `libEGL_mesa.so.0: /opt/sos/julia/lib/julia/libstdc++.so.6: version 'CXXABI_1.3.15'
not found (required by /lib/x86_64-linux-gnu/libz3.so.4)`.

`BUILD_ISO/runtime_setup_v35_22q.sh` (GROOVEBOX_R123_JULIA_ABI_UNIFY_20261119, R123.1):
- `gb_julia_abi_unify` compares the highest GLIBCXX/GCC version of Julia's private
  libstdc++/libgcc_s with the system copy (`sort -V`). When the system copy is the same or
  newer, Julia's private files are moved to `lib/julia/julia-private-abi/` (never scanned by
  the loader or ldconfig) and the soname becomes a symlink to the system library, so every
  process (Julia, Mesa, Z3, Qt) maps exactly one C++ runtime.
- Removes any `/opt/sos/julia` entry from `/etc/ld.so.conf(.d)`.
- Runs after the Julia install and again after the Pkg/juliacall/Lua steps, just before `ldconfig`.
- `LD_LIBRARY_PATH` / `LD_PRELOAD` used for the Julia warm-up are saved and restored, so they
  never leak into the native-library check.
- The native check now runs `ldd` in a clean environment and fails on "not found" OR any
  dependency resolved from `/opt/sos/julia/` ("unresolved or Julia-shadowed dependency").
- The stamp-time `julia_abi_unify.py` sees the new symlinks as already unified (no conflict).

## Also included (repairs since phase 4)
- `ui_autostate.py` (GROOVEBOX_R123_EXPLICIT_STATE_WINS_20261119) + `groovebox.py`
  `_apply_project_snapshot`: values set explicitly by a loaded project (e.g. Reverse time) are no
  longer overwritten by stale saved UI auto-state.
- Test realignment: `test_r107_launch_hardening_20261118.py` now expects the R114 juliacall pin
  (>=0.9.37) and the R123 no-bytecode syntax gate (R107/R108 forbid compileall writes in the image).
- New test `BUILD_ISO/test_r123_julia_abi.py` (fake-tree run of the unifier; 3 pass).

## What to do
Rerun the build (`RUN_ME_v33c.sh` / the release runner). Expected log lines:
`[R123-ABI] .../libstdc++.so.6 -> /usr/lib/x86_64-linux-gnu/libstdc++.so.6 (system GLIBCXX_… >= Julia GLIBCXX_…)`
and no "Julia-shadowed dependency" failures. If it still fails, send the log from the first
`[R123-ABI]` line onward.

My own further improvements/recommendations will come in a later, separate archive.
