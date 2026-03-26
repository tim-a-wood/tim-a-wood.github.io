import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MANIFEST = ROOT / "assets" / "test-hero" / "runtime-manifest.json"
RUNTIME_FRAMES = ROOT / "assets" / "test-hero-frames"


class AshenHollowRuntimeManifestTests(unittest.TestCase):
    def test_runtime_manifest_exists_and_has_expected_keys(self):
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["basePath"], "assets/test-hero-frames")
        self.assertEqual(manifest["frameWidth"], 256)
        self.assertEqual(manifest["frameHeight"], 256)
        self.assertIn("pivot", manifest)
        self.assertIn("body", manifest)
        self.assertIn("clips", manifest)
        self.assertIn("debugBindings", manifest)

    def test_runtime_manifest_frames_exist_in_checked_in_sample_directory(self):
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        clips = manifest.get("clips") or {}
        self.assertIn("idle", clips)
        self.assertIn("run", clips)
        self.assertIn("jump", clips)
        self.assertIn("attack", clips)
        self.assertIn("parry", clips)
        for clip_name, clip in clips.items():
            frames = clip.get("frames") or []
            self.assertEqual(len(frames), int(clip.get("frame_count") or 0), clip_name)
            for frame_name in frames:
                self.assertTrue((RUNTIME_FRAMES / frame_name).exists(), f"missing frame for {clip_name}: {frame_name}")


if __name__ == "__main__":
    unittest.main()
