# Groovebox / sOS — 32 GB x86-64 tablet deployment

This bundle is intended for Intel/AMD x86-64 UEFI tablets and rugged convertibles with 32 GB RAM, including Dell Latitude Rugged-class systems and HIGOLEPC x86-64 tablets.

## Design rule

The build is hardware-neutral. It does **not** hard-code camera numbers, microphone/card indexes, touchscreen device paths, Wi-Fi interfaces, HDMI outputs, or vendor-specific input IDs. Groovebox device selectors and the Linux device stack discover those at runtime.

32 GB RAM requires no special binary build. The same x86-64 application and sOS image can use the additional memory naturally for project media, render buffers, sCode caches/pools and application working sets.

## Recommended deployment path

1. On the Fedora build machine, run `./BUILD_GROOVEBOX_APPLIANCE_ISO.sh` (or the game-ready builder inside `APPLIANCE_ISO`).
2. Write the completed x86-64 ISO to USB with `./BURN_GROOVEBOX_APPLIANCE_USB.sh`.
3. Boot the target tablet from the USB in UEFI mode.
4. **Before erasing its internal SSD**, run `./HARDWARE_PREFLIGHT_32GB.sh` from this bundle or copy it to the live environment.
5. Verify touch, keyboard/dock, Wi-Fi, Bluetooth, audio output, microphone, camera(s), HDMI/external display, USB, battery reporting and suspend/resume.
6. Open Groovebox and confirm the Camera/Microphone/Output selectors enumerate the devices you intend to use.
7. Only after those checks pass, use the included sOS installer to install to the internal SSD.

## Dell rugged notes

Dell Latitude Rugged x86-64 models generally expose conventional PC/UEFI hardware. Dock, serial, WWAN/GPS, rotation sensors, specialized buttons and unusual touch controllers remain model-specific and must be checked from the live USB.

## HIGOLEPC notes

Use only an Intel/AMD x86-64 HIGOLEPC configuration for this ISO. Do not use this x86-64 image on an ARM/Android tablet. Touch, Wi-Fi/Bluetooth, camera and sensor support depends on the exact components fitted by the manufacturer and must be checked from the live USB.

## Dynamics defaults retained

- Canonical Live Overblend default: 50% (net 50/50 user/canonical waveform blend).
- Intentional master Clip/Gain default: 50%.
- No new normalizer or limiter/compressor is introduced.
- Video Clip Studio color-to-sound and sound-to-color translation remain optional.

