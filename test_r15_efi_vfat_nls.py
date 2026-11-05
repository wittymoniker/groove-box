from pathlib import Path
B=Path(__file__).resolve().parent/'BUILD_ISO'
bundle=(B/'bundle_vfat_modules_v35_22zo.py').read_text()
inst=(B/'sos-install-appliance-limine-v33a').read_text()
stamp=(B/'stamp_final_initramfs_v35_22zz.sh').read_text()
master=(B/'master_final_iso_v35_22zz.sh').read_text()
assert 'GROOVEBOX_V35_22ZZ_R15_EFI_VFAT_NLS_RUNTIME_CLOSURE_20260930' in bundle
assert 'lzma.decompress' in bundle and 'gzip.decompress' in bundle
assert 'load_required_module_r15' in inst and 'insmod "$ko"' in inst
assert 'for m in fat nls_ascii nls_cp437 nls_utf8 vfat' in inst
assert 'R15_EFI_VFAT_NLS_FINAL_IMAGE|PASS' in stamp
assert 'R15 required plain module missing' in stamp
assert 'GAME-READY-v35.22zz-R15-EFI-VFAT-NLS' in master
print('PASS: v35.22zz-R15 EFI/VFAT/NLS runtime closure regression contract')
