import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "ark-codex-skill"
    / "scripts"
    / "prepare_loops.py"
)
spec = importlib.util.spec_from_file_location("prepare_loops", SCRIPT)
loops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loops)


class PrepareLoopsTests(unittest.TestCase):
    def make_pet(self, pet, count=36, period=16):
        folder = pet / "frames" / "idle"
        folder.mkdir(parents=True)
        for index in range(count):
            rgba = np.zeros((64, 64, 4), dtype=np.uint8)
            x = 12 + index % period
            rgba[20:40, x : x + 12] = [230, 90, 30, 200]
            rgba[24:36, x + 3 : x + 9] = [30, 190, 240, 255]
            Image.fromarray(rgba).save(folder / f"frame_{index:04d}.png")
        manifest = {
            "fps": 20,
            "size": 64,
            "states": {
                "idle": {
                    "count": count,
                    "duration": count * 50,
                    "bbox": [12, 20, 38, 39],
                }
            },
        }
        (pet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return folder

    def test_detects_period_and_preserves_source_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            pet = Path(directory)
            folder = self.make_pet(pet)
            originals = [path.read_bytes() for path in sorted(folder.glob("*.png"))]
            info = loops.prepare_pet(pet)["states"]["idle"]
            self.assertEqual(info["loop_end"] - info["loop_start"], 16)
            self.assertEqual(info["source_count"], 36)
            self.assertEqual(info["count"], 39)
            self.assertEqual(info["loop_frames"][-3:], [36, 37, 38])
            self.assertEqual(info["loop_duration"], 950)
            for index, original in enumerate(originals):
                self.assertEqual(
                    (folder / f"frame_{index:04d}.png").read_bytes(), original
                )
            for index in (36, 37, 38):
                with Image.open(folder / f"frame_{index:04d}.png") as image:
                    alpha = np.asarray(image.getchannel("A"))
                    self.assertEqual(int(alpha[0, 0]), 0)
                    self.assertGreater(int(alpha.max()), 0)

    def test_manual_range_and_rerun_replace_generated_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            pet = Path(directory)
            folder = self.make_pet(pet)
            info = loops.prepare_pet(pet, ("idle",), 3, 19, 3)["states"]["idle"]
            self.assertEqual(info["loop_frames"], list(range(3, 19)) + [36, 37, 38])
            info = loops.prepare_pet(pet, ("idle",), 4, 20, 1)["states"]["idle"]
            self.assertEqual(info["source_count"], 36)
            self.assertEqual(info["count"], 37)
            self.assertFalse((folder / "frame_0037.png").exists())
            info = loops.prepare_pet(pet, ("idle",), 4, 20, 0)["states"]["idle"]
            self.assertEqual(info["loop_frames"], list(range(4, 20)))
            self.assertFalse((folder / "frame_0036.png").exists())

    def test_rejects_invalid_manual_interval_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            pet = Path(directory)
            folder = self.make_pet(pet)
            with self.assertRaises(ValueError):
                loops.prepare_pet(pet, ("idle",), 10, 5)
            self.assertEqual(len(list(folder.glob("*.png"))), 36)


if __name__ == "__main__":
    unittest.main()
