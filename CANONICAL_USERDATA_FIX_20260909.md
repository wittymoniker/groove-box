# Canonical Userdata Isolation Fix — 2026-09-09

- `global_algo_state` is strictly user-owned project data.
- Canonical Algorithm-Bay output now lives only in `_canonical_global_algo_projection`.
- Canonical projection is tagged `user_data=False`, `user_defined=False`, `canonical_owner="unison"`.
- Canonical projection is re-derived from user data on each canonical transaction; it never feeds itself.
- Returning all canonical engines to OFF discards the projection and refreshes clean user baselines for playlist rows, sequencer patterns, sequence panels, and macro parameters.
- Runtime/game/canonical identity may consume the effective projection while engines are active, while project save/load and Undo/Redo continue to serialize the authored `global_algo_state`.
- User edit paths no longer mark authored Global Algorithm state as `canonical_superwrite=True`.
- Added `test_canonical_userdata_ownership_contract.py`.

Focused regression result: 20 passed.
