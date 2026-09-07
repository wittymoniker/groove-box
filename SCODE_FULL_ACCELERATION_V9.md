# sCode ABI 9 — pool-complete Groovebox optimizer contract

This release freezes sCode first, then Groovebox, then the sOS appliance staging tree.

## sCode contract

- Optimizer ABI 9.
- Universal pool ABI 3 with 18 formats: generic, scalar, vector, matrix, tensor, bytes, text, audio, image, video-frame, object, compiled, symbol, project, sequence, automation, world, and media-stream.
- Every poolable request uses the same finite/exact pipeline: format -> identity -> modality -> shape/subtype -> request key -> slot -> generation -> lane -> coalescing slot -> buffer/ring slot -> result slot -> reuse decision.
- Pool arithmetic folds through `FINITE_INFINITY=134964356` so the stage-0 numeric runtime does not depend on oversized integer products.
- Completion ABI 1 has PURE, GENERATION, FRAME, STREAM, and SIDE_EFFECT policies.
- Host execution uses `scode-work` workers and a separate `scode-complete` publication thread.
- GENERATION/FRAME completions are rejected when stale; STREAM is latest-ready; SIDE_EFFECT never replays from cache or coalesces.
- Qt callbacks are marshalled to the GUI thread. Realtime audio performs no sCode subprocess/IPC or completion bookkeeping.
- The sCode-generated 18-format catalog is loaded once at startup. The host request descriptor is an exact finite-math mirror and is parity-tested against the bundled stage-0 request probe.

## Author-number contract

Scheme: `base16-squiggle-crossbar-subscale-v7`.

- cells 0..15 are base-16 values;
- 16 is the completed-cycle cell;
- every glyph has four ordered cross-bar positions;
- each cross-bar is absent=0, dotted=0.5, or solid=1;
- the automatic 16 cell is solid mask 1111 / dotted mask 0000;
- squiggle can carry the in-cell 2^-1 fraction;
- additional subscale cells proceed at 2^-4k;
- a spaced fractional stroke is 1/1 of its slot and an unspaced stroke is 1/2;
- 17 × 2 × 2 × 3^4 = 5,188 semantic glyph states are precomputed.

## Groovebox consumers

Groovebox consumes the frozen ABI for result generations, universal pool descriptors, background workers/completions, media reconstruction, project save/autosave side effects, visual/frame publication, symbol packets and caches, canonical work claims, stream publication, and reusable native/NumPy buffers. The realtime audio callback reads already-ready state and remains outside sCode IPC.

## sOS boundary

sOS stages this exact sCode/Groovebox pair in `/opt/groovebox`, performs ABI-9 preflight before launch/install, includes the installed-appliance kernel/GRUB/dracut filesystem stack, and has guarded destructive install-to-disk logic. Both normal and Safe/Recovery GRUB entries search for the installed root UUID before loading the kernel.
