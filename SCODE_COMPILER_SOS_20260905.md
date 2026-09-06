# sCode compiler for sOS

The canonical compiler command is `scodec`.

Commands:
- `scodec check File.scode`
- `scodec compile File.scode`
- `scodec compile File.scode -o File.sir`
- `scodec inspect File.scode`
- `scodec hash File.scode`

sOS installation layout:
- `/usr/bin/scodec`
- `/usr/lib/scode/`
- `/etc/scode/language_pack.json`
- `/opt/groovebox/Groovebox.scode`
- `/opt/groovebox/Groovebox.sir`

The compiler emits deterministic JSON sIR and a semantic SHA-256.

This is the bootstrap/reference compiler, implemented in Python so it can run on
the current sOS base and development machines. A later self-hosted sCode compiler
can replace it only after parity tests prove that it accepts/emits the same semantics.
