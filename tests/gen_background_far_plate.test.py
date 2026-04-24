"""Sanity checks for procedural background_far_plate generator (1600×1200, footprint alpha)."""
import importlib.util
import os
import tempfile
import unittest


def _load_module():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "gen_background_far_plate_gothic_hall.py")
    spec = importlib.util.spec_from_file_location("gen_bg", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestBackgroundFarPlateGenerator(unittest.TestCase):
    def test_void_polygon_is_simple_and_eight_vertices(self):
        mod = _load_module()
        poly = mod.VOID_POLY
        self.assertEqual(len(poly), 8)

    def test_generated_png_dimensions_and_transparent_outside(self):
        mod = _load_module()
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.png")
            os.environ["OUT"] = out
            try:
                mod.main()
            finally:
                os.environ.pop("OUT", None)

            im = Image.open(out).convert("RGBA")
            self.assertEqual(im.size, (1600, 1200))
            # Corner of canvas should be outside void → transparent
            self.assertEqual(im.getpixel((0, 0))[3], 0)
            # Approximate interior sample (chamber center)
            self.assertGreater(im.getpixel((800, 600))[3], 200)


if __name__ == "__main__":
    unittest.main()
