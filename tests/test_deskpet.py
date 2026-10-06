import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

APP_DIR = (
    Path(__file__).resolve().parents[1] / "ark-codex-skill" / "assets" / "deskpet-app"
)


@unittest.skipUnless(sys.platform == "win32", "deskpet template requires Windows")
class DeskpetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(APP_DIR))
        spec = importlib.util.spec_from_file_location(
            "deskpet_main", APP_DIR / "main.py"
        )
        cls.main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.main)
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.status = {
            "active": True,
            "task": "A long task title that must scroll in a small pet window",
            "elapsed": 10,
            "tokens": 1000,
            "model": "test",
        }
        main = self.main
        self.patches = [
            patch.object(
                main,
                "load_settings",
                return_value=dict(main.DEFAULT_SETTINGS, scale=0.3),
            ),
            patch.object(main, "save_settings"),
            patch.object(
                main.codex_monitor, "get_codex_status", side_effect=lambda: self.status
            ),
            patch.object(main.PetWindow, "show"),
            patch.object(main.PetWindow, "isVisible", return_value=True),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.window = main.PetWindow()
        for timer in (
            self.window.timer,
            self.window.status_timer,
            self.window.fullscreen_timer,
            self.window.sit_timer,
            self.window.sleep_timer,
            self.window.subtitle_timer,
        ):
            timer.stop()
        self.addCleanup(self.window.deleteLater)

    def test_scroll_pause_wrap_and_live_status_updates(self):
        window = self.window
        window.subtitle_last_tick = 100
        window.subtitle_pause_until = 101.2
        with patch.object(self.main.time, "monotonic", return_value=101):
            window.scroll_subtitle()
        self.assertEqual(window.subtitle_offset, 0)
        with patch.object(self.main.time, "monotonic", return_value=102):
            window.scroll_subtitle()
        self.assertEqual(window.subtitle_offset, 24)
        self.status["elapsed"] += 2
        self.status["tokens"] += 300
        window.refresh_status()
        self.assertEqual(window.subtitle_offset, 24)
        self.assertEqual(window.toolTip(), window.status_text)
        window.subtitle_offset = 10000
        with patch.object(self.main.time, "monotonic", return_value=103):
            window.scroll_subtitle()
        self.assertEqual(window.subtitle_offset, 0)
        self.assertAlmostEqual(window.subtitle_pause_until, 104.2)
        window.subtitle_offset = 50
        self.status["task"] = "New task"
        window.refresh_status()
        self.assertEqual(window.subtitle_offset, 0)

    def test_short_caption_centers_and_render_does_not_truncate(self):
        from PySide6.QtGui import QImage

        window = self.window
        window.status_text = "Idle"
        window.subtitle_offset = 50
        window.scroll_subtitle()
        self.assertEqual(window.subtitle_offset, 0)
        window.bar_length = 40
        bar = window.subtitle_bar()
        self.assertAlmostEqual(bar.center().x(), window.width() / 2)
        window.current_image = lambda: QImage()
        window.grab()  # Exercise real QPainter clipping on the Windows backend.
        window.status_text = "滚动字幕 English " * 30
        window.subtitle_offset = 40
        window.grab()

    def test_loop_sequence_and_original_one_shot_behavior(self):
        window = self.window
        states = {
            name: {
                "count": 8,
                "source_count": 6,
                "bbox": [0, 0, 63, 63],
                "loop_frames": [1, 2, 6, 7],
            }
            for name in ("idle", "move", "sit", "sleep", "interact")
        }
        with patch.dict(self.main.MANIFEST, {"states": states}):
            for state in ("idle", "move", "sit", "sleep"):
                window.set_state(state, hold=state in ("sit", "sleep"))
                self.assertEqual(window.frame_index, 1)
                for expected in (2, 6, 7, 1):
                    window.next_frame()
                    self.assertEqual(window.frame_index, expected)
            for state in ("interact", "sit"):
                window.set_state(state)
                self.assertEqual(window.frame_index, 0)
                window.frame_index = 5
                window.next_frame()
                self.assertEqual(window.state, "idle")
            window.set_state("sleep")
            window.frame_index = 5
            window.next_frame()
            self.assertEqual(window.frame_index, 5)
            states["idle"] = {"count": 6, "bbox": [0, 0, 63, 63]}
            window.set_state("idle")
            window.frame_index = 5
            window.next_frame()
            self.assertEqual(window.frame_index, 0)


if __name__ == "__main__":
    unittest.main()
