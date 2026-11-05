# Global carrier policy — R28.4.42

Vector, Wavetable, Bouncing Ball and Cellular Automata are defined as global-singleton carrier-wave generators in the shared synth context. Each carrier lane has sidechain depth scale 0.5 relative to other instruments, retains peer/equipotent scheduling, and keeps the existing spatial bus allocation (0.19758 spatial group; 0.8024 other instruments).

Direct user activity is represented by `set_activity_lock(context, lane, True, reason)`. While locked, canonical program updates do not auto-generate/restart that lane. `reset_activity_lock` releases the lock; `canonical_may_start` exposes the guard for UI/transport code. The user-authored lane events remain the lane owner while locked.

The current patch adds this shared contract and unit tests. It does not claim a live GUI/audio callback integration or physical hardware test. Before production release, connect UI bounce and single-cell lock gestures to `set_activity_lock`, wire explicit reset/no-activity controls to `reset_activity_lock`, and ensure live renderers consume `sidechain_depth_scale` exactly once.
