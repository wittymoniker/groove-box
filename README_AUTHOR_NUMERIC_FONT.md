# Author Numeric Font / Number Codec v4

Groovebox now separates **number meaning** from **Qt drawing**.

`author_number_codec.py` is the Qt-free reversible spelling layer. `author_numeric_font.py` is the cached code-defined glyph atlas that displays those packets inside numeric fields. No `.ttf`/`.otf` file is required.

## Current number grammar

- ordinary base cells: `0..15` (base 16)
- special semantic cell: `16` = one completed/full cycle
- an in-cell squiggle can carry the first fractional `2^-1 = 1/2`
- additional fractional slot `k`: `16^-k = 2^(-4k)`
- **spaced** straight/count in a fractional slot = `1/1` of the slot
- **unspaced** straight/count in that same slot = `1/2` of the slot
- automatic numeric conversion uses spaced/full fractional cells
- exact integers use no fractional cells
- only enough fractional cells are emitted to preserve the field's visible precision
- the real numeric/project value is never replaced by the display spelling

Examples: `1.5` fits in a squiggled `1` cell; `1.25` is `1` plus a spaced value-4 `2^-4` cell. At slot 1, value 4 spaced is `0.25`, while value 4 unspaced is `0.125`.

## Caching / sCode acceleration

The semantic library precomputes all 68 `(0..16) × squiggle/no-squiggle × spaced/unspaced` faces. Numeric fields dirty-gate their source values, so an unchanged field never re-enters the formatter. The required sCode ABI-5 optimizer chooses the symbol pool/cache identity. Immutable spellings and individual Qt glyph faces are reused across every field showing the same state.

Project save/load and export provenance identify this scheme as `base16-squiggle-subscale-v4`. Scripts can use `author_symbol_spell`, `author_symbol_decode`, and `author_symbol_fraction` so they share the same codec instead of implementing a separate conversion.

## Per-field authored rewriting

`AuthorNumericFieldAdapter.rewrite(text)` asks the automatic codec for a new packet without changing the field value. `rewriteSpelling(packet)` applies an explicit immutable packet, and `setFractionSpacing(slot, True/False)` switches an existing fractional slot between spaced `1/1` and unspaced `1/2` semantics for that field only.
