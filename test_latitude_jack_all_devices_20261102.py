"""GROOVEBOX_R23R_LATITUDE_ALL_DEVICES_JACK_20261102: sos-hardware-volume levels every card and follows the headphone jack.

Runs the real helper script against stub aplay/amixer/alsaucm/pactl/wpctl binaries that model a Latitude 3510:
card 0 = analog HDA codec (Master/Speaker/Headphone/Line Out + a Headphone Jack), card 1 = HDMI.
"""
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "BUILD_ISO" / "v35_22zz" / "sos-hardware-volume-v35_22zz_r23h"

STUBS = {
    "aplay": '''#!/bin/sh
cat <<'EOT'
**** List of PLAYBACK Hardware Devices ****
card 0: PCH [HDA Intel PCH], device 0: ALC3254 Analog [ALC3254 Analog]
card 1: HDMI [HDA Intel HDMI], device 3: HDMI 0 [HDMI 0]
EOT
''',
    "amixer": '''#!/bin/sh
# amixer -c N scontrols | sget NAME | sset NAME VALUE | cget iface=CARD,name='X'
LOG="$STUB_DIR/amixer.log"; card="$2"; shift 2
case "$1" in
  scontrols)
    if [ "$card" = 0 ]; then
      printf "Simple mixer control 'Master',0\\nSimple mixer control 'Headphone',0\\nSimple mixer control 'Speaker',0\\nSimple mixer control 'Line Out',0\\nSimple mixer control 'Mic',0\\nSimple mixer control 'Auto-Mute Mode',0\\n"
    else
      printf "Simple mixer control 'IEC958',0\\nSimple mixer control 'IEC958',1\\n"
    fi ;;
  cget)
    if [ "$card" = 0 ] && echo "$*" | grep -q "Headphone Jack"; then printf "numid=9,iface=CARD,name='Headphone Jack'\\n  ; type=BOOLEAN,access=r-------,values=1\\n  : values=%s\\n" "$(cat "$STUB_DIR/jack")"; fi ;;
  sget) printf "  Mono: Playback 40 [72%%] [on]\\n" ;;
  sset) echo "card$card $*" >> "$LOG" ;;
esac
exit 0
''',
    "alsaucm": '#!/bin/sh\ncat >> "$STUB_DIR/ucm.log"\nexit 0\n',
    "pactl": "#!/bin/sh\nexit 0\n",
    "wpctl": "#!/bin/sh\nexit 0\n",
}


def _run(tmp_path, cmd, jack="off"):
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    for name, body in STUBS.items():
        f = stub / name
        f.write_text(body)
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "jack").write_text(jack)
    script = HELPER.read_text()
    script = script.replace("/var/lib/groovebox", str(tmp_path / "var")).replace("/run/sos", str(tmp_path / "run"))
    script = script.replace("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n", "")   # keep the stub PATH
    path = tmp_path / "helper.sh"
    path.write_text(script)
    (tmp_path / "run").mkdir(exist_ok=True)
    (tmp_path / "var").mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{stub}:/usr/bin:/bin", STUB_DIR=str(tmp_path))
    subprocess.run(["/bin/sh", str(path), *cmd], env=env, check=True, capture_output=True, timeout=30)
    log = tmp_path / "amixer.log"
    ucm = tmp_path / "ucm.log"
    return (log.read_text() if log.exists() else ""), (ucm.read_text() if ucm.exists() else "")


def test_script_is_valid_posix_sh():
    subprocess.run(["/bin/sh", "-n", str(HELPER)], check=True)


def test_every_playback_card_is_levelled_and_unmuted(tmp_path):
    log, _ = _run(tmp_path, ["set", "60"])
    assert "card0 sset Master 60%" in log and "card0 sset Headphone 60%" in log
    assert "card0 sset Line Out 60%" in log                       # codecs that expose the jack as Line Out
    assert "card1 sset IEC958 60%" in log or "card1 sset IEC958 unmute" in log   # HDMI is not left behind


def test_sync_keeps_the_analog_speaker_and_headphone_controls_unmuted(tmp_path):
    log, _ = _run(tmp_path, ["sync"])
    assert "card0 sset Speaker" in log and "card0 sset Headphone unmute" in log


def test_jack_command_reacts_only_to_a_change(tmp_path):
    _, ucm1 = _run(tmp_path, ["jack"], jack="off")                 # first call records state and prepares the route
    assert "set _enadev Speaker" in ucm1 and "set _enadev Headphones" not in ucm1
    (tmp_path / "amixer.log").unlink(missing_ok=True); (tmp_path / "ucm.log").unlink(missing_ok=True)
    log, ucm = _run(tmp_path, ["jack"], jack="off")                # unchanged: no work at all
    assert log == "" and ucm == ""


def test_plugging_headphones_enables_the_headphone_ucm_device_and_unmutes_it(tmp_path):
    _run(tmp_path, ["jack"], jack="off")
    (tmp_path / "amixer.log").unlink(missing_ok=True); (tmp_path / "ucm.log").unlink(missing_ok=True)
    log, ucm = _run(tmp_path, ["jack"], jack="on")
    assert "set _enadev Headphones" in ucm
    assert "card0 sset Headphone unmute" in log and "card0 sset Auto-Mute Mode Disabled" in log


def test_isos_verifier_markers_are_kept():
    s = HELPER.read_text()
    for needle in ('apply_volume "$c" "$pct"; apply_mute "$c" 0', 'alsaucm -c "hw:$c" -b -',
                   'amixer -c "$c" sset "$n" "${pct}%"', "pactl set-sink-volume @DEFAULT_SINK@",
                   "GROOVEBOX_V35_22ZZ_R23H_LINKED_HARDWARE_VOLUME_20261002",
                   "GROOVEBOX_V35_22ZZ_R23M_UCM_SINGLE_SESSION_20261004",
                   "BOOT_STATE=/run/sos/audio-hardware.state", "s/^card=//p"):
        assert needle in s, needle


def test_volume_widget_polls_the_jack_helper():
    src = (ROOT / "hardware_volume.py").read_text(encoding="utf-8")
    assert "request_hardware_volume('jack')" in src and "setInterval(3000)" in src
    assert "setInterval(350)" in src                                    # existing linked state polling kept
