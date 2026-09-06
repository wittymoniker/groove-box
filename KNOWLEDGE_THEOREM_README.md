# sCode 0.3 — Programmer Knowledge + Theorem-Aware Code Devising

This package extends the 0.2 bootstrap compiler with a local, editable programmer
knowledgebase and a theorem-aware candidate generator.

## What works now
- `scodec know QUERY` searches the bundled knowledgebase.
- `scodec devise affine` uses the tested Finite-Infinity affine exact-jump utility.
- `scodec devise modular` uses exact modular periodicity.
- `scodec devise transition` uses finite deterministic orbit decomposition.
- `scodec devise meum` emits a Meum/logic-math optimization *candidate* that
  explicitly requires equivalence verification/benchmarking.
- Generated snippets are valid declarative sCode and compile to deterministic sIR.
- `examples/DeviseCode.scode` demonstrates the intended compact authoring model.

## What is intentionally not claimed yet
The current parser/compiler does not yet execute arbitrary `solve`/`devise`
blocks as a complete programming language runtime. These constructs are valid
semantic declarations today. The next sTheorem/sGraph compiler pass will lower
them into executable verified CPU/SIMD/GPU implementations.

The knowledgebase is broad and extensible, but no finite bundled database can
truthfully contain all programmer knowledge. sAssistant should combine it with
versioned language docs, project retrieval and user-approved external sources.
