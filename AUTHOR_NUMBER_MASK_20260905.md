# Author Number Mask — 2026-09-05

Groovebox Math Symbols now follows the supplied four-quadrant handwritten format.

- outer square: stable glyph cell
- dotted vertical/horizontal cross: quadrant/reference axes
- center ring: origin/reference point
- UL, UR, LL, LR: four base-16 nibble bits
- each active quadrant contains three contextual strokes
- UL/UR/LL strokes are vertical; LR strokes are horizontal, matching the supplied drawing
- straight/squiggly remains contextual metadata and does not change the decoded nibble
- Math Symbols ON masks standard QSpinBox/QDoubleSpinBox numeric controls at rest
- focus a numeric control to reveal/edit its ordinary numeric text; the author mask returns on focus-out
- Math Symbols OFF reveals ordinary numeric values globally for inspectability

The numeric engine values are unchanged by this display layer.
