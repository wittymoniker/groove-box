# Mathematician's Groovebox — Full Clean Standalone Source

This distribution keeps the active Groovebox project tree while removing stale redistribution artifacts and generated caches.

## Main entry point

```bash
python3 groovebox.py
```

## Included

- current `groovebox.py`
- active Groovebox Python modules
- tests
- C++ accelerator source and build files
- Julia bridge/source
- native support source/folder structure
- provisioning/build/install scripts
- documentation
- sample project data
- dependency manifests

## Deliberately removed

- `__pycache__`, `.pyc`, `.pyo`
- nested `RUN ME FIRST` / `UNZIP ME` archives
- old duplicate `launcher groovebox.py`
- prebuilt `.so` accelerator binaries (rebuild from source for the target system)
- generated render output

The final polished main application includes the Finite Infinity–Meum HyperDrive, project-persistent OT/Trig/Meum/Symbol controls, image-frame export, Radio UI fixes, canonical automation restoration, and Symbols-OFF zero-overlay path.

## Build the standalone application

The authoritative application builder is the restored known-good BUILD_KIT lineage:

```bash
python3 build.py --doctor
python3 build.py
```

`build.py` delegates to `BUILD_KIT/build.py`. The lower-level `scripts/build_linux.sh` only builds the native accelerator and is not the complete desktop application build.

Linux desktop / Discover / Flatpak / Fedora packaging material is under `packaging/`.
