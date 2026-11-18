# R106 — Multidim instrument GUI labels

- The Multidim instrument selector now displays the same user-defined instrument labels as the main selector.
- Added an inline rename field and Apply name action in the Multidim window; clearing the field and applying restores the default label.
- Rename validation rejects duplicate labels and retains the existing 48-character normalization/limit.
- Stable canonical instrument keys remain the combo item data and are still used for all synth state, sequence, automation, and patch lookups.
- Renames made in either the main window or Multidim refresh the other visible selector. Project-loaded names refresh the Multidim selector too.
- Regression contract tests cover display-label/key separation, direct rename/reset controls, and host refresh integration.

Validation: Python compilation passed for root and active ISO-overlay modules. Targeted regression tests: 8 passed (3 rename contract tests and 5 export recovery tests). PyQt6 GUI interaction, full application runtime, ISO mastering, and hardware boot were not run in this environment.
