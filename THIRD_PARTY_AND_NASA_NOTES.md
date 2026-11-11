# Third-party and NASA notes

## NASA

Groovebox contains **no NASA source code**. A search of the project's own source tree (Python, C/C++, Rust,
JavaScript and documentation) found no copied NASA code, headers or data files. Only two places mention NASA:

| File | What it is |
|---|---|
| `relativity_projection.py` | Original Groovebox code implementing textbook special-relativity formulas (Lorentz factor, Doppler and aberration-style projections). |
| `performance.py` (relativity panel credit line) | Shows the credit below inside the app. |

NASA open-source simulation projects were consulted only as **engineering references for simulation
architecture**: how to structure a deterministic, time-stepped simulation and keep a model separate from
how it is presented. Credit goes to:

* **Trick Simulation Environment**, NASA Johnson Space Center — https://github.com/nasa/trick
  (NASA Open Source Agreement).
* **core Flight System (cFS)**, NASA Goddard Space Flight Center — https://github.com/nasa/cFS
  (Apache License 2.0).
* **CML**: named in the app's credit line as part of the same reference material. The source does not record
  which project this abbreviation refers to; if you know, add its full name and link here.

Because none of their code is included, their licenses impose no terms on Groovebox. They are credited here
out of courtesy and accuracy.

Use of the NASA name is for attribution only. It does not imply NASA endorsement of Mathematician's
Groovebox.

## The author's own reference

`resources/Scientific_and_Mathematical_Theories_and_Inventions.pdf`: *Scientific and Mathematical Theories
and Inventions* by Noah Girouard King (Eski), the author of Groovebox. It includes the author's isosceles
trigonometry (isn / ics and their inverses, used throughout the seed language as `isn`, `ics`, `isx`, `isy`),
the author's fractal sets and other mathematical works the project draws on.

## Bundled components with their own licenses

* `sCode/LICENSE`: the sCode runtime.
* `BUILD_ISO/limine-v12.9.0/LICENSE`: the Limine bootloader used by the sOS ISO builder.
* Python packages (PyQt6, NumPy, SciPy and others) and FFmpeg are installed as dependencies at setup time,
  not copied into the source, and stay under their own licenses.
