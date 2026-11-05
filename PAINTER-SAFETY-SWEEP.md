# Painter safety and maintenance sweep

The supplied `run_hybrid.sh` log reports an active painter at backing-store completion, another painter failing to begin, an inactive composition-mode call and a segmentation fault. This revision removes concrete lifetime and ownership hazards found in the supplied source; the log alone does not identify the exact crashing native instruction. Runtime tests were not run, following the request to stop testing.

## Comparison findings

- **Working V3/current merge:** Several main-window paint handlers relied on destruction of Python locals rather than guaranteed cleanup. The playlist viewport painter had cleanup on the normal path but not its exception path. Nested drawing closures and retained exception tracebacks make relying on destruction especially undesirable.
- **R41 comparison:** Adds painter tracking and cleanup around widget events. Its global class replacement and import-time subclass sweep are not copied wholesale: they change global behavior, expose only part of the original painter class interface, and do not cover classes created later.
- **Rev-m/rev-p comparison:** Its multidimensional `_safe_paint` catches selected exceptions but does not itself guarantee painter cleanup. That earlier helper is not treated as a complete fix.
- **Multidimensional merge:** `_safe_paint` was attached to `_open_multidim_editor`, not the panel's `paintEvent`. Two instance-level painter registries and a global wrapper were unnecessary lifetime machinery. Those registries, decorators and the global painter factory are removed in favor of explicit scopes.
- **Live trail compositor:** Its private accumulation-image painter could escape normal `end()` after a drawing exception. A later frame could then encounter the same device while it remained active.

## Implemented changes

- **Application ownership:** `qt_painting.owned_painter` wraps 46 construction sites in 13 application modules: `groovebox`, `multidim_ui`, `live_player`, `performance`, `fast_widgets`, `media_visualizer`, `signal_lab`, `layered_signal_lab`, `master_hardware_panel`, `visualizer_widget`, `groovebox_master`, `author_numeric_font` and `video_clip_studio`. It ends only its own painter in `finally`, leaves framework-supplied painters alone, skips unpaintable widgets and raises on failed offscreen image painting.
- **Native Qt interface:** `QPainter` remains the actual Qt class. No global subclass walk or painter-class substitution is installed.
- **Standalone games:** The two exported viewport painter branches use self-contained `try/finally` cleanup and reject active-device reentry. Exported games do not gain a dependency on `qt_painting.py`.
- **Image ownership:** Decoder preview frames are validated, reduced to RGB and copied into an owning QImage. Live recording snapshots already copy their pixels before handing them to the encoder thread.
- **Degenerate previews:** Empty live scopes produce a zero-valued visual trace, nonfinite visual samples are sanitized, and the cellular preview maintains at least one column. These changes do not alter synthesis mathematics or recorded audio samples.
- **Take naming:** A UUID suffix separates takes created in the same second rather than overwriting a prior output with the same timestamp.
- **Audio writer:** Disk-write and close failures set an explicit recording error, close the file in `finally` and stop accepting further audio. The writer uses its stop event instead of an unconditional polling sleep.
- **Video timeline:** A late first snapshot does not backfill future imagery into earlier slots. Uncaptured initial slots use a neutral slate; subsequent gaps continue to hold the last captured image.
- **Encoder lifecycle:** Removed the fixed encoder-startup sleep from the GUI thread. Encoder-start failures close their log descriptors, and finalization closes pipes/logs and terminates a child that exceeds its drain timeout.
- **Recovery:** Finalization errors no longer unconditionally remove the raw/intermediate take directory. The error message identifies the recovery path. Successful complete takes still clean temporary files.
- **Diagnostics:** Existing session logging now records bounded Python stacks for painter/backing-store warnings. The existing crash pointer and native fault log remain the places to look after a future failure.

## Preserved behavior and limits

The first archive's main-window implementation, wide biaxial canvases, enlarged centered master stage, seed/canonical ownership rules and existing pooling weights are retained. No blanket dependency upgrades, Qt ABI swaps or replacements of the comparison GUIs were performed.

The archive contains source, not a newly built executable or completed ISO. ISO and BUILD_KIT use the common runtime module inventory, including `qt_painting.py`, but neither a full release build nor laptop installation is verified by this sweep.

The segmentation fault has not been reproduced or demonstrated eliminated. The patched paths address the reported painter-lifetime failure class; a different native, driver or binary-compatibility cause remains possible.

Large legacy canonical commits can still block the GUI. Experimental cooperative batching remains off by default; this sweep does not turn it on or claim that the earlier canonical-pause issue is solved.

If a later launch still fails, preserve the session log and the native log referenced by `LATEST_CRASH_LOG.txt`, especially the first `QtPaintWarning` stack and any Python exception immediately preceding it. Those call sites are more useful than the last inactive-painter warning alone.
