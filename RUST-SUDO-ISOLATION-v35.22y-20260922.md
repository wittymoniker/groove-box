# v35.22y Rust sudo-isolation repair

- Fixes Rust float literal/type errors in `rust/groovebox_accel/src/lib.rs`.
- Cargo builds never use `rust/groovebox_accel/target/`.
- `scripts/build_rust_accel.py` uses an isolated temporary `CARGO_TARGET_DIR` and atomically installs the native library.
- A prior root-owned `rust/groovebox_accel/target/` can remain on disk; current launch/build code ignores it.
- Root/sudo ISO builds normalize the installed Rust library owner back to the source-tree user when possible.
- The ISO newc scanner also builds in an isolated temporary Cargo target, preventing root-owned `BUILD_ISO/tools/.../target` state.
- Rust remains a required release dependency; Python newc fallback is diagnostic-only unless explicitly enabled.
