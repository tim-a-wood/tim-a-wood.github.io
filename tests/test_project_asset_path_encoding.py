"""Mirror sprite workbench `projectAsset` path rules (JS) for regression coverage."""
from __future__ import annotations

import unittest
from urllib.parse import quote


def encode_path_segments(relative_path: str) -> str:
    """Match tools/2d-sprite-and-animation/index.html `projectAsset` segment encoding."""
    rel = relative_path.strip().replace("\\", "/").lstrip("/")
    return "/".join(quote(seg, safe="") for seg in rel.split("/") if seg)


class TestProjectAssetPathEncoding(unittest.TestCase):
    def test_forward_slashes_unchanged_for_ascii(self) -> None:
        self.assertEqual(
            encode_path_segments("animations/idle/south/frame_01.png"),
            "animations/idle/south/frame_01.png",
        )

    def test_backslashes_normalize(self) -> None:
        self.assertEqual(
            encode_path_segments(r"animations\idle\south\frame_01.png"),
            "animations/idle/south/frame_01.png",
        )

    def test_spaces_encoded(self) -> None:
        self.assertEqual(
            encode_path_segments("export/my clip/frame 1.png"),
            "export/my%20clip/frame%201.png",
        )


if __name__ == "__main__":
    unittest.main()
