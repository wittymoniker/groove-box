# Party Mode

System Settings toggle + intensity slider (0–100).

When on, while you work on a project, render video, or interact with methods:
- Windows receive distortion, color shift, and layering.
- Recent project material (last frames, waveforms, spectral slices, or the
  current scenograph) is played back / composited onto each window at a
  strength controlled by the slider.
- Affects the main window, floating editors, Live Player, and export
  miniplayer surfaces.

Implementation notes:
- Setting lives in compat_settings.py (`party_mode`, `party_intensity`).
- `_apply_party_mode()` stamps the intensity onto windows and requests a
  repaint.
- Actual visual effect belongs in a lightweight overlay or paintEvent filter
  that reads `partyIntensity` and mixes a distorted, hue-shifted copy of the
  most recent project buffer (audio waveform, video frame, or spectral image).
- Keep it optional and cheap; disable the effect path entirely when the
  toggle is off.
