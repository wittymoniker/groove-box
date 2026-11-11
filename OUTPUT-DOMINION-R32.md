# Output dominion — R32.8

**Goal:** from any A to any B, in every format the system handles. The seed program is the complete description.

## The minimal structure

One hub and one rule:

```
          reverse-engineer                     canonical engine
  any A  ───────────────▶  SEED PROGRAM  ───────────────▶  any B
  (sound · image · video · midi · text · data · game · project)
```

* **Seed → B (forward): exact.** The seed renders through the same canonical engine as Play / Export:
  * sound: the shared mixdown;
  * video and image: the VideoSynthEngine plus the video plan;
  * everything else: the canonical sound, then the converters.
  * The same seed gives the same bytes every time. This is the *seed is the perfect goal* direction.
* **A → seed (reverse): a structural estimate, not a byte-exact inverse.** The Transmuter measures A and writes a seed program that reproduces its gesture:
  * what it measures: tempo, base pitch, brightness, onset density and a Fourier energy envelope;
  * what it can't do: no finite seed reproduces an arbitrary recording sample for sample.
  * When B must contain A *exactly*, use the direct converters or the editors below, not the hub.
* **Exactness where it is possible.** The difference tool saves A − B as media. The sound difference is exact: B + (A − B) gives back A bit for bit (32-bit float WAV). This makes "what does this edit / engine / seed change contribute" a file you can play, view or convert further.

## The toolkit (A → B via editors)

| Kind    | Edited in                        | Converts directly to |
|---------|----------------------------------|----------------------|
| sound   | Clip Editor · Wave tools · Post  | image · video · midi · text · data · seed · project · game |
| image   | Image Editor                     | sound · video · midi · seed |
| video   | Clip Editor                      | sound · image · seed |
| midi    | (system MIDI editor)             | sound → everything |
| text    | (system text editor)             | sound · midi → everything |
| data    | (system / spreadsheet)           | sound · midi · image → everything |
| game    | Game Editor                      | seed |
| project | the main window                  | seed · and through it everything |
| seed    | the seed field                   | sound · video · image · project → everything |

Any pair without a direct converter goes through sound or the seed. In the Transmuter, "Open result in editor" sends the result to its editor, and "Difference A − B" works on any two inputs.

## What is not claimed

* There is no lossless round trip through a seed for arbitrary recordings (see the reverse direction above).
* MIDI, text and data have no built-in editor; they open in the system's default application.
* 3D (OBJ) files are a Clip Editor layer, not yet a Transmuter kind.
