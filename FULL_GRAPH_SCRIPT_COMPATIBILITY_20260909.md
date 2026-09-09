# Groovebox Full-Graph Script Compatibility — 2026-09-09

The graph is no longer treated as Seed-only metadata. Seed, Instrument, Algorithm, Domain, Canonical, sound, video, and game consumers share one deterministic graph context.

Variables: `t`, `t_norm`, `x`, `y`, `z`, `seed`, `seed_w`, `graph_radius`, `graph_phase`, `graph_energy`, `graph_index`, `graph_slot`, `graph_u`, `graph_v`, `graph_w`.

Output compatibility: old scalar returns continue to work. New writers may return vectors/lists or named mappings (`value`, spatial axes, pitch/amp/pan/filter, visual/game intentions). Unknown named channels are ignored rather than causing incompatibility.

Authoring updates: Random Seed Script has full-graph templates; Random Global Algorithm has full-graph and named-output templates; Canonical Global Algorithm superwrite authors full-graph functions; Heuristic → Seq Synth now writes spatial/time graph-aware script + domain material. RAND PARAM retains its low-latency deterministic implementation but reads the same graph-coordinate family rather than adding Python eval/RNG to the callback.

Cross-media: canonical documents now retain instrument scripts and the graph-context version/variable contract. Game identity accepts a graph-script fingerprint so changes to graph-authored material can change the deterministic world/video identity without depending on instrument count.
