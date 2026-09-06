# Distribution audit

This tree is the cleaned full-source distribution of the current Groovebox build.

Included:
- current `groovebox.py`
- active helper/runtime modules and tests
- known-good `BUILD_KIT/build.py` lineage plus root wrapper
- C++ native source, Julia source, sCode source/runtime helpers
- real project branding assets (`assets/logo.png`, GOAVA Radio assets, reference art)
- Linux desktop/MIME/AppStream metadata
- Flathub and Fedora packaging scaffolds
- source dependency documentation

Removed as deprecated/generated redistribution debris:
- duplicate historical Groovebox monoliths
- patch-only migration scripts
- Python caches
- build/dist directories
- host-built `.so/.dll/.dylib` products
- nested RUN-ME/UNZIP-ME release copies

Two publication inputs remain intentionally author-controlled: the software license and real current Linux store screenshots. Those are not guessed by the packaging process.
