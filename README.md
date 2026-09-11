# Mathematician's Groovebox

<img width="1920" height="1080" alt="Screenshot_20260911_103102" src="https://github.com/user-attachments/assets/06fdd747-b0a8-4249-9d2c-23b65646e8a2" />


A deterministic generative music, visual, and game engine driven by mathematical seeds.

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

**SEEDED · RAND · LOCK · GOAVA**

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

The README intentionally does not attempt to document the full mathematics.

Technical mathematical documentation should live separately so musicians can learn the instrument without first reading a research document.

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
<img width="1920" height="1080" alt="Screenshot_20260911_103158" src="https://github.com/user-attachments/assets/3303c813-bb61-40a7-a250-bd5516f38b5f" />

## Project philosophy

The short version:

**Make something interesting from a number, hear it immediately, and be able to reproduce it later.**

The deeper mathematical, scripting, rendering, networking, and engine documentation is preserved in `docs/TECHNICAL_REFERENCE_20260909.md` rather than sitting between a new user and the Play button.
