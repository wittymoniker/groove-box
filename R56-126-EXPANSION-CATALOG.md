# MATGROOVEBOX R56 — 126-part expansion register

Legend: `[x]` source implementation plus focused test evidence; `[~]` source integration exists but GUI/installer/hardware acceptance is still pending; `[ ]` scoped for follow-on work. This is a work register, not a claim that 126 features have shipped.

## A. Cloud Command Center and launch surfaces

1. [~] Add the top-of-main-window Cloud Command Center toolbar.
2. [~] Put the GOAVA Autopilot launcher at the toolbar's visual center.
3. [~] Route Cloud menu entries to Extensions, Hardware, Transfer, Updates, Workspaces and Autopilot panels.
4. [~] Add an always-visible local/remote connection state indicator.
5. [~] Add a Hardware Explorer entry point with read-only inventory.
6. [~] Add user-data backup, verification and restore entry points.
7. [x] Add local update-bundle inspection and staging entry points.
8. [~] Add a Workspace Hub entry point.
9. [x] Keep cloud operations local-first and user-initiated by default.
10. [ ] Add authenticated cloud-provider connector slots.
11. [ ] Add background sync queues with pause/resume.
12. [ ] Add sync-conflict inspection and three-way merge UI.
13. [ ] Add account/token storage through the OS secret service.
14. [ ] Add notification center for transfer, sync and update results.

## B. GUI items, launchers and sCode extension contracts

15. [x] Add versioned extension manifest metadata.
16. [x] Define reusable button, toggle, slider, knob, meter, waveform, panel and launcher item kinds.
17. [x] Add stable launcher specifications and categories.
18. [x] Add reusable extension/GUI-item/launcher metadata pool.
19. [x] Define per-extension permission names.
20. [ ] Implement sandboxed extension execution.
21. [ ] Add extension hot reload with lifecycle cleanup.
22. [ ] Add script debugger and variable/event inspection.
23. [ ] Add visual GUI-item editor.
24. [ ] Add drag-and-drop panel composition.
25. [ ] Add dockable/floating custom panels.
26. [ ] Add theme and icon packs for extensions.
27. [ ] Add extension package builder and dependency resolver.
28. [ ] Add signed extension manifests and trust UI.

## C. Hardware discovery and access broker

29. [x] Add read-only Linux sysfs hardware discovery.
30. [x] Discover ALSA MIDI class descriptors where exposed.
31. [x] Discover USB serial and ACM serial endpoints.
32. [x] Discover ALSA sound cards.
33. [x] Discover V4L2 camera/capture endpoints.
34. [x] Discover HID raw endpoints.
35. [x] Discover evdev input/gamepad endpoints.
36. [x] Discover network and Bluetooth adapter descriptors without opening them.
37. [x] Read USB vendor/product and GPIO-chip descriptors.
38. [x] Add explicit per-device capability permission ledger.
39. [x] Require explicit approval before adapter access.
40. [x] Add injected-backend generic read/write/subscribe facade.
41. [ ] Add persistent user-visible permission profiles.
42. [ ] Add udev event subscription and live hot-plug notifications.

## D. Core creative hardware protocol adapters

43. [~] Add MIDI 1.0 message and subscription facade.
44. [~] Add bounded USB/ACM serial read/write facade.
45. [~] Add HID report facade.
46. [~] Add audio interface stream facade.
47. [~] Add UVC camera capture facade.
48. [x] Add OSC message encoder and injected sender.
49. [x] Add Art-Net DMX universe packet encoder.
50. [~] Add gamepad event subscription facade.
51. [~] Add read-only storage-device inspection facade.
52. [x] Add ILDA point validation and laser-DAC safety gate.
53. [~] Retain Bluetooth discovery adapter contract.
54. [~] Retain PTZ camera adapter contract with operator confirmation.
55. [~] Retain IoT/Home Assistant adapters with actuator confirmation.
56. [x] Add BLE-MIDI, sACN and explicit-approval GPIO facades.

## E. Autopilot, GOAVA and stochastic DJ activity

57. [x] Reuse deterministic Seed-Fractal candidate evolution engine.
58. [x] Add GOAVA-aware activity controller.
59. [x] Add adaptive stochastic response mode.
60. [x] Add sparse, dense, locked and ambient activity modes.
61. [x] Add bounded energy/flux-driven control response.
62. [x] Add smooth self-reinterpolation from previous to target DJ amounts.
63. [~] Connect Autopilot to existing GOAVA DJ control.
64. [~] Connect Autopilot to existing RAND PARAM control.
65. [~] Add Auto-activity toggle using live scope energy.
66. [~] Add Start, Pause/Resume and Stop controls.
67. [x] Keep candidate evolution off the audio callback.
68. [x] Keep playback start and project promotion under user control.
69. [ ] Add beat/bar phrase awareness and phrase-safe transitions.
70. [ ] Add user-curated style profiles and crossfade planning.

## F. Performance and real-time behavior

71. [x] Keep GOAVA activity calculation on a bounded control-thread timer.
72. [x] Keep the existing audio callback free of Qt widget reads.
73. [x] Keep the candidate engine in a separate bounded background thread.
74. [ ] Add CPU-budget telemetry for Autopilot and extensions.
75. [ ] Add event-queue backpressure metrics.
76. [ ] Add real-time allocation regression checks for all DJ paths.
77. [ ] Add SIMD/native acceleration for hot event transforms.
78. [ ] Add vectorized GOAVA feature extraction.
79. [ ] Add adaptive update cadence under low-power conditions.
80. [ ] Add memory-budgeted extension caches.
81. [ ] Add extension worker isolation and crash containment.
82. [ ] Add deterministic render-vs-live equivalence tests for GOAVA Autopilot.
83. [ ] Add latency benchmark dashboard.
84. [ ] Add 8 GB / 16 GB / 32 GB memory profile benchmarks.

## G. sOS separate user data and migration

85. [x] Add separate SOS_USERDATA partition planning.
86. [~] Mount SOS_USERDATA at `/home` in the installed system fstab.
87. [~] Keep sOS_SYSTEM as the separate system-state/cache/rollback volume where capacity permits.
88. [~] Add `--preserve-user-data` installer option.
89. [~] Add interactive PRESERVE choice for older copyover layouts.
90. [~] Archive old `/home` on the retained system partition before root formatting.
91. [~] Checksum and verify the migration archive before restoring.
92. [~] Preserve an existing separate user-data filesystem when requested.
93. [~] Seed a new user-data filesystem from the live image home on fresh installs.
94. [x] Add standalone user-data backup creation.
95. [x] Add backup verification.
96. [x] Add non-overwriting restore.
97. [ ] Add selective settings/project migration profiles.
98. [ ] Add migration preview with estimated space and per-folder selection.

## H. Update, transfer, rollback and recovery dynamics

99. [x] Add local ZIP integrity inspection for update bundles.
100. [x] Reject path-traversal entries in staged update bundles.
101. [x] Stage updates in a user-owned data directory.
102. [ ] Add signed release-manifest verification.
103. [ ] Add anti-rollback version policy.
104. [ ] Add inactive-slot update activation.
105. [ ] Add system update rollback and recovery selector.
106. [ ] Add delta updates for large media/runtime payloads.
107. [ ] Add update bandwidth and disk-space budgets.
108. [ ] Add transfer resume and interrupted-copy recovery.
109. [ ] Add device-to-device project transfer discovery.
110. [ ] Add clone-bundle restore preview.
111. [ ] Add migration/upgrade reports with file-level provenance.
112. [ ] Add recovery from interrupted user-data migration.

## I. Diagnostics, developer experience and release acceptance

113. [x] Add focused tests for extension metadata, hardware broker and GOAVA controller.
114. [x] Add focused tests for OSC, Art-Net and ILDA safety gate.
115. [x] Add focused tests for user-data backup/restore and update staging.
116. [x] Add GPT partition-plan arithmetic tests across target capacities.
117. [x] Add active overlay synchronization for new runtime packages and sCode libraries.
118. [ ] Add PyQt6 GUI launch/interaction tests in dependency-complete CI.
119. [ ] Add QEMU/OVMF boot tests for the new installer partition layout.
120. [ ] Add simulated copyover tests for old two-, three- and four-partition layouts.
121. [ ] Add physical hardware acceptance for MIDI/audio/HID/serial/camera/DMX.
122. [ ] Add hardware-in-loop ILDA interlock/scan-fail tests with certified equipment.
123. [ ] Add signed update and extension provenance tests.
124. [ ] Add full R56 ISO build and structural verification.
125. [ ] Add physical UEFI/Secure Boot install and upgrade acceptance.
126. [ ] Publish a signed R56 release manifest after all blockers pass.

## Acceptance policy

A planned item becomes `[x]` only when its implementation is present and its corresponding automated or documented manual acceptance evidence exists. GUI, boot, installer and hardware items cannot be certified by Python unit tests alone.


## Release integration follow-through

- [x] Add paired Secure Boot / unsigned ISO release wrapper with explicit dual-mode Limine menu verification.
- [x] Add six-partition shared-Limine USB writer with three independent data volumes and guarded destructive workflow.
- [x] Add build/partition/enrollment/validation documentation.
- [ ] Generate the paired R56 ISO artifacts on the complete build host.
- [ ] Validate both menu paths under QEMU/OVMF and physical UEFI firmware.
