"""Smoke import for staged environment_v3 package (Milestone 1 scaffold)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.environment_v3 import persistence
from scripts.environment_v3.persistence import (
    ARTIFACT_STYLEPACK,
    DERIVED_SUBDIR,
    derived_artifact_path,
    derived_room_dir,
)


class EnvironmentV3PackageTests(unittest.TestCase):
    def test_derived_paths(self) -> None:
        root = Path("/tmp/proj")
        self.assertEqual(
            derived_room_dir(root, "R1"),
            root / DERIVED_SUBDIR / "R1",
        )
        self.assertEqual(
            derived_artifact_path(root, "R1", ARTIFACT_STYLEPACK),
            root / DERIVED_SUBDIR / "R1" / ARTIFACT_STYLEPACK,
        )

    def test_submodules_importable(self) -> None:
        import scripts.environment_v3.composition  # noqa: F401
        import scripts.environment_v3.editor_contract  # noqa: F401
        import scripts.environment_v3.kit  # noqa: F401
        import scripts.environment_v3.reference_pack  # noqa: F401
        import scripts.environment_v3.semantics  # noqa: F401
        import scripts.environment_v3.stylepack  # noqa: F401
        import scripts.environment_v3.validation  # noqa: F401


if __name__ == "__main__":
    unittest.main()
