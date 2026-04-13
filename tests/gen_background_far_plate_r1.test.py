"""Regression checks for R1 procedural background_far_plate generator."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "gen_background_far_plate_r1.py"


class TestBackgroundFarPlateR1(unittest.TestCase):
    def test_generates_1600_rgba_with_footprint_alpha(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.png"
            r = subprocess.run(
                [sys.executable, str(SCRIPT), str(out)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)
            from PIL import Image

            im = Image.open(out)
            self.assertEqual(im.size, (1600, 1200))
            self.assertEqual(im.mode, "RGBA")
            a = im.split()[3]
            self.assertEqual(a.getpixel((0, 0)), 0)
            # Known interior point inside footprint (from room polygon)
            self.assertGreater(a.getpixel((500, 600)), 200)


if __name__ == "__main__":
    unittest.main()
