"""Raw-cpio / compressed initramfs sniffing (GROOVEBOX_INITRD_IO_SNIFF_20261029)."""
import bz2, gzip, lzma, subprocess, sys, tempfile
from pathlib import Path

BI = Path(__file__).resolve().parent / "BUILD_ISO"
sys.path.insert(0, str(BI))
import initrd_io  # noqa: E402
from newc_pool_v35_22w import collect  # noqa: E402


def _newc(name: bytes, body: bytes) -> bytes:
    def a4(b): return b + b"\0" * ((-len(b)) & 3)
    hdr = b"070701" + b"".join(b"%08X" % v for v in (1, 0o100644, 0, 0, 1, 0, len(body), 0, 0, 0, 0, len(name) + 1, 0))
    return a4(hdr + name + b"\0") + a4(body)


def _archive() -> bytes:
    return (_newc(b"opt/groovebox/scode_optimizer_bridge.py", b"MARK") +
            _newc(b"TRAILER!!!", b""))


def test_every_format_reads_identically():
    raw = _archive()
    with tempfile.TemporaryDirectory() as td:
        for kind, blob in (("newc", raw), ("gzip", gzip.compress(raw)),
                           ("xz", lzma.compress(raw)), ("bzip2", bz2.compress(raw))):
            p = Path(td) / f"i.{kind}"
            p.write_bytes(blob)
            assert initrd_io.detect(p) == kind
            assert initrd_io.read_all(p) == raw
            assert collect(p)["opt/groovebox/scode_optimizer_bridge.py"] == b"MARK"


def test_raw_cpio_is_not_sent_to_gzip():
    # Regression: BadGzipFile: Not a gzipped file (b'07')
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "cache.cpio"
        p.write_bytes(_archive())
        assert collect(p)  # must not raise


def test_garbage_is_rejected_clearly():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad"
        p.write_bytes(b"not an initramfs at all")
        try:
            initrd_io.read_all(p)
        except RuntimeError as e:
            assert "not a recognised initramfs" in str(e)
        else:
            raise AssertionError("garbage accepted")


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("PASS", n)
