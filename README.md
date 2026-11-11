# Mathematician's Groovebox


A deterministic generative music, visual, and game engine driven by mathematical seeds.

## What is proven

The full mathematics, with equations, and the case for why the design is scientifically sound (and where it is
only one arbitrary, rather complex choice among many) is in **[MATHEMATICS.md](MATHEMATICS.md)**.

| Claim | Result (offscreen app, real code paths) |
|---|---|
| Determinism | Same seed → bit-identical audio **and** video frames, in one process and across processes |
| Any kind → any kind | **81 / 81** pairs: sound, image, video, MIDI, text, data, seed, project, game |
| Symbolic completeness | Every finite note sequence is exactly a seed program: 200 / 200 melodies, 0.0 Hz error. MIDI → seed is lossless |
| Save → load | 303 / 312 changed controls restored exactly (the rest are excluded on purpose or recomputed) |
| Engine sync | Every engine's saved state survives snapshot → apply → snapshot, with defaults and with every engine on |
| Clean measurement | Two renders with the engines off differ by 0.000000 (audio) and 0.000 (video), so an engine's effect is measurable on its own |
| Engines together | SEEDED, EUCLIDEAN and LOCK compose on modulation (19 / 19 checks); couplings do nothing unless both engines are on |
| Every stage reaches exports | Local FX, Layer EQ and Mod Osc act on the export mixdown and undo exactly; Global FX acts at the master stage (12 / 12 checks) |
| Project ⇄ OBJ | A song exported as OBJ opens as a normal mesh and gives back the bit-exact audio and the project; any other OBJ imports as sound (12 / 12 checks) |
| Video meshes | Meshes built from each frame's audio are drawn on every frame and are deterministic; a loaded OBJ is drawn large in the centre with an outline; GOAVA shapes show with the GOAVA sound engine off |
| Project load | 0.3–0.8 s with no UI stall over 0.6 s afterwards (was ~2 s plus a 2.4 s stall), and the loaded project renders sample-for-sample the same |
| Signed updates | Ed25519 equals the RFC 8032 test vector; a tampered package is refused |

**Not claimed:** that every recorded sound has a short seed (audio → seed is a structural estimate), or that a measured
difference means better music.

### Guidelines
1. Decide with the seed and edit structure on canonical lanes; keep artistic edits on user lanes. The defaults are neutral, so only structural enhancement is heard.
2. RAND makes reproducible seed children by default. Right-click RAND → **Pure** when you want unrepeatable randomness; the captured value is still saved, so the project replays.
3. To compare two versions, export both and save A − B. Silence or grey means identical.
4. On small machines set the RAM budget (Monitor panel). The tiers keep exports serial and video chunks small.
5. Games keep one savestate each per Groovebox. Delete one or all from the Game Editor.
6. To record onto a USB stick or SD card, pick it under **Save to:** (Export, Batch or Live Player) *before* recording. Press ↻ after plugging in; an unmounted stick shows as "⚠ … not mounted (click to mount)", and **📂 Choose a folder…** reaches any other location. Press ⏏ Flush before unplugging.
7. Quick Rack ▸ 🧊 OBJ exports the whole song as a 3D model (with the exact audio and project inside) and imports any OBJ as sound. "Show an OBJ in the video" puts a model in the centre of every frame.

## 1. Run it and get sound

You do **not** need to understand the math to use Groovebox.

## Build Groovebox yourself

If you do not want to build from source, use a prebuilt release for Windows, Linux, or macOS.

If you **do** want to create a build yourself, the main build script is:

```text
BUILD_KIT/build.py
```

You normally do not need to run the individual internal build scripts manually.

### Linux

Open a terminal in the Groovebox project folder.

First install the required Linux dependencies:

```bash
chmod +x BUILD_KIT/install_dependencies_linux.sh
./BUILD_KIT/install_dependencies_linux.sh
```

Then run the builder:

```bash
cd BUILD_KIT
python3 build.py
```

When the script finishes, check the build/output directory reported by the script for the finished package.

### macOS

Open Terminal in the Groovebox project folder.

Install the required macOS dependencies:

```bash
chmod +x BUILD_KIT/install_dependencies_macos.sh
./BUILD_KIT/install_dependencies_macos.sh
```

Then run:

```bash
cd BUILD_KIT
python3 build.py
```

The builder will print the location of the generated build when it completes.

### Windows

Install Python if it is not already available, then open **PowerShell** or **Command Prompt** in the Groovebox project folder.

Run:

```powershell
cd BUILD_KIT
py build.py
```

If your installation uses `python` instead of the Windows `py` launcher:

```powershell
python build.py
```

The builder will print where it placed the completed Windows build.

### If the build fails

The build kit also includes:

```text
BUILD_KIT/BUILD_DIAGNOSTIC.sh
```

On Linux/macOS, you can run the diagnostic with:

```bash
chmod +x BUILD_KIT/BUILD_DIAGNOSTIC.sh
./BUILD_KIT/BUILD_DIAGNOSTIC.sh
```

When reporting a build problem, include:

```text
Operating system:
Groovebox version:
Command you ran:
Last part of the terminal output:
```

### sOS / native sCode build

The sOS/sCode project has its own native build process.

Build it with:

```bash
./build/build_native.sh
```

Then run its test suite:

```bash
./tests/run_all.sh
```

For the optional static native build:

```bash
SOS_STATIC=1 ./build/build_native.sh
```

To generate the native `.sapp` package repository:

```bash
./scripts/build_sapp_repo.sh
```

Packages are written to:

```text
build/sapp-repo-native/
```

To create the source release archives:

```bash
./scripts/make_source_release.sh
```

These sOS scripts are separate from the normal Windows/Linux/macOS Groovebox application builder.

---

### Short version

For most developers:

```bash
cd BUILD_KIT
python3 build.py
```

For Windows:

```powershell
cd BUILD_KIT
py build.py
```

### Make sound

1. Launch **Mathematician's Groovebox**.
2. Make sure your speakers or headphones are on.
3. Click **Randomize Everything** to create a starting patch and sequence.
4. Click **Play Audio Track**.
5. Use **Master Volume** to set the level.
6. Click **Stop** when you are finished.

That is enough to hear the program.

For the full audiovisual output, use **Play Audiovisual Track** instead.

---

## Generative scope (fractal coverage)

Groovebox is a deterministic generative fractal inside its own mathematical dialect (five canonicals + Morph Bridge + sidechain + EQ + shared renderer). It produces a large, organized, non-redundant family of music, visuals, and game states from numeric seeds.

It does **not** claim to cover every possible sound, music video, or interactive experience. See `FRACTAL_COVERAGE_AND_BOUNDARY.md` for the precise boundary.

## Help and project files

The in-app feature guide is `ReadmeGuideDialog.HELP_TEXT` in `groovebox.py`, mirrored in [the full help text](HELP_TEXT.md).
`BUILD_ISO` and `BUILD_KIT` share a root runtime-module inventory: run `bash BUILD_ISO/sync_overlay_from_root.sh` after source edits
and `bash RUN_ME_ZERO_STATE.sh --check` for the non-installing preflight. Release history is in the `RELEASE-*` files.
The author's book, *Scientific and Mathematical Theories and Inventions* (source of `isn` / `ics` and the fractal sets), is in
[`resources/`](resources/). Credits, including NASA simulation projects consulted as references (no NASA code is included), are in
[THIRD_PARTY_AND_NASA_NOTES.md](THIRD_PARTY_AND_NASA_NOTES.md).

## What is Mathematician's Groovebox?

Groovebox is an experimental desktop instrument where numbers and equations can control:

- notes and rhythm
- synthesis and automation
- audiovisual graphics
- imported audio and video
- deterministic procedural scenes and game worlds

A seed is not just a random-number label. It can act as a reproducible input to the composition system.

The same seed and the same settings are intended to produce the same result.

You can use Groovebox as a normal experimental sequencer without writing equations.

---

## 60-second workflow

A useful first session is:

1. Enter any number in the **Seed** field.
2. Click **Randomize Everything**.
3. Click **Play Audio Track**.
4. Change the seed and listen again.
5. Open **Edit Synth** to modify the selected instrument.
6. Open **Calc Domain**, **Write Script**, or **Patch Modular** when you want deeper control.
7. Use **Play Audiovisual Track** to add the visual engine.
8. Save the project when you find something you want to keep.
9. Export the result as audio or video.

Try seeds such as:

```text
1.1975807343
1.618033
2.71828
3.14159
134964356
```

---

## Main controls

### Transport

- **Play Audio Track** — play the composition without the visual renderer.
- **Play Audiovisual Track** — play audio and generated visuals together.
- **Play Video Game** — enter the generated interactive world.
- **Stop** — stop playback or rendering.

### Generating material

- **Seed** — the main deterministic input.
- **Randomize Everything** — generate a complete starting state.
- **Randomize Sequence** — regenerate sequence material.
- **Trigger All** — trigger the current instruments.
- **Global Track Offset** — move the track timing in beats.

### Editing

- **Edit Synth** — synthesis controls for the selected instrument.
- **Calc Domain** — mathematical/domain controls.
- **Write Script** — script-driven behavior.
- **Patch Modular** — modular routing and patching.

You do not need to use all four editors to make music.

---

## Four canonical engines

The current public canonical row is:

**SEEDED · RAND · LOCK ·EUCKLIDEAN · GOAVA**

Each is an independent toggle and each has its own contribution level in the bottom **Canonical Morph Bridge**. RAND captures fresh operating-system entropy when you activate it, then stores that random instance with the project so playback and exports can reproduce it. LOCK also provides Coupling, Timing Pull, Pitch/Detune Link, Velocity Link, and Phase Spread controls.

The default LOCK character is tuned to **62% / 50% / 62% / 65% / 20%** respectively.

Euclidean Rhythm Assist remains available as a rhythm helper; it is not a fifth canonical engine.

---

## Draw / Record 3D Voxel Kit

The shared Draw/Record media workspace also includes a **3D Voxel Kit**. You can draw or erase voxels on selectable Z slices, voxelize a video frame, import supported 3D model files, and control the overall crisp-to-smooth appearance with **Overall Alias**.

Supported 3D input includes OBJ, PLY, STL, glTF, and GLB references. Authored voxel geometry can be exported as OBJ or PLY, and the same project-owned voxel scene participates in audiovisual/video rendering.

Voxel geometry, model reference, grid size, Overall Alias, canonical levels, and LOCK settings are stored with the project and carried into render provenance.

---

## Sequences and scripts

Groovebox supports ordinary sequencing as well as mathematical and scripted control.

Scripts can work with time-varying values such as:

```text
x(t)
y(t)
r(t)
theta(t)
```

These values may be used to drive compatible musical, visual, and procedural parameters.

In seed scripting, `t` is treated as a musical progression value tied to the arrangement rather than simply being a wall-clock animation timer.

Start with numbers and normal sequencing first. Scripts are an advanced feature.

---

## Audio, samples, and video

Groovebox can combine generated material with imported media.

Depending on the selected controls, you can:

- load a sample for one instrument
- load a global sample
- adjust instrument tuning and volume
- record or import audio/video
- draw media layers
- mix instrument and carrier video
- apply compatible transformations to generated and imported visual material

The project system is designed to keep project media and settings together.

---

## Export

Use the **Export** controls to render the current project.

Supported project workflows include:

- WAV audio
- MP3 audio
- MP4 audiovisual output
- multipart exports

Available audio export rates include conventional rates as well as high-rate options such as **96 kHz** and **128 kHz** where supported by the selected export path.

For reproducibility, exports reset phase state rather than depending on whatever happened to be playing immediately beforehand.

---

## Determinism

Groovebox is built around repeatability.

In practical terms:

```text
same seed
+ same project settings
+ same engine state
= same intended composition
```

Live playback can preserve phase continuity while you perform. Export uses a clean phase start so that a render can be reproduced.

That deterministic behavior is one of the main reasons the project uses mathematical seeds.

---

## About the math

The program contains experimental mathematical systems, including Meum-related calculations, operator transforms, Euclidean timing, parametric functions, and other deterministic mappings.

You do **not** need to understand these systems to use Groovebox.

For example, one Meum relationship used by the project can be written plainly as:

```text
2^M - M^4 - M^2 + M = 0
```

with the project's working Meum value near:

```text
M = 1.1975807343...
```

The README does not attempt to document the full mathematics; it lives in [MATHEMATICS.md](MATHEMATICS.md), so musicians can learn the instrument without first reading a research document.

---

## Build Groovebox yourself

Prebuilt releases are recommended for musicians and testers. Developers can build the application with the included **BUILD_KIT**.

### Linux

```bash
chmod +x BUILD_KIT/install_dependencies_linux.sh
./BUILD_KIT/install_dependencies_linux.sh
cd BUILD_KIT
python3 build.py
```

### macOS

```bash
chmod +x BUILD_KIT/install_dependencies_macos.sh
./BUILD_KIT/install_dependencies_macos.sh
cd BUILD_KIT
python3 build.py
```

### Windows

From PowerShell or Command Prompt in the project folder:

```powershell
cd BUILD_KIT
py build.py
```

If your Python installation uses `python` instead of the Windows `py` launcher:

```powershell
python build.py
```

The builder prints the generated output location when it completes. On Linux/macOS you can also run `BUILD_KIT/BUILD_DIAGNOSTIC.sh` if the build environment needs checking.

### sOS / sCode native build

```bash
./sCode/build/build_native.sh
./sCode/tests/run_all.sh
```

The sOS/sCode native build is separate from the normal Windows/Linux/macOS Groovebox application builder.

---

## Running from source

Release builds are recommended for musicians and testers.

If you want to work on the source code instead, the Python implementation uses components including:

- Python 3
- Qt / PyQt
- NumPy
- SciPy
- sounddevice
- soundfile
- FFmpeg / ffprobe

From a configured source tree, the basic development launch is:

```bash
python3 groovebox.py
```

On systems where Python is invoked as `python`:

```bash
python groovebox.py
```

Groovebox distributions may include local runtime dependencies and launch scripts so that end users do not have to configure the development environment manually.

---

## No sound?

Try these in order:

1. Confirm that **Master Volume** is above zero.
2. Click **Randomize Everything** and then **Play Audio Track**.
3. Confirm that your operating system is sending Groovebox to the expected audio device.
4. Close another application if it has exclusive control of that device.
5. Stop Groovebox and relaunch it after changing audio hardware.
6. If you are running from source, confirm that the audio dependencies are installed correctly.

When reporting an audio problem, include your operating system, audio device, how you launched Groovebox, and the console error if one appeared.

---

## Who is this for?

Groovebox may be interesting if you enjoy:

- synthesizers and sequencers
- generative or algorithmic music
- creative coding
- mathematical composition
- audiovisual performance
- procedural generation
- experimental game/audio systems

Musicians are welcome even if they have no programming or mathematics background.

---

## Feedback

Bug reports and practical usability feedback are especially useful.

If something prevents you from getting sound, opening a project, saving, exporting, or understanding the interface, please report that first. Those problems are more important than understanding the internal mathematics.

When reporting a bug, include:

```text
Operating system:
Groovebox version/build:
What you clicked:
What you expected:
What happened:
Console/error text:
```

Small reproducible reports are much easier to fix than broad descriptions.

---

## Project philosophy

The short version:

**Make something interesting from a number, hear it immediately, and be able to reproduce it later.**

The deeper mathematical, scripting, rendering, networking, and engine documentation is preserved in `docs/TECHNICAL_REFERENCE_20260909.md` rather than sitting between a new user and the Play button.

## Rust support

Groovebox ships Rust source for its optional native accelerator and the BUILD_ISO bounded-memory newc streamer. The release archive does not bundle the Rust compiler: the normal Linux/macOS/Windows dependency and launch scripts provision the stable rustup/Cargo toolchain and platform linker when needed. `GROOVEBOX_NATIVE_BACKEND=rust` selects the Rust C-ABI accelerator, `cpp` selects C++, and `auto` keeps the established native/fallback behavior. BUILD_ISO prebuilds the Rust accelerator and embeds it in `/opt/groovebox/native/`.


## Cross-platform support and deployment

### Supported launch paths

Use the launcher shipped with this source tree; do not run a Linux ELF bootstrap on another operating system.

| Environment | Preferred entry point | Notes |
|---|---|---|
| Windows 10/11 x64 | `LAUNCH_GROOVEBOX_WINDOWS.bat` | Uses the Windows dependency installer and Python launcher when available. Keep the project in a user-writable folder. |
| macOS Intel / Apple silicon | `LAUNCH_GROOVEBOX_MACOS.command` | Uses the host Python/runtime; native sCode bootstrap availability depends on the matching packaged build. |
| Fedora / other Linux desktop | `LAUNCH_GROOVEBOX_LINUX.sh` or `run_hybrid.sh` | Fedora RPM PyQt6 and PipeWire/WirePlumber can differ from pip-installed Qt; avoid mixing Qt stacks in one environment. |
| Groovebox appliance ISO / sOS | `BUILD_GROOVEBOX_APPLIANCE_ISO.sh` and the versioned `BUILD_ISO/` instructions | Build success, boot success, and media success are separate validation gates. |
| Android/mobile helpers | `launch_mobile.sh` | This is a helper path, not a claim of full desktop-feature parity on every phone/tablet. |

**Architecture boundary:** packaged bootstrap binaries and ISO artifacts are architecture-specific. A launcher existing in the source tree does not prove that every CPU architecture or OS release has a tested binary. Windows/macOS/Linux releases need native CI or physical-device testing before being described as fully certified.

### Audio and video startup

- Groovebox's real-time instrument playback uses the `sounddevice` / PortAudio path; media-player features use Qt Multimedia and the platform's media plugins/codecs. These are distinct runtime paths.
- At startup, device discovery can lag behind desktop login, especially with Fedora + PipeWire/WirePlumber. The media bootstrap schedules a bounded, non-blocking probe and logs findings to `~/.local/state/groovebox/media-bootstrap.log` on Unix-like systems (Windows log paths depend on the user's environment and launcher).
- A detected device is not proof that it opened successfully or produced sound. Test playback at a safe volume and select an explicit endpoint if the OS default is not the intended device. Current routing should not be described as synchronized playback to every output unless a true fan-out implementation is present.
- Video playback requires `PyQt6.QtMultimedia`, a working Qt multimedia backend and supported codecs. `PyQt6.QtWebEngineWidgets` is optional and is not the video-player backend.
- For a diagnostic report, run `python scripts/diagnose_platform.py`; to save a report, run `python scripts/diagnose_platform.py --json groovebox-platform-report.json`. The script is read-only and does not install packages or change audio routing.

### Laptop portability checklist

Use this checklist for Dell Latitude, Acer Nitro, and other laptops; avoid hard-coding a specific sound-card number, GPU, camera path, or output name.

1. Confirm the laptop's OS, CPU architecture, desktop session, and Python executable.
2. Run the platform diagnostic and check that `PyQt6.QtMultimedia` and `sounddevice` import in the same interpreter used by the launcher.
3. On Linux, inspect PipeWire/WirePlumber (`wpctl status`), PulseAudio compatibility (`pactl list short sinks`), and ALSA (`aplay -l`) where those tools exist. Prefer the user's desktop default first; treat direct ALSA hardware endpoints as fallback diagnostics, not universal defaults.
4. Check built-in speakers, headphone jack, HDMI/USB audio, Bluetooth, internal microphone, USB microphone, camera, and external display separately when available. Devices may appear/disappear while docking or reconnecting.
5. Keep audio discovery off the real-time audio callback and off the GUI's blocking startup path. Re-scan only through a bounded asynchronous operation and surface errors instead of silently swallowing them.
6. Validate an ISO in stages: builder/verifier tests; ISO file integrity; boot in a VM; boot on physical hardware; then test audio/video after login. A successful build or VM boot does not establish physical audio/video compatibility.

### ISO builder preflight and release discipline

Before publishing an ISO, run the project's documented verifier(s) from `BUILD_ISO/`, confirm the root source and `app-overlay-v35.22zz/` copies of any overlay-managed runtime files match, then check the generated ISO's checksum. Test the ISO against the actual target boot mode (UEFI/Legacy as supported), graphics mode, network, storage, and media devices. Do not copy host-specific device names or runtime logs into the release.

The current sOS builder is explicitly **x86_64**: it verifies the Linux 64-bit boot-protocol header, the PE32+ `EFI/BOOT/BOOTX64.EFI` inside Limine's FAT image, the UEFI El Torito entry, and the hybrid MBR type-0xEF partition. Secure Boot must be disabled unless the EFI loader is separately signed and enrolled. See `BUILD_ISO/README.txt` for the exact checks and remaining hardware-validation gates.

### Reporting a cross-platform defect

Attach the diagnostic JSON plus the latest session log. Include OS/version, CPU architecture, exact launcher (`run_hybrid.sh`, Windows BAT, macOS command, or ISO), whether the main window appeared, whether the player window appeared, selected output, and whether export-to-WAV works when live playback does not. Remove personal paths or device names before sharing if desired.


## Media diagnostics and install checks

The diagnostics below are for systems where the main Groovebox window launches but audio is silent or the video/player window does not appear. It does not claim that every operating system or laptop model has been physically certified.

### Diagnose before changing settings

Run with the same Python interpreter used by the launcher:

```bash
python scripts/diagnose_platform.py --json groovebox-platform-report.json
```

The report checks core imports, PortAudio device enumeration, Qt Multimedia audio/camera endpoint enumeration, and operating-system-specific service/tool diagnostics. It is read-only: it does not install packages, change the default output, or start playback. Review the report for missing modules and service errors before reinstalling anything. On Linux, `wpctl status`, `pactl list short sinks`, and `aplay -l` are useful independent checks when installed.

### Media readiness is separate from core startup

A successful main-window launch does not prove that the video backend initialized or that an audio stream opened. The Windows installer checks Qt Multimedia separately from core dependencies and warns if the player dependency is unavailable. On Fedora, use the distro-matched PyQt6/Qt packages; do not mix RPM Qt libraries with pip Qt wheels. On macOS and other Linux distributions, confirm that Qt Multimedia plugins and codecs are installed for the same Python environment that launches Groovebox.

### Default audio and output selection

Groovebox should begin with the operating-system-selected default output where available. Device enumeration is not proof of successful playback. A single selected output and synchronized multi-output fan-out are different capabilities: Groovebox does not claim simultaneous playback to every physical endpoint unless the active audio backend actually opens and feeds each endpoint. Use the operating-system default first, then select a named output when necessary. Keep volume low for the first test.

### Release gate

Before calling a build complete, run the targeted Python contract tests, the full documented `BUILD_ISO/` verifier chain, archive integrity/checksum checks, and a booted ISO smoke test. Then test the Windows launcher on Windows, macOS launcher on macOS, and the Fedora/Linux launcher on target hardware. A source-level check cannot substitute for a physical sound/video test.

## Fedora: audio devices not appearing

If `run_hybrid.sh` opens Groovebox but audio/video device lists are empty, rerun `./run_hybrid.sh` after installing updates so the Linux installer can provision ALSA, PortAudio, PipeWire/WirePlumber, Qt Multimedia, and GStreamer components. Then run:

```bash
python3 scripts/diagnose_platform.py --json groovebox-platform-report.json
```

Check the `audio.enumeration_error`, `audio.host_apis`, `commands.pipewire_service`, `commands.wireplumber_service`, and `commands.pulse_server` fields. The runtime log is `~/.local/state/groovebox/media-bootstrap.log`. A device name in a diagnostic report means the OS/backend enumerated it, not that a stream has successfully opened. If both Qt and PortAudio report zero devices, confirm the laptop's kernel audio driver and user-session audio service before changing Groovebox's selected output.
