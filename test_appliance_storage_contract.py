from pathlib import Path

ROOT=Path(__file__).resolve().parent
ISO=ROOT/'BUILD_ISO'

def test_iso_builder_source_tree_is_redistributed():
    assert (ISO/'RUN_ME_ZERO_STATE.sh').is_file()
    assert (ISO/'sos-install-appliance-limine-v33a').is_file()
    assert (ISO/'source/rootfs/usr/bin/groovebox-appliance').is_file()
    assert (ISO/'bundle_crc32c_modules_v35_22zq.py').is_file()
    assert (ISO/'verify_crc32c_install_v35_22zq.py').is_file()
    assert (ISO/'limine-live.conf').is_file()

def test_appliance_data_paths_and_installer_contract():
    launch=(ISO/'source/rootfs/usr/bin/groovebox-appliance').read_text(encoding='utf-8')
    install=(ISO/'sos-install-appliance-limine-v33a').read_text(encoding='utf-8')
    limine=(ISO/'limine-live.conf').read_text(encoding='utf-8')
    top=(ROOT/'BUILD_GROOVEBOX_APPLIANCE_ISO.sh').read_text(encoding='utf-8')
    assert 'GROOVEBOX_DATA_DIR' in launch and '/var/lib/groovebox' in launch
    # GROOVEBOX_R23R_NEARBY_INBOX_PY_LEVEL_20261031: the Nearby Grooveboxes/Inbox
    # data path is a Python-level contract (groovebox_paths.py), not a launch-script
    # concern. The launch script only sets GROOVEBOX_DATA_DIR; the Python code
    # creates the Nearby Grooveboxes/Inbox tree under that root.
    paths_src = (ROOT / 'groovebox_paths.py').read_text(encoding='utf-8')
    assert 'Nearby Grooveboxes/Inbox' in paths_src
    assert 'GROOVEBOX_V35_22ZQ_CRC32C_EXT4_MOUNT_PREFLIGHT_20260924' in install
    assert 'INSTALL_FS_READY|PASS ext4 vfat' in install
    assert 'protocol: linux' in limine.lower() and 'module_path:' in limine.lower()
    assert 'BUILD_ISO/RUN_ME_ZERO_STATE.sh' in top
    assert 'APPLIANCE_ISO' not in top

def test_release_packager_keeps_iso_builder_source():
    pkg=(ROOT/'PACKAGE_GROOVEBOX_RELEASE.sh').read_text(encoding='utf-8')
    assert 'BUILD_ISO/.fat-build' in pkg
    assert 'BUILD_ISO/dist/*.iso' in pkg
    assert 'APPLIANCE_ISO' not in pkg
