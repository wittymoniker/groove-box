"""depmod must index the plain fat.ko even when a compressed copy already sits in the rootfs."""
import lzma, os, stat, subprocess, sys
from pathlib import Path

BUNDLER = Path(__file__).resolve().parent / "BUILD_ISO" / "bundle_vfat_modules_v35_22zo.py"
KV = "6.12.0-test"

MODINFO = "#!/bin/sh\ncase \"$(basename \"$3\")\" in vfat.ko*) echo fat;; *) echo '';; esac\n"
DEPMOD = '''#!/usr/bin/env python3
import sys, re
from pathlib import Path
root=Path(sys.argv[2]); kv=sys.argv[3]
base=(root/'lib').resolve()/'modules'/kv
pick={}
for p in sorted(base.rglob('*.ko*')):
    n=re.sub(r'\\.ko(\\.(xz|zst|gz))?$','',p.name)
    if n not in pick or p.name.endswith(('.xz','.zst','.gz')): pick[n]=p
(base/'modules.dep').write_text(''.join(f"{p.relative_to(base)}:\\n" for p in pick.values()))
'''


def test_compressed_duplicate_in_rootfs_does_not_break_depmod_index(tmp_path):
    bindir = tmp_path / "bin"; bindir.mkdir()
    for name, body in (("modinfo", MODINFO), ("depmod", DEPMOD)):
        f = bindir / name; f.write_text(body); f.chmod(f.stat().st_mode | stat.S_IXUSR)
    tree = tmp_path / "tree"; root = tmp_path / "root"
    for sub in ("kernel/fs/fat", "kernel/fs/nls"):
        (tree / sub).mkdir(parents=True)
    (root / "usr/lib").mkdir(parents=True); (root / "lib").symlink_to("usr/lib")
    for m in ("fat", "vfat"):
        (tree / "kernel/fs/fat" / f"{m}.ko.xz").write_bytes(lzma.compress(b"ELF"))
    for m in ("nls_ascii", "nls_cp437", "nls_utf8", "nls_iso8859_1"):
        (tree / "kernel/fs/nls" / f"{m}.ko.xz").write_bytes(lzma.compress(b"ELF"))
    dup = root / "usr/lib/modules" / KV / "kernel/fs/fat"; dup.mkdir(parents=True)
    (dup / "fat.ko.xz").write_bytes(lzma.compress(b"ELF"))      # the pre-existing duplicate
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    r = subprocess.run([sys.executable, str(BUNDLER), str(root), KV, str(tree)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert (dup / "fat.ko").is_file() and not (dup / "fat.ko.xz").exists()
