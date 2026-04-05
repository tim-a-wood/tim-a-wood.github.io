"""Smoke and semantics coverage for staged environment_v3 package."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.environment_v3 import composition, persistence, validation
from scripts.environment_v3 import editor_contract, kit, semantics
from scripts.environment_v3.persistence import (
    ARTIFACT_STYLEPACK,
    DERIVED_SUBDIR,
    derived_artifact_path,
    derived_room_dir,
)


class EnvironmentV3PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.layout_data = json.loads((ROOT / "room-layout-data.json").read_text(encoding="utf-8"))
        cls.fixture = json.loads((ROOT / "tests/fixtures/room_environment_v3/room_semantics_fixture.json").read_text(encoding="utf-8"))
        cls.rooms = {room["id"]: room for room in cls.layout_data.get("rooms", [])}

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

    def test_r11_zero_platform_shaft_semantics(self) -> None:
        room = self.rooms["R11"]
        doc = semantics.derive_room_semantics(room)
        self.assertEqual(doc["room_role"], "traversal_shaft")
        self.assertEqual(doc["summary"]["top_count"], 0)
        self.assertEqual(doc["summary"]["cavity_count"], 0)
        self.assertGreaterEqual(doc["summary"]["opening_count"], 2)
        self.assertTrue(all(item["source"] in {"edge_link", "removed_edge"} for item in doc["opening_records"]))
        self.assertEqual(doc["overlay_geometry"]["platform_tops"], [])
        self.assertEqual(doc["background_cavities"], [])

    def test_r2_hub_semantics_captures_door_and_moving_platform_truth(self) -> None:
        room = self.rooms["R2"]
        doc = semantics.derive_room_semantics(room)
        self.assertEqual(doc["room_role"], "hub")
        self.assertEqual(doc["summary"]["top_count"], len(room["platforms"]) + len(room["movingPlatforms"]))
        self.assertGreaterEqual(doc["summary"]["opening_count"], len(room["doors"]))
        opening_types = [item["opening_type"] for item in doc["opening_records"]]
        self.assertEqual(opening_types.count("door"), len(room["doors"]))
        zone_types = {zone["zone_type"] for zone in doc["gameplay_exclusion_zones"]}
        self.assertIn("moving_platform_path", zone_types)
        self.assertIn("platform_top", zone_types)
        self.assertIn("openings", doc["overlay_geometry"])
        self.assertIn("moving_platform_tops", doc["overlay_geometry"])

    def test_r7_stacked_platform_shaft_has_vertical_faces_and_thresholds(self) -> None:
        room = self.rooms["R7"]
        doc = semantics.derive_room_semantics(room)
        self.assertEqual(doc["room_role"], "traversal_shaft")
        self.assertEqual(doc["summary"]["top_count"], len(room["platforms"]))
        self.assertGreaterEqual(doc["summary"]["vertical_face_count"], len(room["platforms"]) * 2)
        self.assertGreaterEqual(doc["summary"]["opening_count"], len(room["doors"]))
        self.assertTrue(doc["overlay_geometry"]["platform_undersides"])
        self.assertTrue(doc["overlay_geometry"]["vertical_faces"])

    def test_semantics_ignore_non_authority_fields(self) -> None:
        room = json.loads(json.dumps(self.rooms["R2"]))
        baseline = semantics.derive_room_semantics(room)
        room["global"] = {"x": 99999, "y": -99999}
        room["environment"] = {"themeId": "ignore-me", "preview": {"images": ["fake.png"]}}
        mutated = semantics.derive_room_semantics(room)
        self.assertEqual(mutated, baseline)

    def test_results_payload_surfaces_semantics_counts_and_overlay_keys(self) -> None:
        room = self.rooms["R2"]
        semantics_doc = semantics.derive_room_semantics(room)
        payload = editor_contract.build_results_payload(
            {"environment_pipeline_version": "v3"},
            semantics_doc=semantics_doc,
        )
        self.assertEqual(payload["semantics"]["status"], "ready")
        self.assertEqual(payload["semantics"]["counts"]["top_count"], len(room["platforms"]) + len(room["movingPlatforms"]))
        self.assertIn("openings", payload["semantics"]["overlay_keys"])
        self.assertIn("gameplay_exclusion_zones", payload["semantics"]["overlay_keys"])
        self.assertEqual(payload["semantics"]["room_role"], "hub")
        self.assertTrue(payload["semantics"]["overlay_geometry"]["room_polygon"])
        self.assertTrue(payload["semantics"]["truth_checks"])

    def test_environment_kit_taxonomy_boundaries_and_counts(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R2"])
        plan = [
            {"slot_id": "slot-wall", "component_type": "wall_module_left", "schema_key": "walls", "slot_group": "walls", "target_dimensions": {"width": 128, "height": 512}, "local_geometry": {"anchor": "left_wall"}, "tile_mode": "tile"},
            {"slot_id": "slot-floor", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "target_dimensions": {"width": 320, "height": 32}, "local_geometry": {"anchor": "floor_top"}, "tile_mode": "stretch"},
            {"slot_id": "slot-bg", "component_type": "background_far_plate", "schema_key": "background", "slot_group": "background", "target_dimensions": {"width": 1600, "height": 1200}, "local_geometry": {"anchor": "room_center"}, "tile_mode": "stretch"},
            {"slot_id": "slot-decor", "component_type": "banner_cluster", "schema_key": "decor", "slot_group": "decor", "target_dimensions": {"width": 96, "height": 192}, "local_geometry": {"anchor": "decor_safe"}, "tile_mode": "stretch"},
        ]
        doc = kit.build_environment_kit("stylepack-r2", semantics_doc, plan=plan)
        classes = {entry["component_type"]: entry["component_class"] for entry in doc["entries"]}
        self.assertEqual(classes["wall_module_left"], "structural")
        self.assertEqual(classes["main_floor_top"], "structural")
        self.assertEqual(classes["background_far_plate"], "background")
        self.assertEqual(classes["banner_cluster"], "decor")
        self.assertEqual(doc["summary"]["structural_count"], 2)
        self.assertEqual(doc["summary"]["background_count"], 1)
        self.assertEqual(doc["summary"]["decor_count"], 1)
        self.assertEqual(doc["summary"]["component_count_by_type"]["wall_module_left"], 1)
        self.assertEqual(doc["component_count_by_type"]["background_far_plate"], 1)
        self.assertEqual(doc["source"]["semantic_source"]["room_role"], semantics_doc["room_role"])
        self.assertEqual(doc["entries"][0]["structural_slice"]["semantics_room_role"], semantics_doc["room_role"])
        self.assertEqual(doc["validation_errors"], [])

    def test_environment_kit_is_deterministic_for_same_inputs(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R7"])
        plan = [
            {"slot_id": "slot-1", "component_type": "ceiling_band", "schema_key": "ceiling", "slot_group": "ceiling", "target_dimensions": {"width": 1664, "height": 192}, "local_geometry": {"anchor": "ceiling"}, "tile_mode": "stretch"},
            {"slot_id": "slot-2", "component_type": "door_frame", "schema_key": "doors", "slot_group": "doors", "target_dimensions": {"width": 96, "height": 176}, "local_geometry": {"anchor": "threshold"}, "tile_mode": "stretch"},
        ]
        first = kit.build_environment_kit("stylepack-r7", semantics_doc, plan=plan)
        second = kit.build_environment_kit("stylepack-r7", semantics_doc, plan=list(reversed(plan)))
        self.assertEqual(first, second)

    def test_results_payload_surfaces_kit_counts_and_validation(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R2"])
        plan = [
            {"slot_id": "slot-floor", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "target_dimensions": {"width": 320, "height": 32}, "local_geometry": {"anchor": "floor_top"}, "tile_mode": "stretch"},
            {"slot_id": "slot-bg", "component_type": "background_far_plate", "schema_key": "background", "slot_group": "background", "target_dimensions": {"width": 1600, "height": 1200}, "local_geometry": {"anchor": "room_center"}, "tile_mode": "stretch"},
        ]
        kit_doc = kit.build_environment_kit("stylepack-r2", semantics_doc, plan=plan)
        payload = editor_contract.build_results_payload(
            {"environment_pipeline_version": "v3"},
            semantics_doc=semantics_doc,
            kit_doc=kit_doc,
        )
        self.assertEqual(payload["kit"]["summary"]["structural_count"], 1)
        self.assertEqual(payload["kit"]["summary"]["background_count"], 1)
        self.assertEqual(payload["kit"]["component_count_by_type"]["main_floor_top"], 1)
        self.assertEqual(payload["kit"]["taxonomy"]["classes"]["structural"]["default_readability_impact"], "high")
        self.assertEqual(payload["kit"]["source"]["semantic_source"]["room_id"], semantics_doc["room_id"])
        self.assertEqual(payload["kit"]["validation_errors"], [])

    def test_environment_manifest_honors_pass_precedence_and_midground_background(self) -> None:
        plan = [
            {"slot_id": "decor-banner", "component_type": "banner_cluster", "schema_key": "decor", "slot_group": "decor", "placement": {"x": 900, "y": 240}, "target_dimensions": {"width": 96, "height": 192}},
            {"slot_id": "mid-frame", "component_type": "midground_side_frame", "schema_key": "midground", "slot_group": "midground", "placement": {"x": 800, "y": 1200}, "target_dimensions": {"width": 1600, "height": 1200}},
            {"slot_id": "floor-top", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "placement": {"x": 128, "y": 928}, "target_dimensions": {"width": 512, "height": 96}},
            {"slot_id": "wall-left", "component_type": "wall_module_left", "schema_key": "walls", "slot_group": "walls", "placement": {"x": 0, "y": 0}, "target_dimensions": {"width": 320, "height": 960}},
        ]
        manifest = composition.build_environment_manifest(self.rooms["R2"], "stylepack-r2", "seed-r2", plan=plan)
        self.assertEqual(manifest["layer_order"], ["structural", "background", "decor"])
        self.assertEqual([item["slot_id"] for item in manifest["layers"]["structural"]], ["wall-left", "floor-top"])
        self.assertEqual([item["slot_id"] for item in manifest["layers"]["background"]], ["mid-frame"])
        self.assertEqual([item["slot_id"] for item in manifest["layers"]["decor"]], ["decor-banner"])
        self.assertEqual(manifest["passes"]["sequence"][0]["pass_name"], "structural")
        self.assertEqual(manifest["passes"]["summaries"]["background"]["component_types"]["midground_side_frame"], 1)
        self.assertEqual(manifest["seed_source"], "provided")
        self.assertEqual(manifest["placement_summary"]["total_count"], 4)
        self.assertEqual(manifest["placement_summary"]["layers"]["structural"]["slot_ids"], ["wall-left", "floor-top"])
        self.assertEqual(manifest["generation_metadata"]["placement_count"], 4)
        self.assertEqual(manifest["generation_metadata"]["plan_slot_count"], 4)

    def test_environment_manifest_is_deterministic_for_same_seed_and_plan(self) -> None:
        plan = [
            {"slot_id": "door-b", "component_type": "door_frame", "schema_key": "doors", "slot_group": "doors", "placement": {"x": 1536, "y": 704}, "target_dimensions": {"width": 192, "height": 288}},
            {"slot_id": "bg-a", "component_type": "background_far_plate", "schema_key": "background", "slot_group": "background", "placement": {"x": 800, "y": 1200}, "target_dimensions": {"width": 1600, "height": 1200}},
            {"slot_id": "floor-a", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "placement": {"x": 128, "y": 928}, "target_dimensions": {"width": 512, "height": 96}},
        ]
        first = composition.build_environment_manifest(self.rooms["R2"], "stylepack-r2", "seed-r2", plan=plan)
        second = composition.build_environment_manifest(self.rooms["R2"], "stylepack-r2", "seed-r2", plan=list(reversed(plan)))
        self.assertEqual(first, second)
        self.assertTrue(first["deterministic_replay"]["replay_key"])
        self.assertEqual(first["deterministic_replay"]["ordering_rule"], "pass_precedence_then_group_then_position_then_slot_id")

    def test_results_payload_surfaces_manifest_passes_and_replay_metadata(self) -> None:
        plan = [
            {"slot_id": "floor-a", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "placement": {"x": 128, "y": 928}, "target_dimensions": {"width": 512, "height": 96}},
            {"slot_id": "bg-a", "component_type": "background_far_plate", "schema_key": "background", "slot_group": "background", "placement": {"x": 800, "y": 1200}, "target_dimensions": {"width": 1600, "height": 1200}},
        ]
        manifest = composition.build_environment_manifest(self.rooms["R2"], "stylepack-r2", "seed-r2", plan=plan)
        payload = editor_contract.build_results_payload(
            {"environment_pipeline_version": "v3"},
            manifest_doc=manifest,
        )
        self.assertEqual(payload["manifest"]["status"], "ready")
        self.assertEqual(payload["manifest"]["layer_order"], ["structural", "background", "decor"])
        self.assertEqual(payload["manifest"]["passes"]["sequence"][1]["pass_name"], "background")
        self.assertEqual(payload["manifest"]["deterministic_replay"]["seed"], "seed-r2")
        self.assertEqual(payload["manifest"]["placement_summary"]["layers"]["background"]["count"], 1)
        self.assertEqual(payload["manifest"]["generation_metadata"]["background_count"], 1)

    def test_environment_manifest_persistence_round_trip(self) -> None:
        plan = [
            {"slot_id": "floor-a", "component_type": "main_floor_top", "schema_key": "floor", "slot_group": "floor", "placement": {"x": 128, "y": 928}, "target_dimensions": {"width": 512, "height": 96}},
            {"slot_id": "bg-a", "component_type": "background_far_plate", "schema_key": "background", "slot_group": "background", "placement": {"x": 800, "y": 1200}, "target_dimensions": {"width": 1600, "height": 1200}},
        ]
        manifest = composition.build_environment_manifest(self.rooms["R2"], "stylepack-r2", "seed-r2", plan=plan)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            persistence.save_artifact(root, "proj-1", "R2", "environment_manifest", manifest)
            loaded = persistence.load_artifact(root, "proj-1", "R2", "environment_manifest")
        self.assertEqual(loaded, manifest)

    def test_validation_report_flags_geometry_blockers_and_highlights(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R2"])
        manifest = composition.build_environment_manifest(
            self.rooms["R2"],
            "stylepack-r2",
            "seed-r2",
            plan=[
                {
                    "slot_id": "bad-decor",
                    "component_type": "banner_cluster",
                    "schema_key": "decor",
                    "slot_group": "decor",
                    "placement": {"x": 120, "y": 407, "display_width": 96, "display_height": 96, "origin_x": 0, "origin_y": 0},
                    "target_dimensions": {"width": 96, "height": 96},
                }
            ],
        )
        report = validation.build_validation_report(
            review_state={"runtime_review": {"status": "idle", "screenshot_url": None}},
            assembly_plan={"planner_coverage_summary": {"missing_slots": ["door_slots_missing"], "blockers": ["door_slots_missing"]}},
            manifest=manifest,
            semantics_doc=semantics_doc,
        )
        blocker_codes = {item["code"] for item in report["findings"]["blockers"]}
        self.assertIn("door_slots_missing", blocker_codes)
        self.assertIn("wrong_surface_placement", blocker_codes)
        self.assertIn("gameplay_zone_intrusion", blocker_codes)
        self.assertEqual(report["geometry_safety"]["status"], "blocked")
        self.assertTrue(report["validation_highlights"]["wrong_surface_placements"])
        self.assertTrue(report["validation_highlights"]["gameplay_intrusions"])
        self.assertGreaterEqual(report["blocker_count"], 3)

    def test_validation_report_surfaces_warning_and_info_levels(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R2"])
        manifest = composition.build_environment_manifest(
            self.rooms["R2"],
            "stylepack-r2",
            "seed-r2",
            plan=[
                {
                    "slot_id": "floor-top",
                    "component_type": "main_floor_top",
                    "schema_key": "floor",
                    "slot_group": "floor",
                    "placement": {"x": 128, "y": 928, "display_width": 512, "display_height": 96, "origin_x": 0, "origin_y": 0.75},
                    "target_dimensions": {"width": 512, "height": 96},
                },
                {
                    "slot_id": "bg-a",
                    "component_type": "background_far_plate",
                    "schema_key": "background",
                    "slot_group": "background",
                    "placement": {"x": 800, "y": 1200, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 1},
                    "target_dimensions": {"width": 1600, "height": 1200},
                },
                {
                    "slot_id": "bg-b",
                    "component_type": "midground_side_frame",
                    "schema_key": "midground",
                    "slot_group": "midground",
                    "placement": {"x": 800, "y": 1200, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 1},
                    "target_dimensions": {"width": 1600, "height": 1200},
                },
            ],
            validation_flags=["style_drift_warning"],
        )
        report = validation.build_validation_report(
            review_state={"runtime_review": {"status": "pass", "screenshot_url": "/tmp/runtime.png", "review_mode": "headless_browser"}},
            assembly_plan={"planner_coverage_summary": {"missing_slots": [], "blockers": []}},
            manifest=manifest,
            semantics_doc=semantics_doc,
        )
        warning_codes = {item["code"] for item in report["findings"]["warnings"]}
        info_codes = {item["code"] for item in report["findings"]["info"]}
        self.assertIn("ledge_clarity_at_risk", warning_codes)
        self.assertIn("background_dominance_risk", warning_codes)
        self.assertIn("style_drift_warning", warning_codes)
        self.assertIn("visual_validation_backed_by_screenshot", info_codes)
        self.assertEqual(report["visual_consistency"]["status"], "pass")

    def test_results_payload_surfaces_validation_counts_and_findings(self) -> None:
        semantics_doc = semantics.derive_room_semantics(self.rooms["R2"])
        manifest = composition.build_environment_manifest(
            self.rooms["R2"],
            "stylepack-r2",
            "seed-r2",
            plan=[],
        )
        validation_doc = validation.build_validation_report(
            review_state={"runtime_review": {"status": "idle", "screenshot_url": None}},
            assembly_plan={"planner_coverage_summary": {"missing_slots": ["platform_slots_missing"], "blockers": ["platform_slots_missing"]}},
            manifest=manifest,
            semantics_doc=semantics_doc,
        )
        payload = editor_contract.build_results_payload(
            {"environment_pipeline_version": "v3"},
            validation_doc=validation_doc,
        )
        self.assertEqual(payload["validation"]["status"], "ready")
        self.assertGreaterEqual(payload["validation"]["blocker_count"], 2)
        self.assertTrue(payload["validation"]["findings"])
        self.assertIn("unresolved_surfaces", payload["validation"]["validation_highlights"])
        self.assertEqual(payload["validation"]["blockers"][0]["severity"], "blocker")


if __name__ == "__main__":
    unittest.main()
