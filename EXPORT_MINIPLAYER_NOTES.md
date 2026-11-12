# Export Miniplayer & Noisy Exports

When `noisy_exports` is True in compat settings:

- During audio or video export, a small floating miniplayer should appear
  near the export buttons.
- It lines up the current audio row (light voice bursts from the row being
  processed) with the latest video frames.
- Video is shown as a 50% translucent honeycomb / square grid overlay.
- Non-blocking, newest-frame-wins, does not affect the deterministic export.
- Closes when the job finishes.

Implementation sketch (to be wired into the export row loop near
_set_work_progress "synth row" updates):

    if settings.get("noisy_exports"):
        self._ensure_export_miniplayer()  # position near export buttons
        self._miniplayer_push_audio(row_idx, row_mix)
        if video_frame is not None:
            self._miniplayer_push_frame(video_frame)

Recommendations:
- Keep the miniplayer on a separate low-priority audio stream.
- Use the same light synth_row path from live_player.py for notes.
- Make the grid style selectable (honeycomb / squares / plain).
- Add a "mute preview" button on the miniplayer itself.
