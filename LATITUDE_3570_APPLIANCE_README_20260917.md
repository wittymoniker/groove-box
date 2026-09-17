# Dell Latitude 3570 / 3560 appliance build — 2026-09-17

This Groovebox release uses the same x86-64 sOS image for Dell Latitude 3560 and 3570 and for 8 GiB or 16 GiB RAM. The appliance detects memory at boot; it does not bake the RAM amount into the ISO.

## Long video renders

For renders over 2,000,000 audio samples, Groovebox switches to bounded-block DSP. The video renderer already sends RGB frames directly to FFmpeg; this release also removes the old 30-minute ceiling, avoids a full float64 render-time grid, block-processes DomainEQ/seed/EQR/Meum work, uses overlap-add for long Global Convolve, and streams temporary WAV conversion instead of allocating a full second PCM copy. Render duration is therefore primarily a CPU/disk-time question rather than a frame-retention RAM question.

16 GiB is the preferred appliance configuration for long video/export work. 8 GiB remains supported and receives a smaller DSP block size plus best-effort zram. High sample rates, many bound media layers, very large imported carriers, and high video resolutions still increase memory, CPU and disk requirements.

## Building the appliance ISO on Fedora

Keep `groovebox/` and the separately distributed `APPLIANCE_ISO/` folder beside each other (or put `APPLIANCE_ISO/` inside `groovebox/`). Then:

```bash
cd groovebox
sudo ./BUILD_GROOVEBOX_APPLIANCE_ISO.sh
```

The dedicated ISO-side entry point is:

```bash
cd APPLIANCE_ISO
sudo ./BUILD_LATITUDE_35X0_ISO.sh
```

Do not use `--no-fetch` for the laptop you intend to boot. The hardware-ready path installs the complete game-ready rootfs and now hard-fails if `vmlinuz` does not match `/usr/lib/modules`, if essential i915/AHCI/xHCI/HDA modules are absent, if the firmware tree is empty, or if the Python/Qt/audio runtime cannot import.

The GRUB **Install** entry now enters an actual installer menu. It never chooses a disk automatically; the installer shows whole disks, asks for a `/dev/...` target, and then requires the exact `ERASE /dev/...` confirmation before repartitioning.

## Latitude boot setup

UEFI is preferred. The image retains both UEFI and legacy BIOS installation paths. AHCI is the intended SATA mode. Use F12 for the one-time boot menu. First boot from USB in Live mode before installing, verify display/audio/keyboard/touchpad/network, then use the Install entry.

A software build can validate the kernel/module/runtime contract, but the final hardware certification is the real USB boot on the specific Latitude, because Wi-Fi card and firmware options can vary by configuration.
