from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
            stable_hash=lambda *parts: "hash-" + hashlib.sha1("||".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12],
            append_history_event=append_history_event,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fake_ai_generate(self, output_path, prompt, refs, size, transparent):
        img = envsys.Image.new("RGBA", size, (40, 50, 60, 0 if transparent else 255))
        img.save(output_path)
        return True

    def _passing_runtime_review(self):
        return {
            "status": "pass",
            "review_mode": "mocked",
            "capture_issue": None,
            "screenshot_url": "/mock/runtime-review.png",
            "screenshot_path": "/mock/runtime-review.png",
            "metrics": {
                "center_clutter": 0.0,
                "center_upper_contrast": 0.02,
                "center_lower_contrast": 0.03,
                "left_right_balance": 0.0,
                "side_shell_definition": 0.04,
                "floor_background_separation": 0.1,
                "platform_top_readability": 0.1,
                "threshold_visibility": 0.1,
                "platform_sample_count": 1.0,
                "door_sample_count": 1.0,
            },
            "fail_reasons": [],
            "warning_reasons": [],
            "generated_at": "2026-03-28T12:00:00Z",
        }

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
        self.assertTrue(result["art_direction"]["biome_packs"])
        room = self.saved["room_layout"]["rooms"][0]
        self.assertEqual(room["environment"]["preview"]["status"], "outdated")

    def test_generate_biome_pack_visuals_requires_confirm(self):
        out = envsys.generate_biome_pack_visuals(self.project_id, {})
        self.assertFalse(out.get("ok"))
        self.assertIn("confirm_overwrite", str(out.get("error", "")))

    def test_generate_biome_pack_visuals_marks_templates_and_skips_refresh_overwrite(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate):
            out = envsys.generate_biome_pack_visuals(self.project_id, {"confirm_overwrite": True})
        self.assertTrue(out["ok"])
        self.assertTrue(out["used_ai"])
        for row in out["results"]:
            self.assertTrue(row.get("ok"), row)
        pack = out["art_direction"]["biome_packs"][0]
        for t in pack["template_library"]:
            self.assertTrue(str(t.get("biome_visual_generated_at") or "").strip())
            self.assertEqual(t.get("source_template_kind"), "gemini_biome")
        first_rel = pack["template_library"][0]["image_path"]
        path = self.projects_root / self.project_id / first_rel
        self.assertTrue(path.exists())
        marker = b"KEEP-BIOME-VISUAL"
        path.write_bytes(marker)
        envsys.get_project_art_direction(self.project_id)
        self.assertEqual(path.read_bytes(), marker)

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
        prompts = envsys.generate_room_environment_component_prompts(
            self.project_id,
            "R1",
            {"description": adapted["draft_description"]},
        )
        self.assertIn("floor", prompts["components"])
        spec = envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": adapted["draft_description"], "components": prompts["components"]},
        )
        self.assertTrue(spec["ok"])
        env = spec["environment"]
        self.assertIn("spec", env)
        self.assertIn("preview", env)
        self.assertTrue(env["tags"])
        self.assertIn("components", env["spec"])
        self.assertIn("component_schemas", env["spec"])
        self.assertIn("background", env["spec"]["components"])
        self.assertIn("background", env["spec"]["component_schemas"])
        self.assertIn("midground", env["spec"]["component_schemas"])
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
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            asset_pack = envsys.generate_room_environment_asset_pack(
                self.project_id,
                "R1",
                {"preview_id": preview["images"][0]["preview_id"]},
            )
        bespoke = asset_pack["environment"]["runtime"]["bespoke_asset_manifest"]
        self.assertEqual(bespoke["status"], "ready")
        self.assertFalse(bespoke["failed_assets"])
        self.assertTrue(bespoke["assets"])
        self.assertEqual(bespoke["schema_version"], 2)
        self.assertTrue(bespoke["required_slots"])
        self.assertTrue(bespoke["built_slots"])
        self.assertTrue(bespoke["slot_groups"])
        self.assertTrue(bespoke["schema_validation"]["valid"])
        self.assertEqual(bespoke["runtime_review"]["status"], "pass")
        self.assertTrue(bespoke["runtime_review"]["screenshot_url"])
        self.assertEqual(asset_pack["environment"]["runtime"]["status"], "ready")
        self.assertTrue(bespoke["used_ai"])

    def test_layout_change_marks_only_layout_aware_assets_stale(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "industrial-underworks", "locked": True})
        spec_result = envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A grim machinery room with readable catwalks, pressure pipes, and deep utility shadows."},
        )
        env = spec_result["environment"]
        self.assertEqual(env["spec"]["scene_schema"]["kit"]["shell_family"], "industrial_underworks")
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})

        self.saved["room_layout"]["rooms"][0]["platforms"][0]["len"] = 28
        room = envsys._find_room(self.saved, "R1")
        stale = room["environment"]["runtime"]["asset_pack"]["stale_components"]
        self.assertEqual(stale, [])

    def test_generate_bespoke_assets_ready_when_generator_is_mocked(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            result = envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})
        bespoke = result["environment"]["runtime"]["bespoke_asset_manifest"]
        self.assertEqual(bespoke["status"], "ready")
        self.assertEqual(result["environment"]["runtime"]["status"], "ready")
        self.assertGreaterEqual(len(bespoke["assets"]), 4)

    def test_runtime_review_blocks_flat_assets_even_when_generation_succeeds(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])):
            result = envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})
        bespoke = result["environment"]["runtime"]["bespoke_asset_manifest"]
        self.assertEqual(bespoke["status"], "failed")
        self.assertEqual(result["environment"]["runtime"]["status"], "blocked")
        self.assertEqual(bespoke["runtime_review"]["status"], "fail")
        self.assertTrue(bespoke["runtime_review"]["fail_reasons"])

    def test_generate_bespoke_assets_block_room_when_template_render_fails(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", return_value=False):
            result = envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})
        bespoke = result["environment"]["runtime"]["bespoke_asset_manifest"]
        self.assertEqual(bespoke["status"], "failed")
        self.assertTrue(bespoke["failed_assets"])
        self.assertEqual(result["environment"]["runtime"]["status"], "blocked")

    def test_bespoke_prompt_rejects_focal_shrine_carryover_for_background(self):
        prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Quiet ruined hall", "negative_direction": "busy focal shrine scenes"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A hall with a clear route.",
                "component_schemas": {"background": envsys._default_component_schema("background", "A hall with a clear route.")}
            },
            {
                "component_type": "background_far_plate",
                "schema_key": "background",
                "target_dimensions": {"width": 1600, "height": 1200},
                "orientation": "full",
                "tile_mode": "stretch",
                "border_treatment": "full_frame",
                "protected_zones": [{"type": "center_lane", "x": 400, "y": 0, "width": 800, "height": 1200}],
            },
            {"variant_family": "background", "orientation": "full"},
        )
        self.assertIn("far-depth hall shell", prompt)
        self.assertIn("reject carryover of any altar", prompt)
        self.assertIn("open center lane", prompt)
        self.assertIn("not scenic concept art with gameplay layered on top", prompt)

    def test_bespoke_prompt_requires_side_only_midground_and_structural_floor(self):
        midground_prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Quiet ruined hall", "negative_direction": "busy focal shrine scenes"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A hall with a clear route.",
                "component_schemas": {
                    "midground": envsys._default_component_schema("midground", "A hall with a clear route."),
                    "floor": envsys._default_component_schema("floor", "A hall with a clear route."),
                },
            },
            {
                "component_type": "midground_side_frame",
                "schema_key": "midground",
                "target_dimensions": {"width": 1600, "height": 1200},
                "orientation": "full",
                "tile_mode": "stretch",
                "border_treatment": "side_only",
                "protected_zones": [{"type": "main_route", "x": 480, "y": 0, "width": 640, "height": 1200}],
            },
            {"variant_family": "midground", "orientation": "full"},
        )
        floor_prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Quiet ruined hall", "negative_direction": "busy focal shrine scenes"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A hall with a clear route.",
                "component_schemas": {"floor": envsys._default_component_schema("floor", "A hall with a clear route.")},
            },
            {
                "component_type": "main_floor_top",
                "schema_key": "floor",
                "target_dimensions": {"width": 704, "height": 96},
                "orientation": "horizontal",
                "tile_mode": "tile_x",
                "border_treatment": "top_lip_priority",
                "protected_zones": [{"type": "platform_top", "x": 224, "y": 942, "width": 704, "height": 22}],
            },
            {"variant_family": "floor", "orientation": "horizontal"},
        )
        self.assertIn("center fully open and calm", midground_prompt)
        self.assertIn("Restrict arches, columns, and side mass to the left and right edges", midground_prompt)
        self.assertIn("same room shell as the walls and background", floor_prompt)
        self.assertIn("same stone family", floor_prompt)
        self.assertIn("Do not introduce a giant circular ritual graphic", floor_prompt)

    def test_component_reference_guides_sanitize_scenic_slots_and_crop_structural_slots(self):
        refs_root = self.root / "refs"
        template = self.root / "template.png"
        preview = self.root / "preview.png"
        frozen_a = self.root / "frozen-a.png"
        frozen_b = self.root / "frozen-b.png"
        envsys.Image.new("RGBA", (160, 120), (120, 140, 155, 255)).save(template)
        envsys.Image.new("RGBA", (160, 120), (90, 105, 118, 255)).save(preview)
        envsys.Image.new("RGBA", (160, 120), (60, 70, 80, 255)).save(frozen_a)
        envsys.Image.new("RGBA", (160, 120), (50, 60, 70, 255)).save(frozen_b)

        background_refs = envsys._bespoke_reference_images_for_component(
            "background_far_plate",
            template,
            preview,
            [frozen_a, frozen_b],
            refs_root,
            (160, 120),
            False,
        )
        midground_refs = envsys._bespoke_reference_images_for_component(
            "midground_side_frame",
            template,
            preview,
            [frozen_a],
            refs_root,
            (160, 120),
            True,
        )
        floor_refs = envsys._bespoke_reference_images_for_component(
            "main_floor_top",
            template,
            preview,
            [frozen_a],
            refs_root,
            (128, 48),
            False,
        )
        door_refs = envsys._bespoke_reference_images_for_component(
            "door_frame",
            template,
            preview,
            [frozen_a],
            refs_root,
            (96, 144),
            True,
        )

        self.assertNotIn(preview, background_refs)
        self.assertTrue(background_refs[0].exists())
        self.assertEqual(len(background_refs), 1)
        self.assertLess(envsys._region_alpha_ratio(midground_refs[0], (0.36, 0.18, 0.64, 0.82)), 0.15)
        self.assertEqual(len(floor_refs), 1)
        self.assertNotEqual(floor_refs[0], template)
        self.assertTrue(floor_refs[0].exists())
        self.assertEqual(len(door_refs), 1)
        self.assertNotEqual(door_refs[0], template)

    def test_postprocess_component_for_validation_salvages_scenic_readability(self):
        background = self.root / "background-hot.png"
        midground = self.root / "midground-clutter.png"
        envsys.Image.new("RGBA", (160, 120), (200, 205, 210, 255)).save(background)
        envsys.Image.new("RGBA", (160, 120), (40, 50, 60, 255)).save(midground)

        bg_changed = envsys._postprocess_component_for_validation(background, "background_far_plate", ["center_lane_too_hot"], 0)
        mg_changed = envsys._postprocess_component_for_validation(midground, "midground_side_frame", ["midground_center_clutter"], 0)

        self.assertTrue(bg_changed)
        self.assertTrue(mg_changed)
        self.assertLess(
            envsys._region_luminance(background, (0.34, 0.22, 0.66, 0.78)),
            190,
        )
        self.assertLess(envsys._region_alpha_ratio(midground, (0.36, 0.18, 0.64, 0.82)), 0.15)

    def test_midground_template_family_check_uses_edge_similarity(self):
        template = self.root / "midground-template.png"
        candidate = self.root / "midground-candidate.png"
        base = envsys.Image.new("RGBA", (160, 120), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(base)
        draw.rectangle((0, 0, 28, 119), fill=(70, 80, 90, 255))
        draw.rectangle((132, 0, 159, 119), fill=(70, 80, 90, 255))
        draw.rectangle((42, 8, 118, 110), fill=(95, 110, 120, 160))
        base.save(template)
        edge_matched = envsys.Image.new("RGBA", (160, 120), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(edge_matched)
        draw.rectangle((0, 0, 28, 119), fill=(70, 80, 90, 255))
        draw.rectangle((132, 0, 159, 119), fill=(70, 80, 90, 255))
        edge_matched.save(candidate)

        valid, errors = envsys._validate_bespoke_component(candidate, "midground_side_frame", (160, 120), "alpha", template)
        self.assertTrue(valid)
        self.assertNotIn("template_family_drift", errors)

    def test_midground_validation_flags_hot_inner_edges(self):
        template = self.root / "midground-template-hot.png"
        candidate = self.root / "midground-candidate-hot.png"
        envsys.Image.new("RGBA", (160, 120), (0, 0, 0, 0)).save(template)
        image = envsys.Image.new("RGBA", (160, 120), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((14, 10, 28, 110), fill=(255, 255, 255, 255))
        draw.rectangle((132, 10, 146, 110), fill=(255, 255, 255, 255))
        image.save(candidate)

        valid, errors = envsys._validate_bespoke_component(candidate, "midground_side_frame", (160, 120), "alpha", template)
        self.assertFalse(valid)
        self.assertIn("midground_inner_edge_hot", errors)

    def test_background_validation_flags_low_shell_definition(self):
        template = self.root / "background-template-low.png"
        candidate = self.root / "background-candidate-low.png"
        envsys.Image.new("RGBA", (160, 120), (70, 80, 90, 255)).save(template)
        envsys.Image.new("RGBA", (160, 120), (74, 84, 94, 255)).save(candidate)

        valid, errors = envsys._validate_bespoke_component(candidate, "background_far_plate", (160, 120), "opaque", template)
        self.assertFalse(valid)
        self.assertIn("background_shell_definition_low", errors)

    def test_runtime_review_blocks_over_suppressed_shell_reads(self):
        review_root = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review"
        review_root.mkdir(parents=True, exist_ok=True)
        screenshot = review_root / "runtime-review.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (64, 72, 80, 255))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 240, 1200), fill=(34, 40, 48, 255))
        draw.rectangle((1360, 0, 1600, 1200), fill=(34, 40, 48, 255))
        draw.rectangle((280, 160, 1320, 1020), fill=(68, 76, 84, 255))
        draw.rectangle((240, 890, 1360, 1020), fill=(82, 90, 98, 255))
        image.save(screenshot)

        with mock.patch.object(envsys, "_capture_runtime_review_screenshot", return_value=("mocked", None)):
            review = envsys._run_runtime_review(self.saved, self.project_id, "R1", {})

        self.assertEqual(review["status"], "fail")
        self.assertIn("room_shell_readability_low", review["fail_reasons"])


if __name__ == "__main__":
    unittest.main()
