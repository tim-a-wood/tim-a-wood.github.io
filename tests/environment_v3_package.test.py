"""Tests for staged environment_v3 package (persistence + reference pack)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.environment_v3 import persistence, reference_pack
from scripts.environment_v3.persistence import (
    ARTIFACT_REFERENCE_PACK,
    ARTIFACT_STYLEPACK,
    DERIVED_SUBDIR,
    artifact_path,
    hydrate_v3_staged_documents,
    persist_v3_staged_documents,
    staged_artifact_root,
)


class EnvironmentV3PackageTests(unittest.TestCase):
    def test_staged_artifact_paths(self) -> None:
        projects = Path("/tmp") / "proj-root"
        pid, rid = "p1", "R1"
        root = staged_artifact_root(projects, pid, rid)
        self.assertEqual(
            root,
            projects / pid / "room_environment_assets" / rid / DERIVED_SUBDIR,
        )
        self.assertEqual(
            artifact_path(projects, pid, rid, "stylepack"),
            root / ARTIFACT_STYLEPACK,
        )

    def test_persist_and_hydrate_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_id, room_id = "proj-a", "R9"
            env: dict = {
                "reference_pack": reference_pack.build_reference_pack(
                    reference_pack_id="rp-1",
                    notes="test",
                    status="draft",
                ),
                "stylepack": {"stylepack_id": "sp-1", "summary": "x", "locked": False},
            }
            written = persist_v3_staged_documents(root, project_id, room_id, env)
            kinds = {k for k, _ in written}
            self.assertIn("reference_pack", kinds)
            self.assertIn("stylepack", kinds)
            ref_path = artifact_path(root, project_id, room_id, "reference_pack")
            self.assertTrue(ref_path.is_file())
            fresh: dict = {}
            loaded = hydrate_v3_staged_documents(root, project_id, room_id, fresh)
            self.assertIn("reference_pack", loaded)
            self.assertEqual(fresh["reference_pack"]["reference_pack_id"], "rp-1")

    def test_merge_reference_pack(self) -> None:
        base = reference_pack.build_reference_pack(notes="a")
        out = reference_pack.merge_reference_pack(
            base,
            {"notes": "b", "canonical_selection": ["u1"], "uploads": [{"upload_id": "u1"}]},
        )
        self.assertEqual(out["notes"], "b")
        self.assertEqual(out["canonical_selection"], ["u1"])
        self.assertEqual(out["summary"]["upload_count"], 1)
        self.assertEqual(out["summary"]["canonical_count"], 1)

    def test_submodules_importable(self) -> None:
        import scripts.environment_v3.composition  # noqa: F401
        import scripts.environment_v3.editor_contract  # noqa: F401
        import scripts.environment_v3.kit  # noqa: F401
        import scripts.environment_v3.semantics  # noqa: F401
        import scripts.environment_v3.stylepack  # noqa: F401
        import scripts.environment_v3.validation  # noqa: F401


if __name__ == "__main__":
    unittest.main()
