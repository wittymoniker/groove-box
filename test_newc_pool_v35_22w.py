from pathlib import Path

ROOT=Path(__file__).resolve().parent

def test_no_unbounded_archive_reads_in_pooled_verifiers():
    names=['verify_v31c.py','verify_cursor_sync_v32t.py','verify_console_disk_v32w.py','verify_kernel_input_v32m.py','verify_live_boot_v32w.py','verify_session_v35_22u.py','verify_egl_runtime_v35_22q.py']
    for name in names:
        s=(ROOT/'BUILD_ISO'/name).read_text(errors='replace')
        assert 'newc_pool_v35_22w' in s
        assert 'gzip.decompress' not in s
        assert "gzip.open(p,'rb').read()" not in s

def test_builder_uses_one_pool_then_parallel_fanout():
    s=(ROOT/'BUILD_ISO'/'build_from_v31c_layered_cache_v32x.sh').read_text(errors='replace')
    assert 'GROOVEBOX_V35_22W_PARALLEL_POOLED_VERIFY_20260922' in s
    assert 'pool_newc_scan_v35_22w.sh' in s
    assert 'python3 "$HERE/$name" "$archive" &' in s
    assert 'if ! wait "${pids[$i]}"' in s
