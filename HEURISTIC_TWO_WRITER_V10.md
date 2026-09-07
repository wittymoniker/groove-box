# Heuristic Composer Two-Writer Contract

Release cleanup on top of sCode optimizer ABI 9.

- The Heuristic Composer has exactly two write controls: **HEURISTIC WRITE STEP** and **HEURISTIC WRITE AUTOMATION**.
- Both use the shared **GLOBAL / LOCAL** scope selector.
- STEP and AUTOMATION retain separate exact revert snapshots, so either can be reverted without erasing the other.
- The older third/direct **Heuristic Step Write** / number-theory apply toggle is retired rather than aliased.
- Its dedicated `LOCAL selected sequence` toggle and direct apply/unapply snapshot path are retired with it.
- ℤ-Lattice mode, modulus and depth remain available to the Heuristic Composer and **Algorithm → Seed**.
- Algorithm XMod now gates from the authoritative **HEURISTIC WRITE STEP** state.
- Obsolete legacy project keys are simply ignored when loading older projects.
