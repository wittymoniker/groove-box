"""R27.0.2 HDMI/DisplayPort audio endpoint and routing regression tests."""
from unittest.mock import patch
import media_output_router as r


def _which(name):
    return f'/usr/bin/{name}' if name in {'pactl', 'aplay', 'amixer', 'alsactl', 'alsaucm'} else None


def _run(cmd, timeout=2.0):
    if cmd[:4] == ['pactl', 'list', 'short', 'sinks']:
        return '42\tauto_null\tmodule-null-sink.c\ts16le\tIDLE\n'
    if cmd[:2] == ['aplay', '-L']:
        # Deliberately omit HDMI aliases here: some minimal ALSA builds do this.
        return 'default\n    Default PCM\nsysdefault:CARD=PCH\n    Internal\n'
    if cmd[:2] == ['aplay', '-l']:
        return ('card 0: PCH [HDA Intel PCH], device 0: ALC3204 Analog [ALC3204 Analog]\n'
                'card 0: PCH [HDA Intel PCH], device 3: HDMI 0 [HDMI 0]\n')
    return ''


def test_hdmi_is_discovered_from_hardware_even_without_aplay_L_alias():
    with patch.object(r.shutil, 'which', side_effect=_which), patch.object(r, '_run_text', side_effect=_run):
        targets = r.detect_audio_targets()
    hdmi = [t for t in targets if t.kind == 'hdmi' and t.backend == 'alsa']
    assert hdmi, targets
    assert any(t.name == 'alsa/plughw:CARD=PCH,DEV=3' for t in hdmi), hdmi
    assert any('HDMI / DisplayPort' in t.description for t in hdmi), hdmi


def test_explicit_hdmi_routes_to_selected_pcm_with_digital_safe_prepare():
    # GROOVEBOX_R27_HDMI_DIGITAL_SAFE_PREPARE_20261031: explicit HDMI routes call
    # _prepare_physical_alsa_output (digital-safe branch, is_digital=True) to unmute
    # the HDMI PCM without touching analog speaker UCM. This fixes HDMI silence on
    # Dell Latitude 3510 + external display. The digital branch never activates
    # analog UCM, so the speaker mixer is not mutated.
    target = r.AudioTarget('alsa/plughw:CARD=PCH,DEV=3', 'HDMI / DisplayPort · HDMI 0', kind='hdmi', backend='alsa')
    with patch.object(r, '_prepare_physical_alsa_output') as prep:
        args, env = r.player_routing(None, target, want_video=False)
    assert '--ao=alsa' in args, args
    assert '--audio-device=alsa/plughw:CARD=PCH,DEV=3' in args, args
    assert 'PULSE_SINK' not in env, env
    prep.assert_called_once()


def test_internal_speaker_default_remains_unchanged():
    with patch.object(r, '_real_alsa_playback_available', return_value=False):
        args, env = r.player_routing(None, r.AudioTarget('', 'System default', kind='default', backend='default'), want_video=False)
    assert not any('HDMI' in x for x in args)
    assert 'PULSE_SINK' not in env
