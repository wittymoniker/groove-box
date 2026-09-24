from pathlib import Path

ROOT=Path(__file__).resolve().parent

def test_rust_accel_has_no_crate_local_target_contract():
    build=(ROOT/'scripts'/'build_rust_accel.py').read_text()
    runtime=(ROOT/'platform_runtime.py').read_text()
    assert 'TemporaryDirectory' in build
    assert 'CARGO_TARGET_DIR' in build
    assert 'os.replace' in build
    assert "rust/groovebox_accel/target/release" not in runtime

def test_iso_streamer_has_isolated_cargo_source_and_target():
    sh=(ROOT/'BUILD_ISO'/'pool_newc_scan_v35_22w.sh').read_text()
    assert 'mktemp -d' in sh
    assert 'CARGO_TARGET_DIR' in sh
    assert 'cp -a "$TOOL/." "$CARGO_TMP/src/"' in sh
    assert '(cd "$CARGO_TMP/src" && cargo build --release)' in sh

def test_reported_rust_literals_are_fixed():
    src=(ROOT/'rust'/'groovebox_accel'/'src'/'lib.rs').read_text()
    assert 'x.abs()>0.99' in src
    assert 'y.abs()>=0.999' in src
    assert 'let b: f64=' in src
