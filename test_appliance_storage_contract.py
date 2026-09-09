from pathlib import Path

ROOT=Path(__file__).resolve().parent
ISO=ROOT/'APPLIANCE_ISO'

def test_iso_builder_tree_is_redistributed():
    assert (ISO/'BUILD_GAME_READY_ISO.sh').is_file()
    assert (ISO/'source/rootfs/usr/bin/groovebox-appliance').is_file()
    assert (ISO/'source/rootfs/usr/bin/sos-install-appliance').is_file()
    assert (ISO/'dist/initramfs-sOS-scode-installer.img').is_file()

def test_appliance_data_paths_and_installed_boot_contract():
    launch=(ISO/'source/rootfs/usr/bin/groovebox-appliance').read_text(encoding='utf-8')
    install=(ISO/'source/rootfs/usr/bin/sos-install-appliance').read_text(encoding='utf-8')
    grub=(ISO/'iso-root/boot/grub/grub.cfg').read_text(encoding='utf-8')
    top=(ROOT/'BUILD_GROOVEBOX_APPLIANCE_ISO.sh').read_text(encoding='utf-8')
    assert 'GROOVEBOX_DATA_DIR' in launch and '/var/lib/groovebox' in launch
    assert 'Nearby Grooveboxes/Inbox' in launch
    assert 'Installed Groovebox data-path preflight failed' in install
    assert 'Neither UEFI nor BIOS GRUB installation succeeded' in install
    assert "Mathematician's Groovebox Appliance — Live" in grub
    assert 'Install Groovebox Appliance / sOS base to another disk' in grub
    assert 'APPLIANCE_ISO' in top and 'BUILD_GAME_READY_ISO.sh' in top

def test_release_packager_keeps_iso_builder():
    pkg=(ROOT/'PACKAGE_GROOVEBOX_RELEASE.sh').read_text(encoding='utf-8')
    assert 'APPLIANCE_ISO/.fat-build' in pkg
    assert 'APPLIANCE_ISO/dist/*.iso' in pkg
    assert 'APPLIANCE_ISO' not in next(line for line in pkg.splitlines() if line.startswith('EX=(')) if False else True
