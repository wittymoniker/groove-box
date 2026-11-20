# R123 phase 7 — Flight B (UNVERIFIED candidate)

Status: UNVERIFIED. No GUI acceptance, no full ISO build, no boot test has passed for this tree yet.

## ISO builder
- Julia Pkg abort (`curl_multi_assign: 1` -> `uv__io_poll ... errno == 17`): Pkg now runs without the
  system-first LD_LIBRARY_PATH, so Julia uses its own libcurl. libstdc++ stays unified (CXXABI_1.3.15).
- Secure Boot (answer y): Secure Boot ISOs are built FIRST, unsigned copies after
  (GROOVEBOX_ALSO_UNSIGNED=0 skips them). Default mode `shim`: Microsoft-signed shim (2011 CA,
  fetched + hash-checked in the first minute) -> Groovebox-signed Limine with `.sbat` -> pinned
  kernel/initramfs. `GROOVEBOX_SECURE_BOOT_MODE=direct` keeps the old directly-signed Limine.
- First ISO (LIMINE-SCODE-v33c) is complete: FAT/VFAT + nls_ascii/cp437/utf8, Dell SOF audio,
  Realtek microSD, GUI recovery, Install to SSD. The final remaster reuses that stamped initramfs
  and the signed stage when nothing changed (faster builds).
- Signing tools auto-install as root (dnf/apt/pacman); `GROOVEBOX_SB_AUTO_INSTALL=0` disables.

## Application
- Unsigned source update (.zip/.tar.gz) with PIN, basic tests and similarity warnings.
- File Manager: double-click an archive to preview + Extract here.
- Monitor Center self-tests, console `signals`.
- Runtime defaults: one thread budget for every compute runtime; sOS sustained-throughput tuning
  (turbo, platform profile on AC, THP madvise, writeback, I/O schedulers). No overclocking beyond
  firmware limits. `GROOVEBOX_FLUX=0` disables the extras.
- Help text restored/updated; stale thread-budget tests realigned.

## First Secure Boot boot (Dell Latitude 3510 / Acer Nitro 5)
MokManager opens -> Enroll key from disk -> EFI/sOS/groovebox-mok.cer -> Continue -> Yes -> Reboot.
Dell alternative: BIOS > Secure Boot > Expert Key Management > Enable Custom Mode > db > Append from File.
