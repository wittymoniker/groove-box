# Groovebox R28.4.50 HF4 — Boot stability + deploy bundle

This revision keeps the HF3 zero-state entrypoints and existing CRC32C installer closure, and sets the default/live/install/sCode/installed-disk boot command lines to legacy Intel HDA (`snd_intel_dspcfg.dsp_driver=1`) to avoid the Dell Intel SOF IPC `-22` / `HW params ipc failed` loop shown in the supplied photograph. The SOF runtime fallback code remains available but is no longer selected by default boot entries.

The installer CRC32C fix remains in the source: `bundle_crc32c_modules_v35_22zq.py`, `verify_crc32c_install_v35_22zq.py`, and the `v35.22zq+` final initramfs stamping path.

The companion `wasmer_tabletime_deploy/` tree is based on the supplied Tabletime v35.22zt Wasmer repository. It requires authentication before home/post browsing; `/posts.php` is only a redirect to the protected `/post.php`; public landing, login, and registration remain reachable so users can sign in.

Validation performed in this package: source/static boot-contract checks, CRC32C source verifier, Python compilation and shell syntax checks, Tabletime PHP lint where PHP is available, Tabletime access-guard static test, ZIP integrity and SHA-256. This does not claim a fresh ISO was produced or physical Dell boot/SSD installation was tested. Build the ISO on the supported Linux build host using `bash RUN_ME_ZERO_STATE.sh`, then boot-test the ISO before replacing any known-good image.
