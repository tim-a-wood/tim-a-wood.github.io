from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import room_environment_system as envsys


class RoomEnvironmentSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects_root = self.root / "tools" / "2d-sprite-and-animation" / "projects-data"
        self.project_id = "project-alpha"
        self.project = {
            "project_id": self.project_id,
            "project_name": "Project Alpha",
            "art_direction": None,
            "room_layout": {
                "version": 1,
                "meta": {"project_id": self.project_id, "project_name": "Project Alpha"},
                "rooms": [
                    {
                        "id": "R1",
                        "name": "Vault",
                        "size": {"width": 1600, "height": 1200},
                        "global": {"x": 600, "y": 360},
                        "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
                        "platforms": [{"id": "R1-P1", "x": 224, "y": 960, "len": 22}],
                        "movingPlatforms": [],
                        "doors": [{"id": "R1-D1", "x": 160, "y": 960, "kind": "transition"}],
                        "keys": [],
                        "abilities": [],
                        "playerStart": {"x": 320, "y": 928},
                        "edgeLinks": [],
                        "removedEdges": [],
                    }
                ],
            },
        }
        self.saved = copy.deepcopy(self.project)
        self.events = []

        def load_project(project_id: str):
            if project_id != self.project_id:
                raise FileNotFoundError(project_id)
            return copy.deepcopy(self.saved)

        def save_project(project: dict):
            self.saved = copy.deepcopy(project)

        def append_history_event(project_id: str, event: dict):
            self.events.append((project_id, copy.deepcopy(event)))
            return {"project_id": project_id, "events": [event]}

        envsys.configure(
            PROJECTS_ROOT=self.projects_root,
            ROOT=self.root,
            load_project=load_project,
            save_project=save_project,
            now_iso=lambda: "2026-03-28T12:00:00Z",
            stable_hash=lambda *parts: "hash-" + "-".join(str(p) for p in parts)[:12],
            append_history_event=append_history_event,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_template_catalogs_exist(self):
        self.assertGreaterEqual(len(envsys.list_art_direction_templates()), 5)
        self.assertGreaterEqual(len(envsys.list_room_environment_archetypes()), 5)

    def test_update_project_art_direction_persists_and_invalidates_rooms(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "flooded-catacombs"})
        result = envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "flooded-catacombs", "locked": True, "frozen_concept_ids": ["art-direction-02"]},
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["art_direction"]["locked"])
        self.assertEqual(result["art_direction"]["frozen_concept_ids"], ["art-direction-02"])
        room = self.saved["room_layout"]["rooms"][0]
        self.assertEqual(room["environment"]["preview"]["status"], "outdated")

    def test_get_project_frozen_concept_candidates_and_defaults(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        candidates = envsys.list_project_frozen_concept_candidates(self.project_id)
        self.assertEqual(len(candidates), 3)
        current = envsys.get_project_art_direction(self.project_id)
        self.assertEqual(current["frozen_concept_ids"], ["art-direction-01"])
        self.assertEqual(current["frozen_concepts"][0]["label"], "World Keyframe")

    def test_generate_art_direction_concepts_creates_board(self):
        generated = envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "industrial-underworks"})
        self.assertTrue(generated["ok"])
        board = generated["art_direction"]["concept_board"]
        self.assertEqual(board["status"], "ready")
        self.assertEqual(len(board["images"]), 3)
        for item in board["images"]:
            rel_url = item["url"].lstrip("/")
            self.assertTrue((self.root / rel_url).exists())

    def test_adapt_and_build_spec(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        adapted = envsys.adapt_room_template(
            self.project_id,
            "R1",
            {"archetype_id": "shrine-chamber", "instruction": "Adapt this room to the locked style."},
        )
        self.assertTrue(adapted["draft_description"])
        spec = envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": adapted["draft_description"]},
        )
        self.assertTrue(spec["ok"])
        env = spec["environment"]
        self.assertIn("spec", env)
        self.assertIn("preview", env)
        self.assertTrue(env["tags"])
        self.assertIn("scene_schema", env["spec"])
        self.assertIn("set_dressing", env["spec"]["scene_schema"])
        self.assertIn("kit", env["spec"]["scene_schema"])

    def test_generate_and_approve_previews(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "overgrown-shrine", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A quiet shrine chamber with roots, filtered light, and a readable central route."},
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview = generated["environment"]["preview"]
        self.assertEqual(preview["render_level"], "level3")
        self.assertEqual(len(preview["images"]), 3)
        for item in preview["images"]:
            rel_url = item["url"].lstrip("/")
            self.assertTrue((self.root / rel_url).exists())
        approved = envsys.approve_room_environment_preview(
            self.project_id,
            "R1",
            {"preview_id": preview["images"][0]["preview_id"]},
        )
        self.assertEqual(
            approved["environment"]["preview"]["approved_image_id"],
            preview["images"][0]["preview_id"],
        )
        self.assertIsNotNone(approved["environment"]["preview"]["approved_palette"])
        self.assertEqual(approved["environment"]["runtime"]["status"], "ready")
        self.assertEqual(
            approved["environment"]["runtime"]["applied_preview_id"],
            preview["images"][0]["preview_id"],
        )
        self.assertIsNotNone(approved["environment"]["runtime"]["surface_palette"])
        asset_pack = envsys.generate_room_environment_asset_pack(
            self.project_id,
            "R1",
            {"preview_id": preview["images"][0]["preview_id"]},
        )
        self.assertEqual(asset_pack["environment"]["runtime"]["asset_pack"]["status"], "ready")
        for item in asset_pack["environment"]["runtime"]["asset_pack"]["assets"].values():
            rel_url = item["url"].lstrip("/")
            self.assertTrue((self.root / rel_url).exists())


if __name__ == "__main__":
    unittest.main()
