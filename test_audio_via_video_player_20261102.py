import re

SRC = open("performance.py", encoding="utf-8").read()

def test_flag_default_on_and_env_off_switch():
    assert '_AUDIO_VIA_VIDEO_PLAYER = os.environ.get("GROOVEBOX_AUDIO_VIA_PLAYER", "1")' in SRC

def test_inline_audio_paths_skipped_when_flag_on():
    i = SRC.index("def _play_path")
    j = SRC.index("def _host_decode_bridge") if SRC.index("def _host_decode_bridge") > i else len(SRC)
    body = SRC[i:SRC.index("    def _start_host_decode", i)]
    assert "if ext in AUDIO_EXT and not _AUDIO_VIA_VIDEO_PLAYER:" in body
    # the generic external-player launch (same as video) still follows the inline block
    assert "_player_cmd_with_volume(volume_pct, want_video=want_video)" in body
    assert "self._routed_player(cmd, want_video=want_video)" in body
