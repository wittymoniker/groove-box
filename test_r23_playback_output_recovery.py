from unittest.mock import patch
import media_output_router as r


def _which(name):
    return f'/usr/bin/{name}' if name in {'pactl','aplay'} else None


def _run(cmd, timeout=2.0):
    if cmd[:4] == ['pactl','list','short','sinks']:
        return '42\tauto_null\tmodule-null-sink.c\ts16le 2ch 48000Hz\tIDLE\n'
    if cmd[:2] == ['aplay','-l']:
        return 'card 0: sofhdadsp [sof-hda-dsp], device 0: HDA Analog (*) []\n'
    if cmd[:2] == ['aplay','-L']:
        return 'default\n    Default PCM\nsysdefault:CARD=sofhdadsp\n    sof-hda-dsp\nhdmi:CARD=sofhdadsp,DEV=0\n    HDMI\n'
    return ''


def test_dummy_pulse_never_forces_null_audio():
    with patch.object(r.shutil, 'which', side_effect=_which), patch.object(r, '_run_text', side_effect=_run):
        args, env = r.player_routing(None, None, want_video=True)
    assert '--ao=null' not in args
    assert '--ao=alsa' in args
    assert '--audio-device=alsa/plughw:CARD=sofhdadsp,DEV=0' in args
    assert '--audio-samplerate=48000' in args
    assert '--audio-channels=stereo' in args
    assert '--audio-fallback-to-null=no' in args
    assert 'PULSE_SINK' not in env


def test_alsa_targets_include_internal_speaker_route():
    with patch.object(r.shutil, 'which', side_effect=_which), patch.object(r, '_run_text', side_effect=_run):
        targets = r.detect_audio_targets()
    names = [x.name for x in targets]
    assert 'alsa/sysdefault:CARD=sofhdadsp' in names
    assert 'alsa/hdmi:CARD=sofhdadsp,DEV=0' in names


def test_explicit_real_pulse_sink_is_preserved():
    target = r.AudioTarget('alsa_output.pci-test.analog-stereo', 'Internal Speakers', backend='pulse')
    with patch.object(r, '_real_pulse_sink_available', return_value=True):
        args, env = r.player_routing(None, target, want_video=False)
    assert env['PULSE_SINK'] == target.name
    assert '--ao=null' not in args
    assert '--audio-samplerate=48000' in args
