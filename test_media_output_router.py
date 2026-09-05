import os
import tempfile
import unittest

from media_output_router import AudioTarget, DisplayTarget, MediaShareServer, player_routing


class OutputRouterTests(unittest.TestCase):
    def test_mpv_route_is_process_local(self):
        d = DisplayTarget("HDMI-1", index=1, backend="xrandr")
        a = AudioTarget("bluez_output.test", "Bluetooth speaker", kind="bluetooth")
        args, env = player_routing(d, a, want_video=True)
        self.assertIn("--fullscreen", args)
        self.assertIn("--fs-screen=1", args)
        self.assertEqual(env.get("PULSE_SINK"), "bluez_output.test")

    def test_share_manifest_keeps_playlist_modulation(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            srv = MediaShareServer(8780)
            srv.set_playlist([{"path": path, "volume": 73, "rate": 1.25, "pitch_semitones": -3.0}])
            self.assertEqual(len(srv.playlist), 1)
            self.assertEqual(srv.playlist[0]["volume"], 73)
            self.assertAlmostEqual(srv.playlist[0]["rate"], 1.25)
            self.assertAlmostEqual(srv.playlist[0]["pitch_semitones"], -3.0)
            self.assertIn("manifest.json", srv._tv_html())
        finally:
            os.unlink(path)

    def test_game_share_only_accepts_zip(self):
        srv = MediaShareServer(8780)
        fd, path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        try:
            key = srv.share_game(path)
            self.assertIn(key, srv.shared_games)
            self.assertIn("/game/", srv.game_url(key))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
