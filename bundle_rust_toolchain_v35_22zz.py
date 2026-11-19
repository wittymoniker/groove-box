#!/usr/bin/env python3
"""Bundle a host Rust toolchain into the sOS rootfs.

Fedora's packaged rustc reports sysroot=/usr. Copying that tree pulls in
MinGW, cross libs, and the rest of /usr and fills the disk (Errno 28).
Copy only rustc, cargo, and the host rustlib.
"""
from pathlib import Path
import shutil, subprocess, sys

def _host_triple(rustc: str) -> str:
    try:
        out = subprocess.check_output([rustc, "-vV"], text=True)
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: bundle_rust_toolchain_v35_22zz.py ROOTFS")
    root = Path(sys.argv[1])
    dest = root / "opt/sos/rust"
    bind = dest / "bin"
    rustc = __import__("sos_tools").which("rustc")
    cargo = __import__("sos_tools").which("cargo")
    if not rustc or not cargo:
        raise SystemExit("FAIL: host Rust/Cargo missing before ISO Rust bundle")
    sysroot = Path(subprocess.check_output([rustc, "--print", "sysroot"], text=True).strip()).resolve()
    host = _host_triple(rustc)
    if dest.exists():
        shutil.rmtree(dest)
    bind.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rustc, bind / "rustc")
    shutil.copy2(cargo, bind / "cargo")
    # Host rustlib only. Never copy /usr or MinGW cross trees.
    rustlib = sysroot / "lib" / "rustlib"
    copied = []
    if rustlib.is_dir():
        for child in rustlib.iterdir():
            name = child.name
            if "mingw" in name or "windows" in name or "w64" in name:
                continue
            if host and name not in (host, "etc", "src"):
                # Keep the host target and small shared dirs only.
                if name not in ("etc",) and host not in name:
                    continue
            target = dest / "lib" / "rustlib" / name
            if child.is_dir():
                shutil.copytree(child, target, symlinks=True, ignore=shutil.ignore_patterns("*mingw*", "*windows*"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
            copied.append(name)
    (dest / "cargo-home").mkdir(exist_ok=True)
    (root / "opt/sos/RUST-v35.22zz.txt").write_text(
        "Rust toolchain bundled into sOS ISO (host only; /usr and MinGW excluded)\n"
        + subprocess.check_output([rustc, "--version"], text=True)
        + subprocess.check_output([cargo, "--version"], text=True)
        + f"sysroot={sysroot}\nhost={host}\ncopied={copied}\n"
    )
    print("RUST_ISO_TOOLCHAIN|PASS", sysroot, "host", host, "->", dest)
if __name__ == "__main__":
    main()
