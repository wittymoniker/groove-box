# Seed Script Syntax Highlighting — 2026-09-08

The Global Seed / Parametric Script QTextEdit now uses a QSyntaxHighlighter-based visual layer.

- Control/code words such as `if`, `elif`, `else`, `while`, `for`, `def`, and `return` use the lightest neutral grey.
- Supported math/seed names such as `sin`, `cos`, `MEUM`, `polar`, `isn`, and `ics` use a slightly darker grey.
- User variables/identifiers, numeric literals, strings, operators, and comments step progressively darker.
- `()`, `[]`, and `{}` are shaded by nesting depth from light to dark grey; obvious unmatched closing brackets are underlined.
- Highlighting is lexical/visual only. It never evaluates the seed, never modifies project state, and therefore does not affect deterministic composition or audio/video/game output.
- The highlighter operates per QTextDocument block through Qt's native syntax-highlighting mechanism to keep typing overhead small.

Note: syntax highlighting identifies code structure; the Seed evaluator's supported language remains the authority on whether a particular full script can execute.
