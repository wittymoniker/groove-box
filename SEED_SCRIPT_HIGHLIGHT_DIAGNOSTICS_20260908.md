# Seed Script highlighting + diagnostics — 2026-09-08

- Added native `QSyntaxHighlighter` grey-scale syntax shading for Seed Script keywords, variables, builtins, literals, operators, comments/strings, and nested brackets.
- Added a debounced (180 ms), static AST/name diagnostic pass. It never evaluates the Seed Script and therefore never recomposes while typing.
- Unknown loaded identifiers, including assignments such as `voice = MyPreset`, are reported as `unknown variable/preset` and the offending token is highlighted in the editor.
- Confident Python-style syntax errors are highlighted/reported with line information.
- Groovebox coordinate DSL and supported shorthand are handled specially to avoid false-positive Python syntax errors.
- Added a persistent bottom-of-Seed-panel error readout using Groovebox's existing `#ff5555` error treatment; it hides automatically when the script is clean.
- Diagnostics are non-modal and wrapped in a fail-safe so UI feedback cannot become a playback/crash source.
