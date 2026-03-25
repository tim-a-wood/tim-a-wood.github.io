import http.client
import base64
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from PIL import Image, ImageDraw

from scripts import sprite_workbench_server as sw
from scripts import pixellab_client as pl


class SpriteWorkbenchTests(unittest.TestCase):
    FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "sprite_workbench"

    def create_manual_concept_asset(self, path: Path):
        image = Image.new("RGBA", sw.CONCEPT_CANVAS, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((250, 80, 390, 220), fill=(219, 198, 172, 255))
        draw.rectangle((270, 210, 370, 420), fill=(58, 73, 92, 255))
        draw.rectangle((310, 240, 430, 270), fill=(142, 103, 77, 255))
        draw.rectangle((220, 235, 300, 260), fill=(96, 120, 140, 255))
        draw.rectangle((285, 420, 325, 675), fill=(78, 92, 110, 255))
        draw.rectangle((325, 420, 365, 675), fill=(78, 92, 110, 255))
        draw.rectangle((275, 665, 335, 720), fill=(120, 84, 66, 255))
        draw.rectangle((325, 665, 385, 720), fill=(120, 84, 66, 255))
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    def create_logo_and_halo_asset(self, path: Path):
        image = Image.new("RGBA", sw.CONCEPT_CANVAS, (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((250, 80, 390, 220), fill=(219, 198, 172, 255))
        draw.rectangle((270, 210, 370, 420), fill=(58, 73, 92, 255))
        draw.rectangle((310, 240, 430, 270), fill=(142, 103, 77, 255))
        draw.rectangle((220, 235, 300, 260), fill=(96, 120, 140, 255))
        draw.rectangle((285, 420, 325, 675), fill=(78, 92, 110, 255))
        draw.rectangle((325, 420, 365, 675), fill=(78, 92, 110, 255))
        draw.rectangle((275, 665, 335, 720), fill=(120, 84, 66, 255))
        draw.rectangle((325, 665, 385, 720), fill=(120, 84, 66, 255))
        draw.rectangle((24, 24, 86, 50), fill=(24, 24, 24, 255))
        draw.rectangle((0, 0, sw.CONCEPT_CANVAS[0] - 1, sw.CONCEPT_CANVAS[1] - 1), outline=(255, 255, 255, 255), width=1)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    def create_subject_halo_asset(self, path: Path):
        base_path = self.create_manual_concept_asset(path)
        image = Image.open(base_path).convert("RGBA")
        mask = sw.detect_mask(image)
        ring = Image.new("L", image.size, 0)
        dilated = sw.dilate_mask(mask, 1)
        ring_pixels = ring.load()
        dilated_pixels = dilated.load()
        mask_pixels = sw.normalize_mask(mask).load()
        for y in range(image.size[1]):
            for x in range(image.size[0]):
                if dilated_pixels[x, y] > 0 and mask_pixels[x, y] <= 0:
                    ring_pixels[x, y] = 255
        draw = ImageDraw.Draw(image)
        for y in range(image.size[1]):
            for x in range(image.size[0]):
                if ring_pixels[x, y] > 0:
                    draw.point((x, y), fill=(235, 235, 235, 255))
        image.save(path)
        return path

    def create_external_bundle_assets(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        spritesheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(spritesheet)
        draw.rectangle((4, 4, 28, 28), fill=(180, 120, 90, 255))
        draw.rectangle((36, 4, 60, 28), fill=(90, 140, 200, 255))
        spritesheet_path = root / "spritesheet.png"
        spritesheet.save(spritesheet_path)
        atlas_path = root / "atlas.json"
        atlas_path.write_text(json.dumps({
            "image": "spritesheet.png",
            "frames": {
                "idle_00.png": {"x": 0, "y": 0, "w": 32, "h": 32},
                "walk_00.png": {"x": 32, "y": 0, "w": 32, "h": 32},
            },
        }), encoding="utf-8")
        animations_path = root / "animations.json"
        animations_path.write_text(json.dumps({
            "idle": {"fps": 8, "loop": True, "frame_count": 1, "frames": ["idle_00.png"]},
            "walk": {"fps": 10, "loop": True, "frame_count": 1, "frames": ["walk_00.png"]},
        }), encoding="utf-8")
        preview_path = root / "preview.gif"
        spritesheet.crop((0, 0, 32, 32)).save(
            preview_path,
            save_all=True,
            append_images=[spritesheet.crop((32, 0, 64, 32))],
            duration=[120, 120],
            loop=0,
        )
        return {
            "spritesheet": spritesheet_path,
            "atlas": atlas_path,
            "animations": animations_path,
            "preview_gif": preview_path,
        }

    def import_valid_manual_concept(self, project_id: str, *, import_mode: str = "local_path"):
        prompt = sw.generate_initial_prompt(project_id)
        with patch.object(sw, "run_gemini_concept_validation", return_value={
            "decision": "valid",
            "summary": "Extraction-ready after safe normalization.",
            "feedback": "Ready to continue.",
            "improved_gemini_prompt": None,
            "master_pose_ready": True,
            "technical_requirements_ok": True,
            "response_id": "resp_valid",
        }):
            with tempfile.TemporaryDirectory() as asset_dir:
                asset_path = self.create_manual_concept_asset(Path(asset_dir) / "gemini-import.png")
                if import_mode == "upload":
                    encoded = base64.b64encode(asset_path.read_bytes()).decode("ascii")
                    project = sw.import_concept_attempt(project_id, {
                        "source_prompt_id": prompt["concept_id"],
                        "name": "gemini-import.png",
                        "data_url": "data:image/png;base64,%s" % encoded,
                    })
                else:
                    project = sw.import_concept_attempt(project_id, {
                        "source_prompt_id": prompt["concept_id"],
                        "local_path": str(asset_path),
                    })
        imported = next(item for item in project["concepts"] if item.get("preview_image"))
        sw.update_concept_review_state(project_id, imported["concept_id"], "approve", True)
        sw.approve_rig_layout(project_id)
        return sw.load_project(project_id)

    def generate_approved_part_split(self, project_id: str):
        sw.generate_part_split(project_id)
        sw.approve_part_split(project_id)
        return sw.load_project(project_id)

    def build_debug_pipeline(self, tmpdir: str):
        original_root = sw.PROJECTS_ROOT
        sw.PROJECTS_ROOT = Path(tmpdir)
        try:
            project = sw.create_project({
                "project_name": "Pipeline Hero",
                "prompt_text": "a vigilant ranger with a lantern",
                "backend_mode": "debug_procedural",
                "last_ui_mode": "wizard",
            })
            project = self.import_valid_manual_concept(project["project_id"])
            project = self.generate_approved_part_split(project["project_id"])
            sw.build_sprite_model(project["project_id"])
            project = sw.load_project(project["project_id"])
            project["sprite_model_approved"] = True
            project["layer_review_approved"] = True
            sw.save_project(project)
            sw.build_rig(project["project_id"])
            project = sw.load_project(project["project_id"])
            project["rig_review_approved"] = True
            project["rig"]["approved_for_production"] = True
            sw.save_project(project)
            return sw.load_project(project["project_id"])
        finally:
            sw.PROJECTS_ROOT = original_root

    def build_ai_debug_workflow(self, tmpdir: str):
        original_root = sw.PROJECTS_ROOT
        sw.PROJECTS_ROOT = Path(tmpdir)
        try:
            project = sw.create_project({
                "project_name": "AI Workflow Hero",
                "prompt_text": "a side-view lantern knight",
                "backend_mode": "debug_procedural",
                "last_ui_mode": "wizard",
            })
            project = self.import_valid_manual_concept(project["project_id"])
            lock_run = sw.run_ai_workflow_stage(project["project_id"], {"stage": "character_lock", "workflow_profile": "ai_sideview_v1"})
            sw.approve_ai_workflow(project["project_id"], {
                "stage": "character_lock",
                "run_id": lock_run["run_id"],
                "asset_id": lock_run["candidates"][0]["asset_id"],
            })
            pose_run = sw.run_ai_workflow_stage(project["project_id"], {"stage": "key_pose_set", "workflow_profile": "ai_sideview_v1"})
            sw.approve_ai_workflow(project["project_id"], {
                "stage": "key_pose_set",
                "run_id": pose_run["run_id"],
            })
            for clip_name in ["idle", "walk"]:
                motion_run = sw.run_ai_workflow_stage(project["project_id"], {"stage": "motion_clip", "workflow_profile": "ai_sideview_v1", "clip_name": clip_name})
                sw.approve_ai_workflow(project["project_id"], {"stage": "motion_clip", "clip_name": clip_name, "run_id": motion_run["run_id"]})
                extract_run = sw.run_ai_workflow_stage(project["project_id"], {"stage": "extract_frames", "workflow_profile": "ai_sideview_v1", "clip_name": clip_name})
                sw.approve_ai_workflow(project["project_id"], {"stage": "extract_frames", "clip_name": clip_name, "run_id": extract_run["run_id"]})
                cleanup_run = sw.run_ai_workflow_stage(project["project_id"], {"stage": "pixel_cleanup", "workflow_profile": "ai_sideview_v1", "clip_name": clip_name})
                sw.approve_ai_workflow(project["project_id"], {"stage": "pixel_cleanup", "clip_name": clip_name, "run_id": cleanup_run["run_id"]})
            qa = sw.run_qa(project["project_id"])
            export = sw.export_project(project["project_id"])
            return sw.load_project(project["project_id"]), qa, export
        finally:
            sw.PROJECTS_ROOT = original_root

    @contextmanager
    def fixture_project(self, fixture_name: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            shutil.copytree(self.FIXTURE_ROOT / fixture_name, fixture_root / fixture_name)
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = fixture_root
            try:
                yield fixture_root, fixture_name
            finally:
                sw.PROJECTS_ROOT = original_root

    def assert_only_canonical_downstream_json(self, project_dir: Path):
        json_files = {path.name for path in project_dir.glob("*.json")}
        self.assertIn("sprite_model.json", json_files)
        self.assertIn("sprite_model_history.json", json_files)
        self.assertIn("animation_clips.json", json_files)
        self.assertNotIn("layered_character.json", json_files)
        self.assertNotIn("animation_templates.json", json_files)
        self.assertNotIn("palette.json", json_files)

    def test_fixture_matrix_loads_all_project_classes(self):
        for fixture_name in ["legacy-layered-character", "hybrid-mixed-pipeline", "canonical-sprite-model"]:
            with self.subTest(fixture=fixture_name):
                with self.fixture_project(fixture_name):
                    project = sw.load_project(fixture_name)
                    self.assertEqual(project["project_id"], fixture_name)
                    self.assertIsNotNone(project["sprite_model"])
                    self.assertIn(project["sprite_model"]["status"], {"pass", "warning"})

    def test_fixture_matrix_duplicate_writes_only_canonical_downstream_json(self):
        for fixture_name in ["legacy-layered-character", "hybrid-mixed-pipeline", "canonical-sprite-model"]:
            with self.subTest(fixture=fixture_name):
                with self.fixture_project(fixture_name) as (fixture_root, _):
                    duplicate = sw.duplicate_project(fixture_name)
                    self.assertNotEqual(duplicate["project_id"], fixture_name)
                    self.assert_only_canonical_downstream_json(fixture_root / duplicate["project_id"])

    def test_fixture_matrix_archive_marks_project_archived(self):
        for fixture_name in ["legacy-layered-character", "hybrid-mixed-pipeline", "canonical-sprite-model"]:
            with self.subTest(fixture=fixture_name):
                with self.fixture_project(fixture_name):
                    archived = sw.archive_project(fixture_name)
                    self.assertEqual(archived["status"], "archived")
                    self.assertIsNotNone(archived["archived_at"])

    def test_create_project_in_wizard_with_brief_advances_past_references_when_optional(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Wizard Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "last_ui_mode": "wizard",
                })
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(project["last_ui_mode"], "wizard")
        self.assertIn("describe", project["wizard_state"]["completed_steps"])
        # Describe (brief + optional references) satisfied once a brief exists; wizard focuses first incomplete step.
        self.assertEqual(project["step_statuses"]["describe"], "complete")
        self.assertEqual(project["wizard_state"]["current_step"], "concepts")

    def test_create_project_writes_bundle_manifest_and_health_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Persistence Hero",
                    "prompt_text": "a side-view knight",
                })
                project_dir = Path(tmpdir) / project["project_id"]
                manifest = sw.load_json(sw.project_bundle_manifest_path(project_dir))
                health = sw.load_json(sw.project_health_report_path(project_dir))
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(project["project_schema_version"], sw.PROJECT_SCHEMA_VERSION)
        self.assertEqual(project["project_bundle_manifest"]["project_schema_version"], sw.PROJECT_SCHEMA_VERSION)
        self.assertEqual(project["health_report"]["status"], "pass")
        self.assertEqual(manifest["project_id"], project["project_id"])
        self.assertIn("project.json", [item["path"] for item in manifest["artifacts"]])
        self.assertIn("brief.json", [item["path"] for item in manifest["artifacts"]])
        self.assertEqual(health["status"], "pass")

    def test_load_project_health_report_flags_missing_concept_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Broken Concept Project",
                    "prompt_text": "a side-view ranger",
                })
                project_dir = Path(tmpdir) / project["project_id"]
                concept = sw.hydrate_concept({
                    "concept_id": "concept-0001",
                    "project_id": project["project_id"],
                    "preview_image": "concepts/missing.png",
                    "original_preview_image": "concepts/missing.png",
                    "approved_source_image": "concepts/missing.png",
                    "review_state": {"approved": True},
                }, project["created_at"])
                project["selected_concept_id"] = concept["concept_id"]
                project["concepts"] = [concept]
                sw.save_project(project)
                loaded = sw.load_project(project["project_id"])
                stored_health = sw.load_json(sw.project_health_report_path(project_dir))
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(loaded["health_report"]["status"], "warning")
        self.assertEqual(stored_health["status"], "warning")
        self.assertTrue(any(item["path"] == "concepts/missing.png" for item in loaded["health_report"]["missing_files"]))

    def test_project_summary_reports_missing_export_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Missing Export Project",
                    "prompt_text": "a side-view rogue",
                })
                project["last_export"] = {
                    "export_dir": "exports/missing-build",
                    "generated_at": sw.now_iso(),
                }
                sw.save_project(project)
                summary = sw.project_summary(sw.list_projects(include_archived=True)[0])
                loaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(summary["project_health_status"], "warning")
        self.assertGreaterEqual(summary["project_health_missing_file_count"], 1)
        self.assertTrue(any(item["type"] == "last_export_missing" for item in loaded["health_report"]["missing_files"]))

    def test_workbench_settings_and_usage_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                defaults = sw.load_workbench_settings()
                self.assertEqual(defaults["safe_mode"], False)
                saved = sw.save_workbench_settings({"safe_mode": True, "confirm_paid_actions": False})
                self.assertEqual(saved["safe_mode"], True)
                self.assertEqual(saved["confirm_paid_actions"], False)
                sw.append_usage_ledger_entry(
                    provider="pixellab",
                    endpoint="pixellab.animate-custom",
                    project_id="demo-project",
                    usage_cost_usd=1.25,
                    metadata={"animation_name": "walk"},
                )
                summary = sw.summarize_usage_ledger()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(summary["entry_count"], 1)
        self.assertAlmostEqual(summary["today_usage_cost_usd"], 1.25)
        self.assertEqual(summary["recent_entries"][0]["endpoint"], "pixellab.animate-custom")

    def test_provider_call_allowed_blocks_when_safe_mode_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                sw.save_workbench_settings({"safe_mode": True})
                with self.assertRaises(ValueError):
                    sw.provider_call_allowed()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_import_demo_project_rehomes_fixture_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            original_demo_root = sw.DEMO_PROJECT_FIXTURE_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            sw.DEMO_PROJECT_FIXTURE_ROOT = self.FIXTURE_ROOT
            try:
                imported = sw.import_demo_project({"fixture_name": "canonical-sprite-model"})
                loaded = sw.load_project(imported["project_id"])
                project_json_exists = (Path(tmpdir) / imported["project_id"] / "project.json").exists()
            finally:
                sw.PROJECTS_ROOT = original_root
                sw.DEMO_PROJECT_FIXTURE_ROOT = original_demo_root

        self.assertNotEqual(imported["project_id"], "")
        self.assertEqual(loaded["project_id"], imported["project_id"])
        self.assertEqual(loaded["status"], "demo_imported")
        self.assertTrue(project_json_exists)

    def test_build_project_bundle_archive_includes_project_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Bundle Hero",
                    "prompt_text": "a side-view knight",
                })
                filename, payload = sw.build_project_bundle_archive(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertTrue(filename.endswith(".spriteworkbench.zip"))
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            names = set(zf.namelist())
        prefix = f"{project['project_id']}/"
        self.assertIn(f"{prefix}project.json", names)
        self.assertIn(f"{prefix}brief.json", names)
        self.assertIn(f"{prefix}{sw.ROOM_LAYOUT_FILENAME}", names)
        self.assertIn(f"{prefix}{sw.ROOM_LAYOUT_HISTORY_FILENAME}", names)
        self.assertIn(f"{prefix}{sw.LEVEL_VALIDATION_REPORT_FILENAME}", names)
        self.assertIn(f"{prefix}{sw.PROJECT_BUNDLE_MANIFEST_FILENAME}", names)
        self.assertIn(f"{prefix}{sw.PROJECT_HEALTH_REPORT_FILENAME}", names)

    def test_import_project_bundle_round_trips_assets_and_rehomes_project_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Import Hero",
                    "prompt_text": "a side-view ranger",
                })
                project_dir = Path(tmpdir) / project["project_id"]
                image_path = project_dir / "concepts" / "concept-0001.png"
                self.create_manual_concept_asset(image_path)
                concept = sw.hydrate_concept({
                    "concept_id": "concept-0001",
                    "project_id": project["project_id"],
                    "preview_image": "concepts/concept-0001.png",
                    "original_preview_image": "concepts/concept-0001.png",
                    "approved_source_image": "concepts/concept-0001.png",
                    "review_state": {"approved": True},
                }, project["created_at"])
                project["selected_concept_id"] = concept["concept_id"]
                project["concepts"] = [concept]
                sw.save_project(project)

                _, archive_bytes = sw.build_project_bundle_archive(project["project_id"])
                imported = sw.import_project_bundle({
                    "name": "import-hero.spriteworkbench.zip",
                    "data_url": "data:application/zip;base64,%s" % base64.b64encode(archive_bytes).decode("ascii"),
                })
                imported_dir = Path(tmpdir) / imported["project_id"]
                imported_asset_exists = (imported_dir / "concepts" / "concept-0001.png").exists()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertNotEqual(imported["project_id"], project["project_id"])
        self.assertEqual(imported["selected_concept_id"], "concept-0001")
        self.assertTrue(imported_asset_exists)
        self.assertEqual(imported["concepts"][0]["project_id"], imported["project_id"])
        self.assertEqual(imported["project_schema_version"], sw.PROJECT_SCHEMA_VERSION)
        self.assertEqual(imported["health_report"]["status"], "pass")
        self.assertEqual(imported["room_layout"]["meta"]["project_id"], imported["project_id"])
        self.assertEqual(imported["room_layout_history"]["project_id"], imported["project_id"])
        self.assertEqual(imported["level_validation_report"]["project_id"], imported["project_id"])

    def test_create_project_writes_room_layout_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Room Layout Hero",
                    "prompt_text": "a side-view cartographer",
                })
                project_dir = Path(tmpdir) / project["project_id"]
                room_layout = sw.load_json(project_dir / sw.ROOM_LAYOUT_FILENAME, {})
                room_history = sw.load_json(project_dir / sw.ROOM_LAYOUT_HISTORY_FILENAME, {})
                room_validation = sw.load_json(project_dir / sw.LEVEL_VALIDATION_REPORT_FILENAME, {})
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(room_layout["meta"]["project_id"], project["project_id"])
        self.assertEqual(len(room_layout["rooms"]), 1)
        self.assertEqual(room_history["project_id"], project["project_id"])
        self.assertEqual(room_history["current_revision_id"], "initial")
        self.assertEqual(room_validation["status"], "pass")

    def test_save_room_layout_persists_history_and_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Room Save Hero",
                    "prompt_text": "a side-view architect",
                })
                room_layout = sw.get_room_layout(project["project_id"])
                room_layout["rooms"].append({
                    "id": "R2",
                    "name": "Room 2",
                    "size": {"width": 1600, "height": 1200},
                    "global": {"x": 900, "y": 360},
                    "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
                    "platforms": [],
                    "movingPlatforms": [],
                    "doors": [],
                    "keys": [],
                    "abilities": [],
                    "playerStart": None,
                    "edgeLinks": [],
                    "removedEdges": [],
                })
                result = sw.save_room_layout(project["project_id"], room_layout)
                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertTrue(result["ok"])
        self.assertEqual(reloaded["room_layout"]["meta"]["project_id"], project["project_id"])
        self.assertEqual(len(reloaded["room_layout"]["rooms"]), 2)
        self.assertGreaterEqual(len(reloaded["room_layout_history"]["revisions"]), 2)
        self.assertEqual(reloaded["level_validation_report"]["status"], "warning")
        self.assertEqual(reloaded["status"], "room_layout_saved")
        self.assertTrue(any(item.get("type") == "room_layout_saved" for item in reloaded["history"]["events"]))

    def test_room_layout_api_round_trips_project_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Room API Hero",
                    "prompt_text": "a side-view surveyor",
                })
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request("GET", f"/api/projects/{project['project_id']}/room-layout")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["meta"]["project_id"], project["project_id"])

                    payload["rooms"][0]["name"] = "Edited Room"
                    body = json.dumps(payload)
                    connection.request(
                        "POST",
                        f"/api/projects/{project['project_id']}/room-layout",
                        body=body,
                        headers={"Content-Type": "application/json"},
                    )
                    save_response = connection.getresponse()
                    self.assertEqual(save_response.status, 200)
                    save_payload = json.loads(save_response.read().decode("utf-8"))
                    self.assertTrue(save_payload["ok"])
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()

                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(reloaded["room_layout"]["rooms"][0]["name"], "Edited Room")

    def test_update_project_brief_advances_wizard_to_concepts_when_references_satisfied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Blank Wizard",
                    "last_ui_mode": "wizard",
                })
                project = sw.update_project_brief(created["project_id"], {
                    "prompt_text": "a torch-bearing scout with layered leather armor",
                })
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertIn("describe", project["wizard_state"]["completed_steps"])
        self.assertEqual(project["step_statuses"]["describe"], "complete")
        self.assertEqual(project["wizard_state"]["current_step"], "concepts")

    def test_wizard_navigate_back_preserves_completed_step(self):
        """User can set current_step to a completed step; hydrate must not snap forward."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Back Nav Hero",
                    "prompt_text": "a side-view scout",
                    "last_ui_mode": "wizard",
                })
                reloaded = sw.update_wizard_state(created["project_id"], {"current_step": "describe"})
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(reloaded["wizard_state"]["current_step"], "describe")
        self.assertEqual(reloaded["step_statuses"].get("describe"), "complete")

    def test_review_stays_locked_until_a_valid_import_exists_and_refine_step_is_gone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Prompt Wizard",
                    "prompt_text": "a dune guard with a curved blade",
                    "last_ui_mode": "wizard",
                })
                sw.generate_initial_prompt(created["project_id"])
                before_valid = sw.load_project(created["project_id"])
                project = self.import_valid_manual_concept(created["project_id"], import_mode="local_path")
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertNotIn("refine", before_valid["step_statuses"])
        self.assertEqual(before_valid["step_statuses"]["concepts"], "active")
        self.assertEqual(before_valid["step_statuses"]["character"], "locked")
        self.assertIn("concept", before_valid["blocking_reasons"]["character"][0].lower())
        self.assertEqual(project["step_statuses"]["concepts"], "complete")
        self.assertNotIn("rig_layout", project["step_statuses"])
        self.assertIn(project["step_statuses"]["character"], {"active", "ready", "complete"})

    def test_concept_approval_generates_rig_layout_before_sprite_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Knight Layout",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "last_ui_mode": "wizard",
                })
                prompt = sw.generate_initial_prompt(created["project_id"])
                with patch.object(sw, "run_gemini_concept_validation", return_value={
                    "decision": "valid",
                    "summary": "Extraction-ready after safe normalization.",
                    "feedback": "Ready to continue.",
                    "improved_gemini_prompt": None,
                    "master_pose_ready": True,
                    "technical_requirements_ok": True,
                    "response_id": "resp_valid",
                }):
                    with tempfile.TemporaryDirectory() as asset_dir:
                        asset_path = self.create_manual_concept_asset(Path(asset_dir) / "knight.png")
                        project = sw.import_concept_attempt(created["project_id"], {
                            "source_prompt_id": prompt["concept_id"],
                            "local_path": str(asset_path),
                        })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                project = sw.update_concept_review_state(created["project_id"], imported["concept_id"], "approve", True)
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(project["current_stage"], "rig_layout")
        if project["ai_workflow"]["enabled"] and not project["ai_workflow"].get("legacy_mode"):
            self.assertNotIn("rig_layout", project["step_statuses"])
            self.assertIn(project["step_statuses"]["character"], {"active", "ready", "complete"})
            self.assertEqual(project["ai_workflow"]["selected_assets"]["approved_concept_id"], imported["concept_id"])
        elif project["ai_workflow"]["enabled"]:
            self.assertIn(project["step_statuses"]["rig_layout"], {"active", "ready"})
            self.assertEqual(project["ai_workflow"]["selected_assets"]["approved_concept_id"], imported["concept_id"])
        else:
            self.assertIn(project["step_statuses"]["rig_layout"], {"active", "ready"})
            self.assertFalse(project["rig_layout_approved"])
            self.assertEqual(project["rig_layout"]["rig_profile"], sw.SIDE_KNIGHT_SIMPLE_7)

    def test_valid_gemini_import_sets_direct_source_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Direct Source Hero",
                    "prompt_text": "a side-view armored pilgrim with a lantern",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                accepted = next(item for item in project["concepts"] if item["concept_id"] == project["selected_concept_id"])
                approved_source_exists = (sw.PROJECTS_ROOT / project["project_id"] / accepted["approved_source_image"]).exists()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(accepted["validation_status"], "valid")
        self.assertTrue(accepted["approved_source_image"])
        self.assertTrue(approved_source_exists)

    def test_generate_part_split_creates_candidate_parts_and_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Split Hero",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                sw.generate_part_manifest(project["project_id"])
                sw.approve_part_manifest(project["project_id"])
                sw.initialize_part_shapes(project["project_id"])
                sw.approve_part_shapes(project["project_id"])
                part_split = sw.build_split_from_part_shapes(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertTrue(part_split["parts"])
        self.assertEqual(part_split["approved"], False)
        self.assertIn("path", part_split["reconstruction_preview"])
        self.assertIn(part_split["validation"]["status"], {"pass", "warning", "fail"})

    def test_validate_part_split_uses_canvas_position_for_overlap_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "split-validate"
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "part_split" / "parts").mkdir(parents=True, exist_ok=True)
            (project_dir / "part_split" / "masks").mkdir(parents=True, exist_ok=True)
            image = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
            mask = Image.new("L", (10, 10), 255)
            left_image_path, left_mask_path = sw.write_part_split_asset(project_dir, "left_piece", image, mask)
            right_image_path, right_mask_path = sw.write_part_split_asset(project_dir, "right_piece", image, mask)

            validation = sw.validate_part_split(project_dir, {
                "part_manifest": {
                    "parts": [
                        {"part_name": "left_piece", "required": True},
                        {"part_name": "right_piece", "required": True},
                    ]
                },
                "parts": [
                    {
                        "part_name": "left_piece",
                        "image_path": left_image_path,
                        "mask_path": left_mask_path,
                        "bbox": [0, 0, 10, 10],
                        "source_method": "manual_edit",
                    },
                    {
                        "part_name": "right_piece",
                        "image_path": right_image_path,
                        "mask_path": right_mask_path,
                        "bbox": [20, 20, 30, 30],
                        "source_method": "manual_edit",
                    },
                ],
            })

        self.assertEqual(validation["status"], "pass")
        self.assertFalse(validation["failures"])
        self.assertFalse(validation["warnings"])

    def test_generate_part_manifest_and_shapes_persist_new_contracts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Manifest Hero",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                manifest = sw.generate_part_manifest(project["project_id"])
                sw.approve_part_manifest(project["project_id"])
                shapes = sw.initialize_part_shapes(project["project_id"])
                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertTrue(manifest["parts"])
        self.assertIn(manifest["validation"]["status"], {"pass", "warning"})
        self.assertTrue(shapes["parts"])
        self.assertIn(shapes["validation"]["status"], {"pass", "warning"})
        self.assertTrue(reloaded["part_manifest_approved"])
        self.assertFalse(reloaded["part_shapes_approved"])

    def test_delete_concept_removes_json_and_image_when_unshared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Delete Me Hero",
                    "prompt_text": "a side-view scout with a cloak",
                    "last_ui_mode": "wizard",
                })
                prompt = sw.generate_initial_prompt(created["project_id"])
                with patch.object(sw, "run_gemini_concept_validation", return_value={
                    "decision": "valid",
                    "summary": "ok",
                    "feedback": "",
                    "improved_gemini_prompt": None,
                    "master_pose_ready": True,
                    "technical_requirements_ok": True,
                    "response_id": "resp_valid",
                }):
                    with tempfile.TemporaryDirectory() as asset_dir:
                        asset_path = self.create_manual_concept_asset(Path(asset_dir) / "scout.png")
                        project = sw.import_concept_attempt(created["project_id"], {
                            "source_prompt_id": prompt["concept_id"],
                            "local_path": str(asset_path),
                        })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                cid = imported["concept_id"]
                project_dir = sw.PROJECTS_ROOT / created["project_id"]
                json_path = project_dir / "concepts" / ("%s.json" % cid)
                self.assertTrue(json_path.exists())
                after = sw.delete_concept(created["project_id"], cid)
                self.assertFalse(any(c.get("concept_id") == cid for c in after["concepts"]))
                self.assertFalse(json_path.exists())
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_synthetic_key_pose_run_from_selected_concept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = root
            try:
                pid = "proj-synth-pose"
                pdir = root / pid
                concepts_dir = pdir / "concepts"
                concepts_dir.mkdir(parents=True)
                img_path = concepts_dir / "concept-0001.png"
                Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(img_path)
                project = {
                    "project_id": pid,
                    "selected_concept_id": "concept-0001",
                    "concepts": [{
                        "concept_id": "concept-0001",
                        "preview_image": "concepts/concept-0001.png",
                    }],
                }
                run = sw._ai_synthetic_key_pose_run_from_selected_concept(project, pdir)
                self.assertIsNotNone(run)
                self.assertEqual(len(run["poses"]), len(sw.AI_KEY_POSE_NAMES))
                for pose in run["poses"]:
                    self.assertEqual(pose["image_path"], "concepts/concept-0001.png")
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_ai_workflow_debug_pipeline_can_drive_qa_and_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project, qa, export = self.build_ai_debug_workflow(tmpdir)
            store = project["ai_workflow"]
            self.assertTrue(store["enabled"])
            self.assertEqual(store["profile"], "ai_sideview_v1")
            lock_run = store["character_lock"]["runs"][store["character_lock"]["approved_run_id"]]
            self.assertEqual(len(lock_run["candidates"]), 6)
            pose_run = store["key_pose_set"]["runs"][store["key_pose_set"]["approved_run_id"]]
            self.assertEqual(sorted(pose["pose_name"] for pose in pose_run["poses"]), sorted(sw.AI_KEY_POSE_NAMES))
            idle_cleanup = store["cleanup_runs"]["idle"]["runs"][store["cleanup_runs"]["idle"]["approved_run_id"]]
            walk_cleanup = store["cleanup_runs"]["walk"]["runs"][store["cleanup_runs"]["walk"]["approved_run_id"]]
            self.assertEqual(len(idle_cleanup["frames"]), 6)
            self.assertEqual(len(walk_cleanup["frames"]), 8)
            self.assertEqual(qa["mode"], "ai_workflow")
            self.assertEqual(qa["status"], "pass")
            self.assertEqual(export["mode"], "ai_workflow")
            export_dir = Path(tmpdir) / project["project_id"] / export["export_dir"]
            self.assertTrue((export_dir / "spritesheet.png").exists())
            self.assertTrue((export_dir / "atlas.json").exists())
            self.assertTrue((export_dir / "animations.json").exists())
            self.assertIn("idle", export.get("animation_sheets") or {})
            self.assertTrue((export_dir / "animation_sheets" / "idle.png").exists())
            self.assertTrue((export_dir / "animation_sheets" / "idle.json").exists())
            self.assertTrue((export_dir / "preview_idle.gif").exists())
            self.assertTrue((export_dir / "preview_walk.gif").exists())
            self.assertFalse((export_dir / "preview.gif").exists())
            self.assertTrue((export_dir / "export_manifest.json").exists())

    def test_ai_workflow_health_normalizes_legacy_comfyui_mode(self):
        health = sw.ai_workflow_health_snapshot("comfyui")
        self.assertEqual(health["overall_status"], "pass")
        self.assertEqual(health["backend_mode"], "debug_procedural")
        self.assertEqual(health["dependencies"]["comfyui"]["status"], "pass")

    def test_ai_character_lock_uses_procedural_when_brief_has_legacy_comfyui(self):
        """Legacy ``comfyui`` brief mode maps to debug_procedural; no external Comfy calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Comfy Hero",
                    "prompt_text": "a side-view lantern knight",
                    "backend_mode": "comfyui",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                run = sw.run_ai_character_lock(project["project_id"], sw.AI_WORKFLOW_PROFILE, [project["selected_concept_id"]], {}, progress=None)
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(len(run["candidates"]), sw.AI_CHARACTER_LOCK_COUNT)
        self.assertTrue(all(item.get("workflow_id") == "photomaker_ipadapter_character_lock" for item in run["candidates"]))

    def test_legacy_projects_hydrate_read_only_ai_mode(self):
        with self.fixture_project("hybrid-mixed-pipeline"):
            project = sw.load_project("hybrid-mixed-pipeline")
        self.assertTrue(project["ai_workflow"]["legacy_mode"])
        self.assertFalse(project["ai_workflow"]["enabled"])

    def test_external_authoring_mutation_endpoints_return_410(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Legacy Endpoint Hero",
                    "prompt_text": "a side-view shield knight",
                    "backend_mode": "debug_procedural",
                })
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request(
                        "POST",
                        f"/api/projects/{project['project_id']}/external-authoring/update",
                        body=json.dumps({"enabled": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    body = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root
        self.assertEqual(response.status, 410)
        self.assertIn("retired", body["error"].lower())

    def test_part_shape_update_round_trips_vertices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Shape Edit Hero",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                sw.generate_part_manifest(project["project_id"])
                sw.approve_part_manifest(project["project_id"])
                shapes = sw.initialize_part_shapes(project["project_id"])
                target = shapes["parts"][0]
                updated = sw.update_part_shapes(project["project_id"], {
                    "operation": "update_part",
                    "part_name": target["part_name"],
                    "vertices": [[260, 90], [360, 90], [360, 210], [260, 210]],
                    "source_method": "manual_edit",
                })
            finally:
                sw.PROJECTS_ROOT = original_root

        edited = next(item for item in updated["parts"] if item["part_name"] == target["part_name"])
        self.assertEqual(edited["vertices"], [[260, 90], [360, 90], [360, 210], [260, 210]])
        self.assertEqual(edited["source_method"], "manual_edit")

    def test_regenerating_part_manifest_preserves_matching_shape_vertices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Manifest Preserve Hero",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                sw.generate_part_manifest(project["project_id"])
                sw.approve_part_manifest(project["project_id"])
                shapes = sw.initialize_part_shapes(project["project_id"])
                target = shapes["parts"][0]
                custom_vertices = [[260, 90], [360, 90], [360, 210], [260, 210]]
                sw.update_part_shapes(project["project_id"], {
                    "operation": "update_part",
                    "part_name": target["part_name"],
                    "vertices": custom_vertices,
                    "source_method": "manual_edit",
                })
                sw.update_part_manifest(project["project_id"], {
                    "operation": "reset_to_rig_profile_default",
                })
                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        preserved = next(item for item in reloaded["part_shapes"]["parts"] if item["part_name"] == target["part_name"])
        self.assertEqual(preserved["vertices"], custom_vertices)
        self.assertFalse(reloaded["part_shapes_approved"])

    def test_sprite_model_build_requires_approved_part_split_on_new_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Blocked Hero",
                    "prompt_text": "a side-view armored knight with sword and cape",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                sw.generate_part_split(project["project_id"])
                with self.assertRaisesRegex(ValueError, "Approve the part split"):
                    sw.build_sprite_model(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_sprite_model_build_extracts_required_parts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Sprite Model Hero",
                    "prompt_text": "a watchful scout with a lantern",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                self.generate_approved_part_split(project["project_id"])
                sprite_model = sw.build_sprite_model(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(sprite_model["status"], "pass")
        self.assertGreaterEqual(len(sprite_model["parts"]), 1)
        self.assertTrue(sprite_model["approved_source_image"].startswith("concepts/"))
        self.assertIsNone(sprite_model["approved_master_pose"])
        self.assertIn("swatches", sprite_model["palette"])
        self.assertEqual(sprite_model["source_mode"], "approved_part_split")

    def test_full_debug_pipeline_renders_clips_passes_qa_and_exports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Full Pipeline Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                self.generate_approved_part_split(project["project_id"])
                sw.build_sprite_model(project["project_id"])
                project = sw.load_project(project["project_id"])
                project["sprite_model_approved"] = True
                project["layer_review_approved"] = True
                sw.save_project(project)
                sw.build_rig(project["project_id"])
                project = sw.load_project(project["project_id"])
                project["rig_review_approved"] = True
                project["rig"]["approved_for_production"] = True
                sw.save_project(project)
                sw.render_animation(project["project_id"], "idle")
                sw.render_animation(project["project_id"], "walk")
                qa = sw.run_qa(project["project_id"])
                export = sw.export_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(qa["status"], "pass")
        self.assertIn("idle", qa["per_animation_checks"])
        self.assertTrue(export["export_dir"].startswith("exports/"))
        self.assertIn("spritesheet.png", export["files"])

    def test_sprite_model_validation_blocks_approval_on_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                updated = sw.update_sprite_model(project["project_id"], {
                    "operation": "remove_from_mask",
                    "part_name": "torso",
                    "region": [0, 0, 500, 500],
                })
                self.assertEqual(updated["status"], "fail")
                with self.assertRaisesRegex(ValueError, "blocked"):
                    sw.approve_sprite_model_review(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_sprite_model_revision_restore_round_trip_restores_exact_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                project_dir = Path(tmpdir) / project["project_id"]
                original_hash = sw.image_sha256(project_dir / "sprite_model.json")
                original_revision_id = sw.load_project(project["project_id"])["sprite_model_history"]["current_revision_id"]
                sw.update_sprite_model(project["project_id"], {
                    "operation": "translate_part",
                    "part_name": "torso",
                    "dx": 9,
                    "dy": 0,
                })
                restored = sw.restore_sprite_model_revision(project["project_id"], original_revision_id)
                self.assertEqual(restored["sprite_model_history"]["current_revision_id"], original_revision_id)
                self.assertEqual(sw.image_sha256(project_dir / "sprite_model.json"), original_hash)
                rig = sw.build_rig(project["project_id"])
                self.assertIn("rig_joint_map", rig)
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_clip_update_persists_controls_and_clears_export_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                sw.approve_rig_review(project["project_id"])
                sw.render_animation(project["project_id"], "idle")
                sw.render_animation(project["project_id"], "walk")
                sw.run_qa(project["project_id"])
                sw.export_project(project["project_id"])
                updated = sw.update_animation_clip(project["project_id"], "idle", {
                    "controls": {
                        "body_bob": 4.0,
                        "arm_swing": 9.0,
                    },
                })
                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(updated["controls"]["body_bob"], 4.0)
        self.assertEqual(reloaded["animation_clips"]["idle"]["controls"]["arm_swing"], 9.0)
        self.assertIsNone(reloaded["qa_report"])
        self.assertIsNone(reloaded["last_export"])

    def test_export_manifest_includes_post_pack_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                sw.approve_rig_review(project["project_id"])
                sw.render_animation(project["project_id"], "idle")
                sw.render_animation(project["project_id"], "walk")
                sw.run_qa(project["project_id"])
                export = sw.export_project(project["project_id"])
                export_manifest = sw.load_json(Path(tmpdir) / project["project_id"] / export["export_dir"] / "export_manifest.json")
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(export_manifest["verification"]["status"], "pass")
        self.assertIn("atlas.json", export_manifest["bundle_hashes"])
        self.assertIn("animation_sheets", export_manifest)
        self.assertEqual(export["verification"]["status"], "pass")

    def test_hydrate_brief_is_backward_compatible(self):
        legacy = {
            "subject": "humanoid biped",
            "silhouette": "broad",
            "outfit": "armored traveler",
            "palette_direction": "storm steel",
            "prop": "lantern",
            "normalized_prompt": "Humanoid biped side-view armored traveler with a lantern.",
            "reference_images": ["refs/id.png"],
            "style_references": ["refs/style.png"],
        }
        brief = sw.hydrate_brief(legacy, "")
        self.assertEqual(brief["role_archetype"], "humanoid biped")
        self.assertEqual(brief["prop"], "lantern")
        self.assertEqual(len(brief["references"]), 2)
        self.assertEqual(brief["references"][0]["role"], "identity")
        self.assertEqual(brief["references"][1]["role"], "style")

    def test_generate_initial_prompt_persists_history_and_prompt_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Prompt Hero",
                    "prompt_text": "a watchful ranger with layered leather armor and a lantern",
                })
                result = sw.generate_initial_prompt(project["project_id"])
                reloaded = sw.load_project(project["project_id"])
                prompt_exists = (Path(tmpdir) / project["project_id"] / "prompts" / "latest-gemini-prompt.txt").exists()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertIn("Character brief:", result["prompt_text"])
        self.assertEqual(reloaded["latest_prompt"]["prompt_version"], 1)
        self.assertTrue(prompt_exists)
        self.assertEqual(reloaded["status"], "prompt_ready")

    def test_generate_improved_prompt_includes_prior_prompt_and_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Improve Hero",
                    "prompt_text": "a grim pilgrim with a lantern",
                })
                initial = sw.generate_initial_prompt(project["project_id"])
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": initial["concept_id"],
                    "local_path": str(self.create_manual_concept_asset(Path(tmpdir) / "concept.png")),
                })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                updated = sw.update_concept_validation(project["project_id"], imported["concept_id"], "invalid", "make the silhouette leaner and remove the heavy shoulder mass")
                improved = sw.generate_improved_prompt(project["project_id"], imported["concept_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertIn("Use the attached previous image as the direct reference.", improved["prompt_text"])
        self.assertIn("make the silhouette leaner", improved["prompt_text"])
        self.assertEqual(updated["concepts"][-1]["validation_status"], "invalid")

    def test_upload_import_creates_concept_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Upload Hero",
                    "prompt_text": "a lantern scout",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                image_path = self.create_manual_concept_asset(Path(tmpdir) / "upload-source.png")
                encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": prompt["concept_id"],
                    "name": "upload-source.png",
                    "data_url": "data:image/png;base64,%s" % encoded,
                })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                import_exists = (Path(tmpdir) / project["project_id"] / imported["preview_image"]).exists()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(imported["import_source"], "upload")
        self.assertEqual(imported["validation_status"], "valid")
        self.assertTrue(import_exists)

    def test_local_path_import_creates_concept_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Path Hero",
                    "prompt_text": "a lantern scout",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                image_path = self.create_manual_concept_asset(Path(tmpdir) / "local-source.png")
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": prompt["concept_id"],
                    "local_path": str(image_path),
                })
            finally:
                sw.PROJECTS_ROOT = original_root

        imported = next(item for item in project["concepts"] if item.get("preview_image"))
        self.assertEqual(imported["import_source"], "local_path")
        self.assertEqual(imported["validation_status"], "valid")
        self.assertFalse((imported.get("validation_error") or "").strip())

    def test_safe_normalization_removes_detached_logo_and_white_halo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = self.create_logo_and_halo_asset(Path(tmpdir) / "logo-halo.png")
            output_path = Path(tmpdir) / "processed.png"
            result = sw.safe_normalize_concept_image(source_path, output_path)
            processed = Image.open(output_path).convert("RGBA")
            alpha = processed.getchannel("A")
            bbox = alpha.getbbox()

        self.assertEqual(result["status"], "applied")
        self.assertIsNotNone(bbox)
        self.assertGreater(bbox[0], 100)
        self.assertGreater(bbox[1], 20)
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(alpha.getpixel((sw.CONCEPT_CANVAS[0] - 1, 0)), 0)

    def test_safe_normalization_removes_subject_edge_halo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = self.create_subject_halo_asset(Path(tmpdir) / "subject-halo.png")
            output_path = Path(tmpdir) / "processed.png"
            result = sw.safe_normalize_concept_image(source_path, output_path)
            processed = Image.open(output_path).convert("RGBA")
            alpha = processed.getchannel("A")
            bbox = alpha.getbbox()

        self.assertEqual(result["status"], "applied")
        self.assertIsNotNone(bbox)
        edge_sample = processed.getpixel((bbox[0], (bbox[1] + bbox[3]) // 2))
        self.assertLess(min(edge_sample[:3]), 220)

    def test_invalid_gemini_import_persists_retry_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Gemini Reject Hero",
                    "prompt_text": "a lantern scout",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                with patch.object(sw, "run_gemini_concept_validation", return_value={
                    "decision": "invalid",
                    "summary": "Silhouette is too front-facing.",
                    "feedback": "Use a stricter side profile and a cleaner background.",
                    "improved_gemini_prompt": "Side-profile lantern scout, one full-body humanoid, plain removable background.",
                    "master_pose_ready": False,
                    "technical_requirements_ok": False,
                    "response_id": "resp_invalid",
                }):
                    project = sw.import_concept_attempt(project["project_id"], {
                        "source_prompt_id": prompt["concept_id"],
                        "local_path": str(self.create_manual_concept_asset(Path(tmpdir) / "reject.png")),
                    })
            finally:
                sw.PROJECTS_ROOT = original_root

        imported = next(item for item in project["concepts"] if item.get("preview_image"))
        self.assertEqual(imported["validation_status"], "invalid")
        self.assertEqual(imported["validation_source"], "gemini")
        self.assertIn("stricter side profile", imported["validation_feedback"])
        self.assertEqual(project["latest_prompt"]["prompt_source"], "gemini_retry")
        self.assertIn("plain removable background", project["latest_prompt"]["prompt_text"])

    def test_gemini_failure_revalidation_stays_pending_with_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Retry Hero",
                    "prompt_text": "a lantern scout",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": prompt["concept_id"],
                    "local_path": str(self.create_manual_concept_asset(Path(tmpdir) / "retry.png")),
                })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                with patch.object(sw, "run_gemini_concept_validation", side_effect=RuntimeError("service unavailable")):
                    project = sw.validate_imported_concept(project["project_id"], imported["concept_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        retried = next(item for item in project["concepts"] if item["concept_id"] == imported["concept_id"])
        self.assertEqual(retried["validation_status"], "pending")
        self.assertEqual(retried["validation_source"], "gemini")
        self.assertIn("service unavailable", retried["validation_error"])

    def test_wizard_steps_remove_master_pose(self):
        self.assertNotIn("master_pose", sw.WIZARD_STEPS)

    def test_manual_validation_transitions_pending_to_invalid_and_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Validation Hero",
                    "prompt_text": "a lantern scout",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": prompt["concept_id"],
                    "local_path": str(self.create_manual_concept_asset(Path(tmpdir) / "validation.png")),
                })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                invalid = sw.update_concept_validation(project["project_id"], imported["concept_id"], "invalid", "prop reads too large")
                valid = sw.update_concept_validation(project["project_id"], imported["concept_id"], "valid")
            finally:
                sw.PROJECTS_ROOT = original_root

        invalid_attempt = next(item for item in invalid["concepts"] if item["concept_id"] == imported["concept_id"])
        valid_attempt = next(item for item in valid["concepts"] if item["concept_id"] == imported["concept_id"])
        self.assertEqual(invalid_attempt["validation_status"], "invalid")
        self.assertEqual(invalid_attempt["validation_feedback"], "prop reads too large")
        self.assertEqual(valid_attempt["validation_status"], "valid")

    def test_accepting_concept_requires_valid_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Accept Hero",
                    "prompt_text": "a lantern scout",
                    "backend_mode": "debug_procedural",
                })
                prompt = sw.generate_initial_prompt(project["project_id"])
                project = sw.import_concept_attempt(project["project_id"], {
                    "source_prompt_id": prompt["concept_id"],
                    "local_path": str(self.create_manual_concept_asset(Path(tmpdir) / "accept.png")),
                })
                imported = next(item for item in project["concepts"] if item.get("preview_image"))
                # Import runs local validation immediately (valid for test assets); flip to invalid to exercise the gate.
                project = sw.update_concept_validation(project["project_id"], imported["concept_id"], "invalid", "blocked for acceptance test")
                with self.assertRaisesRegex(ValueError, "Only valid imported concepts can be accepted"):
                    sw.update_concept_review_state(project["project_id"], imported["concept_id"], "approve", True)
                project = sw.update_concept_validation(project["project_id"], imported["concept_id"], "valid")
                accepted = sw.update_concept_review_state(project["project_id"], imported["concept_id"], "approve", True)
            finally:
                sw.PROJECTS_ROOT = original_root

        accepted_attempt = next(item for item in accepted["concepts"] if item["concept_id"] == imported["concept_id"])
        self.assertEqual(accepted["selected_concept_id"], imported["concept_id"])
        self.assertTrue(accepted_attempt["accepted_for_review"])

    def test_normalize_brief_backend_mode_maps_comfyui_to_debug(self):
        self.assertEqual(sw.normalize_brief_backend_mode("comfyui"), "debug_procedural")
        self.assertEqual(sw.normalize_brief_backend_mode("debug_procedural"), "debug_procedural")
        self.assertEqual(sw.normalize_brief_backend_mode("pixellab"), "pixellab")

    def test_build_positive_prompt_base_uses_ashen_hollow_house_style(self):
        brief = sw.hydrate_brief({
            "raw_prompt": "armored lantern pilgrim",
            "role_archetype": "ashen hollow pilgrim",
            "silhouette_intent": "broad guarded profile",
            "outfit_materials": "weathered plate over layered travel cloth",
            "prop": "lantern",
            "palette_mood": "storm steel",
            "shape_language": "angular disciplined silhouettes",
            "mood_tone": "watchful and haunted",
            "side_view_constraints": "strict side view",
        }, "")
        prompt = sw.build_positive_prompt_base(brief)
        self.assertIn("Ashen Hollow", prompt)
        self.assertIn("Hollow Knight-inspired atmosphere", prompt)
        self.assertIn("orthographic side profile", prompt)
        self.assertIn("single character only", prompt)

    def test_build_rig_layout_handoff_prompt_biases_toward_simple_rig(self):
        project = sw.apply_project_defaults({
            "project_id": "demo-project",
            "project_name": "Demo Project",
            "brief": {
                "role_archetype": "armored traveler",
                "silhouette_intent": "broad guarded profile",
                "outfit_materials": "weathered plate and cloth",
                "prop": "sword",
                "palette_mood": "storm steel",
                "mood_tone": "grim and vigilant",
            },
            "selected_concept_id": "concept-0001",
            "concepts": [{
                "concept_id": "concept-0001",
                "positive_prompt": "side-view armored knight with sword and cloth drape",
            }],
        })
        rig_layout = sw.resolve_rig_layout(project, persist=False)
        prompt = sw.build_rig_layout_handoff_prompt(project, rig_layout)
        self.assertIn("rig_profile: side_knight_simple_7", prompt)
        self.assertIn('"rig_profile": "side_knight_simple_7"', prompt)
        self.assertIn("The allowed part list is a superset, not a target checklist.", prompt)
        self.assertIn("Do not return more than 8 total parts. If more than 8 parts seem necessary, return valid=false.", prompt)
        self.assertIn("8 total parts is a hard ceiling for this response.", prompt)
        self.assertIn("If the simplified profile still cannot represent the concept within 8 total parts, return valid=false.", prompt)
        self.assertIn("For side_knight_simple_7, the default expected joint_driving_parts are: head, torso_pelvis, front_arm, front_leg, weapon.", prompt)
        self.assertIn("A typical good result for this kind of character is about 7 to 8 total parts, not 20.", prompt)
        self.assertIn("If the concept would require the legacy many-part rig to function, return valid=false instead of emitting an over-split layout.", prompt)
        self.assertIn("If the layout reaches anything close to the legacy full-part count, treat that as a likely failure to simplify and reconsider from scratch.", prompt)

    def test_create_job_tracks_progress_updates(self):
        job = sw.create_job(None, "demo.progress", lambda progress: (progress(55, "Halfway there", "Testing progress"), {"ok": True})[1])
        deadline = time.time() + 5
        while time.time() < deadline:
            with sw.JOB_LOCK:
                snapshot = dict(sw.JOBS[job["job_id"]])
            if snapshot["status"] == "completed":
                break
            time.sleep(0.05)
        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(snapshot["progress_percent"], 100)
        self.assertEqual(snapshot["progress_label"], "Completed")
        self.assertEqual(snapshot["result"], {"ok": True})

    def test_derive_metrics_from_history(self):
        history = {
            "project_id": "demo",
            "events": [
                {
                    "type": "concept_run",
                    "run_id": "run-a",
                    "run_kind": "initial",
                    "created_at": "2026-03-13T10:00:00+00:00",
                },
                {
                    "type": "review_action",
                    "run_id": "run-a",
                    "concept_id": "concept-0001",
                    "action": "approve",
                    "value": True,
                    "created_at": "2026-03-13T10:02:00+00:00",
                },
                {
                    "type": "review_action",
                    "run_id": "run-a",
                    "concept_id": "concept-0002",
                    "action": "reject",
                    "value": True,
                    "created_at": "2026-03-13T10:01:00+00:00",
                },
                {
                    "type": "concept_run",
                    "run_id": "run-b",
                    "run_kind": "refinement",
                    "source_concept_id": "concept-0001",
                    "created_at": "2026-03-13T10:03:00+00:00",
                },
            ],
        }
        metrics = sw.derive_metrics(history)
        self.assertEqual(metrics["concept_runs_per_project"], 1)
        self.assertEqual(metrics["approvals_per_run"]["run-a"], 1)
        self.assertEqual(metrics["rejects_per_run"]["run-a"], 1)
        self.assertEqual(metrics["refinements_per_selected_concept"]["concept-0001"], 1)
        self.assertEqual(metrics["time_to_approved_concept_seconds"], 120)

    def test_aggregate_check_state_handles_not_implemented(self):
        self.assertEqual(sw.aggregate_check_state(["pass", "not_implemented"]), "pass")
        self.assertEqual(sw.aggregate_check_state(["not_implemented", "not_implemented"]), "not_implemented")
        self.assertEqual(sw.aggregate_check_state(["pass", "fail"]), "fail")

    def test_cleanup_frame_keeps_anchor_stable_across_translated_sources(self):
        first = Image.new("RGBA", sw.WORKING_CANVAS, (0, 0, 0, 0))
        first_draw = ImageDraw.Draw(first)
        first_draw.rectangle((120, 80, 160, 200), fill=(255, 255, 255, 255))
        first_draw.rectangle((110, 200, 170, 214), fill=(255, 255, 255, 255))

        second = Image.new("RGBA", sw.WORKING_CANVAS, (0, 0, 0, 0))
        second_draw = ImageDraw.Draw(second)
        second_draw.rectangle((147, 80, 187, 200), fill=(255, 255, 255, 255))
        second_draw.rectangle((137, 200, 197, 214), fill=(255, 255, 255, 255))

        cleaned_first, meta_first = sw.cleanup_frame(first, anchor_point=(140, 214))
        cleaned_second, meta_second = sw.cleanup_frame(second, anchor_point=(167, 214))

        self.assertEqual(meta_first["output_box"], meta_second["output_box"])
        self.assertEqual(cleaned_first.tobytes(), cleaned_second.tobytes())

    def test_generate_clip_frames_simple_walk_stays_conservative(self):
        frames = sw.generate_clip_frames("walk", sw.DEFAULT_CLIP_CONTROLS["walk"], rig_profile=sw.SIDE_KNIGHT_SIMPLE_7)

        self.assertLessEqual(max(abs(frame["shoulder_front_rotation"]) for frame in frames), 6.0)
        self.assertLessEqual(max(abs(frame["hip_front_rotation"]) for frame in frames), 7.5)
        self.assertLessEqual(max(abs(frame["root_offset"][1]) for frame in frames), 3.0)
        self.assertLessEqual(max(abs(frame["weapon_rotation"]) for frame in frames), 2.4)

    def test_build_joint_map_uses_part_names_for_simple_profile(self):
        sprite_model = {
            "rig_layout": {"rig_profile": sw.SIDE_KNIGHT_SIMPLE_7},
            "parts": [
                {"part_name": "torso_pelvis", "part_role": "primary", "bbox": [100, 120, 160, 220], "pivot_point": [30, 20]},
                {"part_name": "head", "part_role": "primary", "bbox": [112, 48, 154, 126], "pivot_point": [14, 64]},
                {"part_name": "front_arm", "part_role": "primary", "bbox": [132, 130, 194, 210], "pivot_point": [8, 10]},
                {"part_name": "front_leg", "part_role": "primary", "bbox": [108, 196, 150, 280], "pivot_point": [16, 8]},
                {"part_name": "weapon", "part_role": "primary", "bbox": [176, 150, 228, 198], "pivot_point": [6, 16]},
                {"part_name": "cape_back", "part_role": "overlay", "bbox": [88, 122, 118, 232], "pivot_point": [6, 8]},
            ],
        }

        joint_map = sw.build_joint_map_from_sprite_model(sprite_model)

        self.assertEqual(set(joint_map), {"root", "torso", "neck", "head", "shoulder_front", "wrist_front", "hip_front", "ankle_front"})
        self.assertEqual(joint_map["torso"], [130.0, 140.0])
        self.assertEqual(joint_map["head"], [126.0, 112.0])

    def test_clone_part_entry_can_scale_and_bottom_align(self):
        image = Image.new("RGBA", (10, 20), (255, 255, 255, 255))
        mask = Image.new("L", (10, 20), 255)
        source_part = {"part_name": "front_leg"}

        cloned_image, cloned_mask, meta = sw.clone_part_entry(
            source_part,
            image,
            mask,
            (100, 200, 130, 250),
            shade_factor=0.7,
            scale_x=0.5,
            scale_y=0.5,
            align="bottom_right",
        )

        self.assertEqual(cloned_image.size, (5, 10))
        self.assertEqual(cloned_mask.size, (5, 10))
        self.assertEqual(meta["bbox"], [125, 240, 130, 250])
        self.assertEqual(cloned_image.getpixel((0, 0)), (178, 178, 178, 255))

    def test_generate_clip_frames_dual_leg_walk_stays_pixel_conservative(self):
        frames = sw.generate_clip_frames("walk", sw.DEFAULT_CLIP_CONTROLS["walk"], rig_profile=sw.SIDE_KNIGHT_DUAL_LEG_8)

        self.assertLessEqual(max(abs(frame["shoulder_front_rotation"]) for frame in frames), 1.6)
        self.assertLessEqual(max(abs(frame["weapon_rotation"]) for frame in frames), 0.65)
        self.assertLessEqual(max(abs(frame["root_offset"][1]) for frame in frames), 1.7)
        self.assertGreaterEqual(max(abs(frame["hip_front_rotation"]) for frame in frames), 5.5)
        self.assertGreaterEqual(max(abs(frame["hip_back_rotation"]) for frame in frames), 5.0)
        self.assertLessEqual(max(abs(frame["hip_front_rotation"]) for frame in frames), 6.4)
        self.assertLessEqual(max(abs(frame["hip_back_rotation"]) for frame in frames), 5.8)
        self.assertLessEqual(max(abs(frame["front_cloth_rotation_bias"]) for frame in frames), 0.9)

    def test_server_supports_cors_preflight(self):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
        except PermissionError:
            self.skipTest("Sandbox does not allow binding a local socket.")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request(
                "OPTIONS",
                "/api/health",
                headers={
                    "Origin": "http://127.0.0.1:5500",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 204)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", response.getheader("Access-Control-Allow-Methods"))
            self.assertIn("Content-Type", response.getheader("Access-Control-Allow-Headers"))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_health_endpoint_includes_settings_usage_and_demo_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            original_demo_root = sw.DEMO_PROJECT_FIXTURE_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            sw.DEMO_PROJECT_FIXTURE_ROOT = self.FIXTURE_ROOT
            try:
                sw.save_workbench_settings({"safe_mode": True, "confirm_paid_actions": True})
                sw.append_usage_ledger_entry(
                    provider="pixellab",
                    endpoint="concepts.generate-pixellab",
                    project_id="demo",
                    usage_cost_usd=0.5,
                )
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request("GET", "/api/health")
                    response = connection.getresponse()
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)
                    self.assertEqual(data["settings"]["safe_mode"], True)
                    self.assertEqual(data["usage_summary"]["entry_count"], 1)
                    self.assertGreaterEqual(len(data["demo_projects"]), 1)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root
                sw.DEMO_PROJECT_FIXTURE_ROOT = original_demo_root

    def test_pixellab_configured_false_when_key_unset(self):
        original_key = sw.PIXELLAB_API_KEY
        sw.PIXELLAB_API_KEY = ""
        # Keep the lazy singleton consistent in case other tests ran first.
        if hasattr(sw, "_pixellab_client"):
            sw._pixellab_client = None
        try:
            self.assertFalse(sw.pixellab_configured())
        finally:
            sw.PIXELLAB_API_KEY = original_key
            if hasattr(sw, "_pixellab_client"):
                sw._pixellab_client = None

    def test_pixellab_character_wizard_complete_reads_json_and_project_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp)
            char_path = pdir / "pixellab_character.json"
            project = {"project_id": "x"}
            self.assertFalse(sw.pixellab_character_wizard_complete(project, pdir))
            char_path.write_text(json.dumps({"approved": False}), encoding="utf-8")
            self.assertFalse(sw.pixellab_character_wizard_complete(project, pdir))
            char_path.write_text(json.dumps({"approved": True}), encoding="utf-8")
            self.assertTrue(sw.pixellab_character_wizard_complete(project, pdir))
            self.assertTrue(sw.pixellab_character_wizard_complete({"pixellab_character_approved": True}, pdir))

    def test_load_project_hydrates_pixellab_character_and_skeleton(self):
        original_root = sw.PROJECTS_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            sw.PROJECTS_ROOT = Path(tmp)
            try:
                project = sw.create_project({
                    "project_name": "PL Hydrate",
                    "prompt_text": "a test hero",
                    "last_ui_mode": "wizard",
                })
                pid = project["project_id"]
                pdir = sw.PROJECTS_ROOT / pid
                char_doc = {"character_id": "c1", "approved": False, "images": {"east": "character/east.png"}}
                skel_doc = {"direction": "east", "skeleton_keypoints": [[1.0, 2.0]]}
                (pdir / "pixellab_character.json").write_text(json.dumps(char_doc), encoding="utf-8")
                (pdir / "pixellab_skeleton.json").write_text(json.dumps(skel_doc), encoding="utf-8")
                loaded = sw.load_project(pid)
                self.assertEqual(loaded["pixellab_character"]["character_id"], "c1")
                self.assertEqual(loaded["pixellab_skeleton"]["direction"], "east")
                self.assertIn("animations", loaded["pixellab_animations"])
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_wizard_steps_active_inserts_animations_for_pixellab(self):
        project = {
            "brief": {"backend_mode": "pixellab"},
            "ai_workflow": {"enabled": True, "legacy_mode": False},
        }
        seq = sw.wizard_steps_active(project)
        self.assertEqual(seq, sw.WIZARD_STEPS_PIXEL_LAB_UI)
        self.assertIn("animations", seq)
        self.assertEqual(seq.index("animations"), seq.index("character") + 1)

    def test_wizard_steps_active_omits_animations_for_non_pixellab_ai(self):
        project = {
            "brief": {"backend_mode": "debug_procedural"},
            "ai_workflow": {"enabled": True, "legacy_mode": False},
        }
        self.assertEqual(sw.wizard_steps_active(project), sw.WIZARD_STEPS_AI_SIMPLE_UI)
        self.assertNotIn("animations", sw.wizard_steps_active(project))

    def test_wizard_steps_active_ai_omits_rig_layout_and_part_manifest(self):
        project = {
            "brief": {"backend_mode": "debug_procedural"},
            "ai_workflow": {"enabled": True, "legacy_mode": False},
        }
        seq = sw.wizard_steps_active(project)
        self.assertNotIn("rig_layout", seq)
        self.assertNotIn("part_manifest", seq)
        self.assertIn("character", seq)

    def test_pixellab_animation_store_has_frames_detects_any_generated_clip(self):
        self.assertFalse(sw.pixellab_animation_store_has_frames(None))
        self.assertFalse(sw.pixellab_animation_store_has_frames({}))
        self.assertTrue(
            sw.pixellab_animation_store_has_frames({"idle": {"directions": {"east": {"frames": ["a"]}}}})
        )
        self.assertTrue(
            sw.pixellab_animation_store_has_frames({
                "jump": {"directions": {"east": {"frames": ["b"]}}},
            })
        )

    def test_validate_pixellab_animation_name_slug(self):
        self.assertEqual(sw.validate_pixellab_animation_name("Attack"), "attack")
        self.assertEqual(sw.validate_pixellab_animation_name("cast_spell"), "cast_spell")
        with self.assertRaises(ValueError):
            sw.validate_pixellab_animation_name("9bad")
        with self.assertRaises(ValueError):
            sw.validate_pixellab_animation_name("no spaces")

    def test_pixellab_qa_clip_names_orders_default_set_then_custom(self):
        clips = {
            "z_custom": {"frames": ["a.png"]},
            "idle": {"frames": ["i0.png"]},
            "walk": {"frames": ["w0.png"]},
            "run": {"frames": ["r0.png"]},
            "jump": {"frames": ["j0.png"]},
            "empty": {"frames": []},
            "no_frames": {},
        }
        self.assertEqual(sw._pixellab_qa_clip_names(clips), ["idle", "walk", "run", "jump", "z_custom"])

    def test_sync_pixellab_animation_clips_merges_generated_frames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixel Lab Sync",
                    "prompt_text": "a side-view pilot",
                    "backend_mode": "pixellab",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id
                char_payload = {
                    "character_id": "char-test",
                    "approved": True,
                    "directions": ["east"],
                    "image_size": {"width": 128, "height": 128},
                    "images": {"east": "character/east.png"},
                }
                (project_dir / "character").mkdir(parents=True, exist_ok=True)
                Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(project_dir / "character" / "east.png")
                (project_dir / "pixellab_character.json").write_text(json.dumps(char_payload, indent=2), encoding="utf-8")

                frames_dir = project_dir / "animations" / "run" / "east"
                frames_dir.mkdir(parents=True, exist_ok=True)
                frame_rel_paths = []
                for idx in range(2):
                    frame_path = frames_dir / ("frame_%02d.png" % idx)
                    Image.new("RGBA", (128, 128), (idx * 40, 0, 0, 255)).save(frame_path)
                    frame_rel_paths.append(str(frame_path.relative_to(project_dir)))

                pix_store = {
                    "project_id": project_id,
                    "updated_at": sw.now_iso(),
                    "animations": {
                        "run": {
                            "animation_name": "run",
                            "fps": 14,
                            "frame_count": 2,
                            "loop": True,
                            "directions": {
                                "east": {
                                    "frames": frame_rel_paths,
                                    "frame_count": 2,
                                    "fps": 14,
                                    "updated_at": sw.now_iso(),
                                }
                            },
                        }
                    },
                }
                (project_dir / "pixellab_animations.json").write_text(json.dumps(pix_store, indent=2), encoding="utf-8")

                clips = sw.sync_pixellab_animation_clips(project_id)
                reloaded = sw.load_project(project_id)
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(clips["run"]["frame_count"], 2)
        self.assertEqual(clips["run"]["frames_by_direction"]["east"], frame_rel_paths)
        self.assertEqual(reloaded["animation_clips"]["run"]["frames"], frame_rel_paths)
        self.assertEqual(reloaded["status"], "pixellab_animation_clips_synced")

    def test_pixellab_animate_custom_poll_timeout_constant_sane(self):
        self.assertGreaterEqual(sw.PIXELLAB_ANIMATE_CUSTOM_POLL_TIMEOUT_SECONDS, 180)

    def test_env_int_respects_minimum(self):
        key = "__SW_ENV_INT_TEST__"
        old = os.environ.pop(key, None)
        try:
            self.assertEqual(sw.env_int(key, 900, minimum=180), 900)
            os.environ[key] = "50"
            self.assertEqual(sw.env_int(key, 900, minimum=180), 900)
            os.environ[key] = "1200"
            self.assertEqual(sw.env_int(key, 900, minimum=180), 1200)
        finally:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_hydrate_animation_clips_aligns_frame_count_with_raster_bridge_frames(self):
        """animation_clips.json from Pixel Lab can list fewer paths than ANIMATION_SPECS."""
        raw = {
            "idle": {
                "frame_count": 6,
                "fps": 8,
                "loop": True,
                "frames": ["animations/idle/east/frame_%02d.png" % i for i in range(4)],
                "frames_by_direction": {
                    "east": ["animations/idle/east/frame_%02d.png" % i for i in range(4)],
                },
            },
            "walk": {
                "frame_count": 8,
                "fps": 10,
                "loop": True,
                "frames": ["animations/walk/east/frame_%02d.png" % i for i in range(8)],
            },
        }
        out = sw.hydrate_animation_clips(raw, None, rig_profile=sw.LEGACY_RIG_PROFILE)
        self.assertEqual(out["idle"]["frame_count"], 4)
        self.assertEqual(len(out["idle"]["frames"]), 4)
        self.assertEqual(out["idle"]["fps"], 8)
        self.assertEqual(out["walk"]["frame_count"], 8)

    def test_pixellab_animations_step_complete_requires_any_generated_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp)
            doc_bad = {
                "project_id": "x",
                "animations": {
                    "walk": {"directions": {}},
                },
            }
            (pdir / "pixellab_animations.json").write_text(json.dumps(doc_bad), encoding="utf-8")
            project = {"project_id": "x"}
            self.assertFalse(sw.pixellab_animations_step_complete(project, pdir))
            doc_ok = {
                "project_id": "x",
                "animations": {
                    "jump": {"directions": {"east": {"frames": ["b.png"]}}},
                },
            }
            (pdir / "pixellab_animations.json").write_text(json.dumps(doc_ok), encoding="utf-8")
            self.assertTrue(sw.pixellab_animations_step_complete(project, pdir))

    def test_pixellab_health_endpoint_returns_configured_false_when_key_unset(self):
        original_key = sw.PIXELLAB_API_KEY
        sw.PIXELLAB_API_KEY = ""
        if hasattr(sw, "_pixellab_client"):
            sw._pixellab_client = None

        try:
            try:
                server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
            except PermissionError:
                self.skipTest("Sandbox does not allow binding a local socket.")

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("GET", "/api/pixellab/health")
                response = connection.getresponse()
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                self.assertEqual(data.get("configured"), False)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
        finally:
            sw.PIXELLAB_API_KEY = original_key
            if hasattr(sw, "_pixellab_client"):
                sw._pixellab_client = None

    def test_pixellab_client_encode_decode_roundtrip(self):
        client = pl.PixelLabClient("fake-key")
        img = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
        b64 = client.encode_image(img)
        decoded = client.decode_image(b64)
        self.assertEqual(decoded.size, (8, 8))
        self.assertEqual(decoded.getpixel((0, 0)), (255, 0, 0, 128))

    def test_pixellab_client_encode_image_accepts_path(self):
        client = pl.PixelLabClient("fake-key")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            file_path = Path(tmp.name)
        try:
            Image.new("RGB", (4, 4), (0, 255, 0)).save(file_path)
            b64_path = client.encode_image(file_path)
            b64_str = client.encode_image(str(file_path))
            self.assertEqual(b64_path, b64_str)
        finally:
            file_path.unlink(missing_ok=True)

    def test_base64_image_payload_matches_v2_schema(self):
        payload = pl.base64_image_payload("Zm9v")
        self.assertEqual(
            payload,
            {"type": "base64", "base64": "Zm9v", "format": "png"},
        )
        self.assertEqual(
            pl.base64_image_payload("eA==", image_format="jpeg"),
            {"type": "base64", "base64": "eA==", "format": "jpeg"},
        )

    def test_normalize_pixellab_image_base64_strips_data_uri(self):
        raw = "iVBORw0KGgo" + ("A" * 80)
        uri = "data:image/png;base64," + raw
        self.assertEqual(sw._normalize_pixellab_image_base64(uri), raw)

    def test_pixellab_open_image_bytes_accepts_raw_rgba_square(self):
        """API may return 64×64×4 packed RGBA with no PNG header (e.g. 16384 null bytes)."""
        side = 64
        raw = bytes(side * side * 4)  # transparent black
        img = sw._pixellab_open_image_bytes(raw, where="test")
        self.assertEqual(img.size, (side, side))
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0, 0))

    def test_pixellab_open_image_bytes_raw_rgba_uses_canvas_hint(self):
        w, h = 64, 64
        raw = bytes(w * h * 4)
        img = sw._pixellab_open_image_bytes(
            raw,
            where="south",
            rgba_size=(w, h),
        )
        self.assertEqual(img.size, (w, h))

    def test_try_pixellab_raw_packed_pixels_rejects_wrong_length_for_canvas(self):
        raw = bytes(100)  # not 64*64*4
        self.assertIsNone(sw._try_pixellab_raw_packed_pixels(raw, width=64, height=64))

    def test_collect_nested_images_dict_finds_result_branch(self):
        got = sw._collect_nested_images_dict({"result": {"images": {"east": {"base64": "eA=="}}}})
        self.assertIsNotNone(got)
        self.assertIn("east", got)

    def test_extract_pixellab_character_directions_from_images_map(self):
        img = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        directions = ["south", "east"]
        result = {"images": {d: {"type": "base64", "base64": b64} for d in directions}}
        out = sw._extract_pixellab_character_direction_image_bytes(result, directions, client=None)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], buf.getvalue())
        self.assertEqual(out[1], buf.getvalue())

    def test_extract_pixellab_character_rotation_urls_fallback(self):
        tiny = Image.new("RGBA", (1, 1), (1, 2, 3, 4))
        png_buf = io.BytesIO()
        tiny.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        class FakeClient:
            api_key = "k"

            def get_character(self, character_id):
                return {
                    "id": character_id,
                    "rotation_urls": {
                        "south": "https://cdn.example/s.png",
                        "east": "https://cdn.example/e.png",
                    },
                }

        with patch.object(sw, "_download_url_bytes", return_value=png_bytes):
            result = {"character_id": "char-123", "status": "completed"}
            out = sw._extract_pixellab_character_direction_image_bytes(
                result,
                ["south", "east"],
                client=FakeClient(),
            )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], png_bytes)
        self.assertEqual(out[1], png_bytes)

    def test_extract_unwraps_background_job_last_response_for_character_id(self):
        """Pixel Lab GET /v2/background-jobs/{id} nests payload under ``last_response``."""
        tiny = Image.new("RGBA", (1, 1), (5, 6, 7, 255))
        png_buf = io.BytesIO()
        tiny.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        class FakeClient:
            api_key = "k"
            seen_id = None

            def get_character(self, character_id):
                self.seen_id = character_id
                return {
                    "id": character_id,
                    "rotation_urls": {
                        "south": "https://cdn.example/s.png",
                        "east": "https://cdn.example/e.png",
                    },
                }

        fc = FakeClient()
        wrapped = {
            "id": "job-uuid",
            "status": "completed",
            "last_response": {"character_id": "char-from-last-response"},
        }
        with patch.object(sw, "_download_url_bytes", return_value=png_bytes):
            out = sw._extract_pixellab_character_direction_image_bytes(
                wrapped,
                ["south", "east"],
                client=fc,
            )
        self.assertEqual(len(out), 2)
        self.assertEqual(fc.seen_id, "char-from-last-response")
        self.assertEqual(out[0], png_bytes)

    def test_extract_pixellab_images_map_per_direction_url(self):
        tiny = Image.new("RGBA", (1, 1), (9, 8, 7, 255))
        png_buf = io.BytesIO()
        tiny.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        class FakeClient:
            api_key = "k"

        with patch.object(sw, "_download_url_bytes", return_value=png_bytes) as dl:
            result = {"images": {"south": {"url": "https://cdn.example/s.png"}}}
            out = sw._extract_pixellab_character_direction_image_bytes(
                result,
                ["south"],
                client=FakeClient(),
            )
        self.assertEqual(out, [png_bytes])
        dl.assert_called_once()

    def test_pixellab_poll_job_prefers_last_response(self):
        client = pl.PixelLabClient("fake-key")
        seq = iter(
            [
                {"id": "j1", "status": "processing"},
                {"id": "j1", "status": "completed", "last_response": {"character_id": "c1", "ok": True}},
            ]
        )

        def fake_request(method, path):
            return next(seq)

        with patch.object(client, "_request_json", side_effect=fake_request):
            out = client._poll_job("j1", timeout_seconds=15, interval_seconds=0)
        self.assertEqual(out.get("character_id"), "c1")
        self.assertTrue(out.get("ok"))

    def test_format_background_job_failure_extracts_error_and_detail(self):
        payload = {
            "id": "6274163f-ac2b-42e5-9437-2ee19019389d",
            "status": "failed",
            "last_response": {
                "error": "Animation splitting failed: Expected 4 frames but only got 0.",
                "detail": "Request validation failed",
            },
        }
        msg = pl.format_background_job_failure(payload)
        self.assertIn("Animation splitting failed", msg)
        self.assertIn("Request validation failed", msg)
        self.assertNotIn("usd", msg)

    def test_pixellab_animate_character_polls_all_background_job_ids(self):
        """POST /v2/characters/animations may return ``background_job_ids`` (polled in parallel)."""
        client = pl.PixelLabClient("fake-key")
        accepted = {
            "background_job_ids": ["job-a", "job-b"],
            "directions": ["south", "east"],
            "status": "accepted",
        }
        lr_a = {"direction": "south", "ok": True}
        lr_b = {"direction": "east", "ok": True}

        def rq(method, path, payload=None):
            if method == "POST":
                return accepted
            if "job-a" in path:
                return {"id": "job-a", "status": "completed", "last_response": lr_a}
            if "job-b" in path:
                return {"id": "job-b", "status": "completed", "last_response": lr_b}
            raise AssertionError((method, path))

        with patch.object(client, "_request_json", side_effect=rq):
            out = client.animate_character(
                "char-1",
                "template_walk",
                directions=["south", "east"],
                poll_timeout_seconds=30,
            )
        self.assertEqual(out.get("per_job_last_response"), [lr_a, lr_b])
        self.assertEqual(out.get("background_job_ids"), ["job-a", "job-b"])
        self.assertEqual(out.get("status"), "completed")

    def test_animate_character_falls_back_to_serial_when_parallel_fails(self):
        client = pl.PixelLabClient("fake-key")
        post_calls = {"n": 0}

        def rq(method, path, payload=None):
            if method == "POST":
                post_calls["n"] += 1
                if post_calls["n"] == 1:
                    return {
                        "background_job_ids": ["m1", "m2"],
                        "directions": ["south", "east"],
                        "status": "p",
                    }
                if post_calls["n"] == 2:
                    return {"background_job_ids": ["s1"], "directions": ["south"], "status": "p"}
                if post_calls["n"] == 3:
                    return {"background_job_ids": ["s2"], "directions": ["east"], "status": "p"}
            raise AssertionError((method, path))

        def until_settled(job_ids, **kwargs):
            # Parallel batch all failed/timed out → refill every direction serially.
            return ({}, {str(j): "splitting failed" for j in job_ids})

        def parallel_poll(job_ids, **kwargs):
            return [{"jid": jid} for jid in job_ids]

        with patch.object(client, "_poll_jobs_parallel_until_settled", side_effect=until_settled), patch.object(
            client, "_poll_jobs_parallel", side_effect=parallel_poll
        ), patch.object(client, "_request_json", side_effect=rq):
            out = client.animate_character(
                "cid",
                "breathing-idle",
                directions=["south", "east"],
                seed=9,
                poll_timeout_seconds=20,
            )
        self.assertEqual([x.get("jid") for x in out["per_job_last_response"]], ["s1", "s2"])
        self.assertEqual(out["background_job_ids"], ["s1", "s2"])

    def test_animate_character_serial_refill_only_failed_directions(self):
        client = pl.PixelLabClient("fake-key")
        post_n = {"n": 0}

        def rq(method, path, payload=None):
            if method == "POST":
                post_n["n"] += 1
                if post_n["n"] == 1:
                    return {
                        "background_job_ids": ["ja", "jb"],
                        "directions": ["south", "east"],
                        "status": "p",
                    }
                if post_n["n"] == 2:
                    pl = (payload or {}).get("directions") or []
                    self.assertEqual(pl, ["east"])
                    return {"background_job_ids": ["jr"], "directions": ["east"], "status": "p"}
            raise AssertionError((method, path))

        def until_settled(job_ids, **kwargs):
            self.assertEqual(list(job_ids), ["ja", "jb"])
            return ({"ja": {"lane": "parallel"}}, {"jb": "east failed fast"})

        def parallel_poll(job_ids, **kwargs):
            if list(job_ids) == ["jr"]:
                return [{"lane": "serial", "east": True}]
            raise AssertionError(job_ids)

        with patch.object(client, "_poll_jobs_parallel_until_settled", side_effect=until_settled), patch.object(
            client, "_poll_jobs_parallel", side_effect=parallel_poll
        ), patch.object(client, "_request_json", side_effect=rq):
            out = client.animate_character(
                "cid",
                "breathing-idle",
                directions=["south", "east"],
                seed=9,
                poll_timeout_seconds=20,
            )
        self.assertEqual(
            out["per_job_last_response"],
            [{"lane": "parallel"}, {"lane": "serial", "east": True}],
        )
        self.assertEqual(out["background_job_ids"], ["ja", "jr"])

    def test_animate_character_serial_by_direction_merges_in_order(self):
        client = pl.PixelLabClient("fake-key")
        posts = iter(
            [
                {"background_job_ids": ["ja"], "directions": ["south"], "status": "p"},
                {"background_job_ids": ["jb"], "directions": ["east"], "status": "p"},
            ]
        )

        def rq(method, path, payload=None):
            if method == "POST":
                return next(posts)
            if "background-jobs" in path:
                jid = path.rstrip("/").split("/")[-1]
                return {"id": jid, "status": "completed", "last_response": {"jid": jid}}
            raise AssertionError((method, path))

        with patch.object(client, "_request_json", side_effect=rq):
            merged, ids = client._animate_character_serial_by_direction(
                "cid",
                "tid",
                ["south", "east"],
                30,
                {"seed": 5},
            )
        self.assertEqual(ids, ["ja", "jb"])
        self.assertEqual([m.get("jid") for m in merged], ["ja", "jb"])

    def test_poll_jobs_parallel_surfaces_failure_without_finishing_first_job(self):
        client = pl.PixelLabClient("fake-key")

        def rq(method, path, payload=None):
            if "job-slow" in path:
                return {"id": "job-slow", "status": "processing"}
            if "job-bad" in path:
                return {
                    "id": "job-bad",
                    "status": "failed",
                    "last_response": {"error": "split failed", "detail": "x"},
                }
            raise AssertionError(path)

        with patch.object(client, "_request_json", side_effect=rq):
            with self.assertRaisesRegex(pl.PixelLabError, "west"):
                client._poll_jobs_parallel(
                    ["job-slow", "job-bad"],
                    direction_labels=["south", "west"],
                    timeout_seconds=60,
                    interval_seconds=0,
                )

    def test_poll_jobs_parallel_until_settled_allows_other_jobs_to_finish(self):
        client = pl.PixelLabClient("fake-key")
        state = {"good_polls": 0}

        def rq(method, path, payload=None):
            if "job-bad" in path:
                return {
                    "id": "job-bad",
                    "status": "failed",
                    "last_response": {"error": "split failed", "detail": "x"},
                }
            if "job-good" in path:
                state["good_polls"] += 1
                if state["good_polls"] < 2:
                    return {"id": "job-good", "status": "processing"}
                return {"id": "job-good", "status": "completed", "last_response": {"ok": 1}}
            raise AssertionError(path)

        with patch.object(client, "_request_json", side_effect=rq):
            completed, failed = client._poll_jobs_parallel_until_settled(
                ["job-bad", "job-good"],
                direction_labels=["west", "south"],
                timeout_seconds=60,
                interval_seconds=0,
            )
        self.assertIn("job-bad", failed)
        self.assertIn("west", failed["job-bad"])
        self.assertEqual(completed.get("job-good"), {"ok": 1})

    def test_pixellab_client_get_balance_parses_json(self):
        client = pl.PixelLabClient("fake-key")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"type":"usd","usd":12.5}'

        with patch.object(pl, "urlopen", autospec=True) as mock_urlopen:
            # urlopen is used as a context manager in the client.
            mock_urlopen.return_value.__enter__.return_value = mock_response
            balance = client.get_balance()

        self.assertEqual(balance.get("usd"), 12.5)

    def test_build_concept_prompt_scaffold_includes_debug_and_defaults(self):
        brief = {
            "raw_prompt": "a vigilant ranger with a lantern",
            "role_archetype": "ashen hollow ranger",
            "silhouette_intent": "broad guarded profile",
            "outfit_materials": "weathered plate over travel cloth",
            "prop": "lantern",
            "palette_mood": "storm steel",
            "shape_language": "balanced angular to rounded mix",
            "mood_tone": "watchful and haunted",
        }

        scaffold = sw.build_concept_prompt(brief)
        self.assertIn("DEBUG CONSTRAINTS", scaffold["display_prompt"])
        self.assertIn("128x128", scaffold["display_prompt"])
        self.assertEqual(scaffold["pixellab_params"]["image_size"]["width"], 128)
        self.assertEqual(scaffold["pixellab_params"]["view"], "side")
        self.assertEqual(scaffold["pixellab_params"]["direction"], "east")
        self.assertIn("debug_constraints", scaffold)
        self.assertEqual(scaffold["debug_constraints"]["canvas_size"]["width"], 128)

    def test_build_iteration_prompt_inpaint_returns_base64_and_mask(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            concept_path = Path(tmpdir) / "concept.png"
            # Create a simple RGBA concept-like image.
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 10, 80, 90), fill=(180, 120, 90, 255))
            img.save(concept_path)

            brief = {
                "raw_prompt": "a vigilant ranger with a lantern",
                "role_archetype": "ashen hollow ranger",
                "silhouette_intent": "broad guarded profile",
                "outfit_materials": "weathered plate over travel cloth",
                "prop": "lantern",
                "palette_mood": "storm steel",
                "shape_language": "balanced angular to rounded mix",
                "mood_tone": "watchful and haunted",
            }

            scaffold = sw.build_iteration_prompt(
                brief,
                "outfit",
                "make the cape longer and more tattered",
                source_concept_path=concept_path,
            )
            self.assertIn("DEBUG CONSTRAINTS", scaffold["display_prompt"])
            self.assertIn("EDIT CONTRACT:", scaffold["display_prompt"])
            self.assertIn("Editable aspect: outfit and materials", scaffold["display_prompt"])
            self.assertIn("This is the ONLY aspect that may materially change.", scaffold["display_prompt"])
            self.assertIn("LOCKED ASPECTS FOR THIS EDIT:", scaffold["display_prompt"])
            self.assertIn("Never add a backing silhouette, halo, matte, cutout fill, shadow plate, or blocker shape behind the sprite.", scaffold["display_prompt"])
            self.assertIn("mask_boxes", scaffold["debug_constraints"]["inpaint"])
            self.assertTrue(len(scaffold["debug_constraints"]["inpaint"]["mask_boxes"]) >= 1)
            self.assertIn("inpainting_image_b64", scaffold["pixellab_params"])
            self.assertIn("mask_image_b64", scaffold["pixellab_params"])
            self.assertTrue(len(scaffold["pixellab_params"]["inpainting_image_b64"]) > 20)
            self.assertTrue(len(scaffold["pixellab_params"]["mask_image_b64"]) > 20)
            self.assertEqual(scaffold["pixellab_params"]["image_size"]["width"], 128)
            self.assertTrue(scaffold["pixellab_params"]["crop_to_mask"])

    def test_build_iteration_prompt_pose_locks_non_pose_aspects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            concept_path = Path(tmpdir) / "concept.png"
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 10, 80, 90), fill=(180, 120, 90, 255))
            img.save(concept_path)

            brief = {
                "raw_prompt": "a vigilant ranger with a lantern",
                "role_archetype": "ashen hollow ranger",
                "silhouette_intent": "broad guarded profile",
                "outfit_materials": "weathered plate over travel cloth",
                "prop": "lantern",
                "palette_mood": "storm steel",
                "shape_language": "balanced angular to rounded mix",
                "mood_tone": "watchful and haunted",
            }

            scaffold = sw.build_iteration_prompt(
                brief,
                "pose",
                "raise the front arm slightly and shift to a more guarded stance",
                source_concept_path=concept_path,
            )

            self.assertIn("Editable aspect: pose", scaffold["display_prompt"])
            self.assertIn("limb placement, arm angles, leg angles, and stance only while preserving the existing side-profile head and torso read", scaffold["display_prompt"])
            self.assertIn("character identity, armor design, and prop design", scaffold["display_prompt"])
            self.assertIn("head profile, face direction, and torso side-view read", scaffold["display_prompt"])
            self.assertIn("The source image is the authority for identity, rendering, layout, and all untouched pixels.", scaffold["display_prompt"])

    def test_build_iteration_prompt_pose_view_correction_unlocks_orientation_fix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            concept_path = Path(tmpdir) / "concept.png"
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 10, 80, 90), fill=(180, 120, 90, 255))
            img.save(concept_path)

            brief = {
                "raw_prompt": "a vigilant ranger with a lantern",
                "role_archetype": "ashen hollow ranger",
                "silhouette_intent": "broad guarded profile",
                "outfit_materials": "weathered plate over travel cloth",
                "prop": "lantern",
                "palette_mood": "storm steel",
                "shape_language": "balanced angular to rounded mix",
                "mood_tone": "watchful and haunted",
            }

            scaffold = sw.build_iteration_prompt(
                brief,
                "pose",
                "convert this 3/4 view into a strict side view profile",
                source_concept_path=concept_path,
            )

            self.assertIn("Editable aspect: pose and view correction", scaffold["display_prompt"])
            self.assertIn("VIEW CORRECTION MODE:", scaffold["display_prompt"])
            self.assertIn("Replace 3/4-view, front-facing, or camera-turned anatomy with a clean strict side profile.", scaffold["display_prompt"])

    def test_build_iteration_prompt_strict_side_view_request_triggers_view_correction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            concept_path = Path(tmpdir) / "concept.png"
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 10, 80, 90), fill=(180, 120, 90, 255))
            img.save(concept_path)

            brief = {
                "raw_prompt": "a vigilant ranger with a lantern",
                "role_archetype": "ashen hollow ranger",
                "silhouette_intent": "broad guarded profile",
                "outfit_materials": "weathered plate over travel cloth",
                "prop": "lantern",
                "palette_mood": "storm steel",
                "shape_language": "balanced angular to rounded mix",
                "mood_tone": "watchful and haunted",
            }

            scaffold = sw.build_iteration_prompt(
                brief,
                "pose",
                "change the pose to a strict side view",
                source_concept_path=concept_path,
            )

            self.assertIn("Editable aspect: pose and view correction", scaffold["display_prompt"])
            self.assertIn("VIEW CORRECTION MODE:", scaffold["display_prompt"])

    def test_build_gemini_requirements_prompt_describes_single_aspect_contract(self):
        brief = {
            "raw_prompt": "a vigilant ranger with a lantern",
            "role_archetype": "ashen hollow ranger",
            "silhouette_intent": "broad guarded profile",
            "outfit_materials": "weathered plate over travel cloth",
            "prop": "lantern",
            "palette_mood": "storm steel",
            "shape_language": "balanced angular to rounded mix",
            "mood_tone": "watchful and haunted",
        }

        prompt = sw._build_gemini_requirements_prompt(
            brief,
            "expression",
            "make the eyes brighter",
        )

        self.assertIn("This is an image edit, not a redesign and not a fresh generation.", prompt)
        self.assertIn("Aspect to change: expression", prompt)
        self.assertIn("Editable zone: face or visor read only", prompt)
        self.assertIn("Allowed changes:", prompt)
        self.assertIn("Keep unchanged unless required by the requested edit:", prompt)
        self.assertIn("Return one edited full sprite image only.", prompt)
        self.assertNotIn("PIXEL OWNERSHIP RULES:", prompt)
        self.assertNotIn("Treat areas outside the selected edit region as copy-from-source pixels", prompt)

    def test_gemini_iteration_supported_for_all_iteration_elements(self):
        for element in sw.ITERATION_ELEMENTS:
            self.assertTrue(sw.gemini_iteration_supported_for_element(element))
        self.assertFalse(sw.gemini_iteration_supported_for_element("unknown"))

    def test_concept_source_image_relpath_prefers_original_preview(self):
        concept = {
            "processed_preview_image": "concepts/processed.png",
            "preview_image": "concepts/preview.png",
            "original_preview_image": "concepts/original.png",
            "image_path": "concepts/fallback.png",
        }
        self.assertEqual(sw._concept_source_image_relpath(concept), "concepts/original.png")

    def test_gemini_iteration_uses_raw_source_image_bytes(self):
        source = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((8, 8, 56, 56), fill=(200, 10, 10, 255))
        source_buf = io.BytesIO()
        source.save(source_buf, format="PNG")
        source_bytes = source_buf.getvalue()

        generated = source.copy()
        generated_draw = ImageDraw.Draw(generated)
        generated_draw.rectangle((18, 14, 30, 22), fill=(10, 10, 200, 255))
        generated_buf = io.BytesIO()
        generated.save(generated_buf, format="PNG")

        captured = {}

        fake_response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=generated_buf.getvalue()))]
                    )
                )
            ]
        )
        def fake_from_bytes(*, data, mime_type):
            captured["image_bytes"] = data
            captured["mime_type"] = mime_type
            return SimpleNamespace(data=data, mime_type=mime_type)

        def fake_generate_content(**kwargs):
            captured["contents"] = kwargs["contents"]
            return fake_response

        fake_client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=fake_generate_content
            )
        )

        brief = {
            "raw_prompt": "a vigilant ranger with a lantern",
            "role_archetype": "ashen hollow ranger",
            "silhouette_intent": "broad guarded profile",
            "outfit_materials": "weathered plate over travel cloth",
            "prop": "lantern",
            "palette_mood": "storm steel",
            "shape_language": "balanced angular to rounded mix",
            "mood_tone": "watchful and haunted",
        }

        with patch.object(sw, "get_gemini_client", return_value=fake_client), \
             patch.object(sw._google_genai_types.Part, "from_bytes", side_effect=fake_from_bytes):
            out_bytes = sw.gemini_iterate_concept(
                source_bytes,
                "expression",
                "make the eyes brighter",
                brief,
            )

        out = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
        self.assertEqual(captured["image_bytes"], source_bytes)
        self.assertEqual(captured["mime_type"], "image/png")
        self.assertEqual(out.getpixel((20, 16)), (10, 10, 200, 255))
        self.assertIn("Aspect to change: expression", captured["contents"][1])
        self.assertIn("User request: make the eyes brighter", captured["contents"][1])

    def test_validate_prompt_constraints_allows_negated_multi_view_terms(self):
        sw.validate_prompt_constraints("strict side view, not front view, one character only")
        sw.validate_prompt_constraints("single side-view knight, no front view please")
        sw.validate_prompt_constraints("avoid rear view and turnaround sheet")

    def test_validate_prompt_constraints_rejects_positive_multi_view_terms(self):
        with self.assertRaisesRegex(ValueError, "highly asymmetric multi-view requirements"):
            sw.validate_prompt_constraints("front view knight turnaround")

    def test_prepare_pixellab_character_color_source_fits_subject_to_canvas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "concept.png"
            image = Image.new("RGBA", (640, 768), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((220, 120, 420, 700), fill=(180, 120, 90, 255))
            image.save(source_path)

            prepared = sw.prepare_pixellab_character_color_source(source_path, 64)

            self.assertEqual(prepared.size, (64, 64))
            self.assertGreater(sw.detect_mask(prepared).getbbox()[2], 0)

    def test_prepare_pixellab_concept_init_image_fits_to_128_canvas(self):
        image = Image.new("RGBA", (320, 180), (30, 40, 50, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((90, 20, 230, 170), fill=(200, 180, 120, 255))
        buf = io.BytesIO()
        image.save(buf, format="PNG")

        prepared = sw.prepare_pixellab_concept_init_image(buf.getvalue(), 128)

        self.assertEqual(prepared.size, (128, 128))
        self.assertIsNotNone(sw.detect_mask(prepared).getbbox())

    def test_pixellab_client_encode_image_rgba_returns_raw_pixel_bytes(self):
        image = Image.new("RGBA", (64, 64), (10, 20, 30, 255))
        client = pl.PixelLabClient(api_key="test-key")
        encoded = client.encode_image_rgba(image)
        raw = base64.b64decode(encoded)
        self.assertEqual(len(raw), 64 * 64 * 4)

    def test_pixellab_client_edit_animation_v2_wraps_string_frames(self):
        client = pl.PixelLabClient(api_key="test-key")
        captured = {}

        def fake_request(method, path, payload=None):
            captured["method"] = method
            captured["path"] = path
            captured["payload"] = payload
            return {"ok": True}

        with patch.object(client, "_request_json", side_effect=fake_request):
            client.edit_animation_v2(
                "tighten the slash timing",
                ["ZmFrZS1mcmFtZS0w", "ZmFrZS1mcmFtZS0x"],
                {"width": 128, "height": 128},
            )

        self.assertEqual(captured["path"], "/v2/edit-animation-v2")
        frames = captured["payload"]["frames"]
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["image"]["type"], "base64")
        self.assertEqual(frames[0]["image"]["format"], "png")
        self.assertEqual(frames[0]["size"], {"width": 128, "height": 128})

    def test_resolve_animation_timing_defaults_unknown_clips_to_8_frames(self):
        timing = sw._resolve_animation_timing("attack")
        self.assertEqual(timing["frame_count"], 8)
        self.assertEqual(timing["fps"], 12)

    def test_chunk_frame_indices_splits_edit_requests_into_four_frame_batches(self):
        self.assertEqual(sw.chunk_frame_indices(0), [])
        self.assertEqual(sw.chunk_frame_indices(3), [[0, 1, 2]])
        self.assertEqual(sw.chunk_frame_indices(8), [[0, 1, 2, 3], [4, 5, 6, 7]])
        self.assertEqual(sw.chunk_frame_indices(9), [[0, 1, 2, 3], [4, 5, 6, 7], [8]])

    def test_gemini_iteration_returns_model_output_without_tool_compositing(self):
        source = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((8, 8, 56, 56), fill=(200, 10, 10, 255))
        source_buf = io.BytesIO()
        source.save(source_buf, format="PNG")

        generated = source.copy()
        generated.putpixel((2, 50), (10, 10, 200, 255))
        generated_buf = io.BytesIO()
        generated.save(generated_buf, format="PNG")

        fake_response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=generated_buf.getvalue()))]
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: fake_response
            )
        )

        brief = {
            "raw_prompt": "a vigilant ranger with a lantern",
            "role_archetype": "ashen hollow ranger",
            "silhouette_intent": "broad guarded profile",
            "outfit_materials": "weathered plate over travel cloth",
            "prop": "lantern",
            "palette_mood": "storm steel",
            "shape_language": "balanced angular to rounded mix",
            "mood_tone": "watchful and haunted",
        }

        with patch.object(sw, "get_gemini_client", return_value=fake_client):
            out_bytes = sw.gemini_iterate_concept(
                source_buf.getvalue(),
                "expression",
                "make the eyes brighter",
                brief,
            )

        out = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
        self.assertEqual(out.getpixel((2, 50)), (10, 10, 200, 255))

    def test_scaffold_build_prompt_endpoint_returns_scaffold_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Scaffold Endpoint Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/build-prompt",
                        body=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)
                    self.assertIn("display_prompt", data)
                    self.assertIn("pixellab_params", data)
                    self.assertIn("debug_constraints", data)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_generate_pixellab_endpoint_debug_writes_concept(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Generate Pixellab Endpoint Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/build-prompt",
                        body=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)
                    pixellab_params = data["pixellab_params"]

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/generate-pixellab",
                        body=json.dumps({"pixellab_params": pixellab_params, "mode": "v2"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    response2 = connection.getresponse()
                    raw2 = response2.read().decode("utf-8")
                    created = json.loads(raw2)

                    concept_id = created["concept_id"]
                    expected_png = project_dir / "concepts" / f"{concept_id}.png"
                    self.assertTrue(expected_png.exists())
                    self.assertEqual(created["preview_image"], str(expected_png.relative_to(project_dir)))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_generate_pixellab_endpoint_debug_with_init_upload_records_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Generate Pixellab Init Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                source = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
                draw = ImageDraw.Draw(source)
                draw.rectangle((100, 20, 220, 170), fill=(180, 120, 90, 255))
                source_buf = io.BytesIO()
                source.save(source_buf, format="PNG")
                source_data_url = "data:image/png;base64,%s" % base64.b64encode(source_buf.getvalue()).decode("ascii")

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/build-prompt",
                        body=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    data = json.loads(response.read().decode("utf-8"))
                    pixellab_params = data["pixellab_params"]

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/generate-pixellab",
                        body=json.dumps({
                            "pixellab_params": pixellab_params,
                            "mode": "pixflux",
                            "init_image_name": "custom-source.png",
                            "init_image_data_url": source_data_url,
                        }).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    response2 = connection.getresponse()
                    created = json.loads(response2.read().decode("utf-8"))

                    self.assertEqual(created["concept_source_mode"], "custom_init_image")
                    self.assertTrue(created["init_source_image"])
                    init_path = project_dir / created["init_source_image"]
                    self.assertTrue(init_path.exists())
                    self.assertEqual(Image.open(init_path).size, (128, 128))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_load_project_backfills_preview_image_from_original_preview_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Preview Fallback Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id
                sw.write_json(project_dir / "concepts" / "concept-0002.json", {
                    "concept_id": "concept-0002",
                    "created_at": sw.now_iso(),
                    "run_kind": "pixellab_generate",
                    "original_preview_image": "concepts/concept-0002.png",
                    "processed_preview_image": None,
                    "review_state": {"approved": False, "favorite": False, "rejected": False},
                })

                loaded = sw.load_project(project_id)
                concept = next(item for item in loaded["concepts"] if item["concept_id"] == "concept-0002")
                self.assertEqual(concept["preview_image"], "concepts/concept-0002.png")
                self.assertEqual(concept["approved_source_image"], "concepts/concept-0002.png")
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_iterate_pixellab_endpoint_debug_writes_concept_and_lineage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                # Create a project and an initial approved concept we can iterate on.
                project = sw.create_project({
                    "project_name": "Iterate Pixellab Endpoint Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]

                source_project = self.import_valid_manual_concept(project_id)
                source_concept_id = next(item["concept_id"] for item in source_project["concepts"] if item.get("preview_image"))
                project_dir = sw.PROJECTS_ROOT / project_id

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/build-iteration-prompt",
                        body=json.dumps({
                            "concept_id": source_concept_id,
                            "element": "outfit",
                            "change_text": "make the cape longer and more tattered",
                        }).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    raw = resp.read().decode("utf-8")
                    scaffold = json.loads(raw)
                    pixellab_params = scaffold["pixellab_params"]

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/iterate-pixellab",
                        body=json.dumps({"concept_id": source_concept_id, "pixellab_params": pixellab_params}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp2 = connection.getresponse()
                    raw2 = resp2.read().decode("utf-8")
                    created = json.loads(raw2)

                    concept_id = created["concept_id"]
                    expected_png = project_dir / "concepts" / f"{concept_id}.png"
                    self.assertTrue(expected_png.exists())
                    self.assertEqual(created["lineage"]["parent_concept_id"], source_concept_id)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_create_character_pixellab_debug_writes_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Create Character Pixellab Endpoint Hero",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]

                # Generate an initial concept via our debug-safe pixellab endpoint flow.
                project_dir = sw.PROJECTS_ROOT / project_id
                build_scaffold = sw.build_concept_prompt(project["brief"])
                pixellab_params = build_scaffold["pixellab_params"]

                # Call server endpoints to mirror real HTTP flow (CORS path usage).
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/generate-pixellab",
                        body=json.dumps({"pixellab_params": pixellab_params, "mode": "v2"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    raw = resp.read().decode("utf-8")
                    created = json.loads(raw)
                    concept_id = created["concept_id"]

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/create-character",
                        body=json.dumps({"directions": 4, "color_concept_id": concept_id, "seed": 123}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp2 = connection.getresponse()
                    raw2 = resp2.read().decode("utf-8")
                    if resp2.status >= 400:
                        raise AssertionError(f"create-character HTTP {resp2.status}: {raw2}")
                    char_data = json.loads(raw2)

                    char_path = project_dir / "pixellab_character.json"
                    self.assertTrue(char_path.exists())
                    self.assertEqual(char_data.get("approved"), False)
                    self.assertEqual(char_data.get("image_size"), {"width": 128, "height": 128})

                    # Directions should exist for 4-dir.
                    expected_dirs = ["south", "west", "east", "north"]
                    assets_dir = project_dir / "character"
                    for d in expected_dirs:
                        self.assertTrue((assets_dir / f"{d}.png").exists())

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/estimate-skeleton",
                        body=json.dumps({"direction": "east", "seed": 456}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp3 = connection.getresponse()
                    raw3 = resp3.read().decode("utf-8")
                    skel_data = json.loads(raw3)
                    self.assertTrue((project_dir / "pixellab_skeleton.json").exists())
                    self.assertEqual(len(skel_data.get("skeleton_keypoints") or []), 18)

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/approve-character",
                        body=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                    resp4 = connection.getresponse()
                    raw4 = resp4.read().decode("utf-8")
                    approved = json.loads(raw4)
                    self.assertEqual(approved.get("approved"), True)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_pixellab_animate_rejects_unapproved_character(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixellab Animate Approval Gate",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                project_dir.joinpath("pixellab_character.json").write_text(json.dumps({
                    "character_id": "debug-char-1",
                    "pixellab_character_approved": False,
                    "approved": False,
                    "directions": ["south", "west", "east", "north"],
                    "image_size": {"width": 64, "height": 64},
                    "backend_name": "debug_procedural",
                    "seed": 1,
                    "images": {},
                }), encoding="utf-8")

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/animate",
                        body=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self.assertGreaterEqual(resp.status, 400)
                    self.assertFalse(data.get("ok", True))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_pixellab_use_concept_as_east_character_copies_selected_concept(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixellab East Source",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                scaffold = sw.build_concept_prompt(project.get("brief") or {})
                pixellab_params = scaffold["pixellab_params"]

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/concepts/generate-pixellab",
                        body=json.dumps({"pixellab_params": pixellab_params, "mode": "v2"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    created = json.loads(resp.read().decode("utf-8"))
                    concept_id = created["concept_id"]

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/use-concept-character",
                        body=json.dumps({"concept_id": concept_id}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp2 = connection.getresponse()
                    raw2 = resp2.read().decode("utf-8")
                    if resp2.status >= 400:
                        raise AssertionError(f"use-concept-character HTTP {resp2.status}: {raw2}")
                    char_data = json.loads(raw2)

                    self.assertEqual(char_data.get("directions"), ["east"])
                    self.assertTrue(char_data.get("east_only_source"))
                    self.assertEqual(char_data.get("image_size"), {"width": 128, "height": 128})
                    east_rel = (char_data.get("images") or {}).get("east")
                    self.assertTrue(east_rel)
                    east_path = project_dir / east_rel
                    self.assertTrue(east_path.exists())
                    with Image.open(east_path) as east_img:
                        self.assertEqual(east_img.size, (128, 128))

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/estimate-skeleton",
                        body=json.dumps({"direction": "east", "seed": 456}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp3 = connection.getresponse()
                    skel_data = json.loads(resp3.read().decode("utf-8"))
                    self.assertEqual(len(skel_data.get("skeleton_keypoints") or []), 18)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_load_project_normalizes_legacy_east_only_character_source_to_concept_canvas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Normalize East Only Character",
                    "prompt_text": "a side-view armored knight",
                    "backend_mode": "pixellab",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                concepts_dir = project_dir / "concepts"
                concepts_dir.mkdir(parents=True, exist_ok=True)
                concept_png = concepts_dir / "concept-0001.png"
                Image.new("RGBA", (2048, 2048), (0, 0, 0, 0)).save(concept_png)
                concept_json = concepts_dir / "concept-0001.json"
                concept_json.write_text(json.dumps({
                    "concept_id": "concept-0001",
                    "created_at": sw.now_iso(),
                    "preview_image": str(concept_png.relative_to(project_dir)),
                    "original_preview_image": str(concept_png.relative_to(project_dir)),
                    "prompt_text": "legacy concept",
                }, indent=2), encoding="utf-8")

                char_dir = project_dir / "character"
                char_dir.mkdir(parents=True, exist_ok=True)
                east_png = char_dir / "east.png"
                Image.new("RGBA", (2048, 2048), (30, 60, 90, 255)).save(east_png)
                (project_dir / "pixellab_character.json").write_text(json.dumps({
                    "approved": True,
                    "east_only_source": True,
                    "directions": ["east"],
                    "image_size": {"width": 2048, "height": 2048},
                    "source_concept_id": "concept-0001",
                    "images": {"east": str(east_png.relative_to(project_dir))},
                }, indent=2), encoding="utf-8")
                (project_dir / "pixellab_skeleton.json").write_text(json.dumps({
                    "approved": False,
                    "direction": "east",
                    "image_size": {"width": 2048, "height": 2048},
                    "skeleton_keypoints": [],
                }, indent=2), encoding="utf-8")
                anim_dir = project_dir / "animations" / "attack" / "east"
                anim_dir.mkdir(parents=True, exist_ok=True)
                frame_png = anim_dir / "frame_00.png"
                Image.new("RGBA", (64, 64), (200, 100, 50, 255)).save(frame_png)
                (project_dir / "pixellab_animations.json").write_text(json.dumps({
                    "animations": {
                        "attack": {
                            "animation_name": "attack",
                            "directions": {
                                "east": {
                                    "frames": [str(frame_png.relative_to(project_dir))],
                                    "frame_count": 1,
                                    "fps": 12,
                                }
                            },
                        }
                    }
                }, indent=2), encoding="utf-8")

                loaded = sw.load_project(project_id)
                self.assertEqual(loaded["pixellab_character"]["image_size"], {"width": 128, "height": 128})
                with Image.open(project_dir / "character" / "east.png") as east_img:
                    self.assertEqual(east_img.size, (128, 128))
                with Image.open(frame_png) as anim_img:
                    self.assertEqual(anim_img.size, (128, 128))
                self.assertIsNone(loaded["pixellab_skeleton"])
                self.assertFalse((project_dir / "pixellab_skeleton.json").exists())
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_pixellab_template_animation_rejects_east_only_concept_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixellab East Source Animate Gate",
                    "prompt_text": "a vigilant ranger with a lantern",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                assets_dir = project_dir / "character"
                assets_dir.mkdir(parents=True, exist_ok=True)
                east_path = assets_dir / "east.png"
                Image.new("RGBA", (64, 64), (20, 40, 60, 255)).save(east_path)
                project_dir.joinpath("pixellab_character.json").write_text(json.dumps({
                    "approved": True,
                    "east_only_source": True,
                    "directions": ["east"],
                    "images": {"east": str(east_path.relative_to(project_dir))},
                }, indent=2), encoding="utf-8")
                project["pixellab_character_approved"] = True
                sw.save_project(project)

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/animate",
                        body=json.dumps({"template_animation_id": "walking-4-frames", "animation_name": "walk", "directions": 4}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    raw = resp.read().decode("utf-8")
                    self.assertGreaterEqual(resp.status, 400)
                    self.assertIn("east-only source image", raw)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_pixellab_animate_custom_debug_writes_frames_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixellab Animate Custom Debug",
                    "prompt_text": "a side-view lantern knight",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id

                brief = project.get("brief") or {}
                canvas_size = sw.coerce_canvas_size(brief.get("canvas_size"), sw.DEFAULT_CANVAS_SIZE)
                directions = ["south", "west", "east", "north"]

                (project_dir / "character").mkdir(parents=True, exist_ok=True)
                images = sw.debug_pixellab_character_images(directions, canvas_size, seed=123)
                for d, img in images.items():
                    img.save(project_dir / "character" / ("%s.png" % d))

                char_payload = {
                    "character_id": "debug-char-1",
                    "pixellab_character_approved": True,
                    "approved": True,
                    "directions": directions,
                    "image_size": {"width": canvas_size, "height": canvas_size},
                    "backend_name": "debug_procedural",
                    "seed": 123,
                    "images": {d: str((project_dir / "character" / ("%s.png" % d)).relative_to(project_dir)) for d in directions},
                }
                (project_dir / "pixellab_character.json").write_text(json.dumps(char_payload, indent=2), encoding="utf-8")

                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/animate-custom",
                        body=json.dumps({"action": "make him wave", "animation_name": "idle", "seed": 999}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = connection.getresponse()
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    if resp.status >= 400:
                        raise AssertionError(f"animate-custom HTTP {resp.status}: {raw}")
                    self.assertTrue(data.get("ok"))

                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/animate-custom",
                        body=json.dumps({"action": "walking forward", "animation_name": "walk", "seed": 1000}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp_w = connection.getresponse()
                    raw_w = resp_w.read().decode("utf-8")
                    data_w = json.loads(raw_w)
                    if resp_w.status >= 400:
                        raise AssertionError(f"animate-custom walk HTTP {resp_w.status}: {raw_w}")
                    self.assertTrue(data_w.get("ok"))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()

                frame0 = project_dir / "animations" / "idle" / "east" / "frame_00.png"
                frame_last = project_dir / "animations" / "idle" / "east" / "frame_05.png"
                self.assertTrue(frame0.exists())
                self.assertTrue(frame_last.exists())

                store_path = project_dir / "pixellab_animations.json"
                self.assertTrue(store_path.exists())
                store = json.loads(store_path.read_text(encoding="utf-8"))
                self.assertIn("idle", store.get("animations", {}))
                dirs = store["animations"]["idle"].get("directions", {})
                self.assertIn("east", dirs)
                self.assertEqual(len(dirs["east"].get("frames") or []), 6)
                self.assertIn("walk", store.get("animations", {}))
                wdirs = store["animations"]["walk"].get("directions", {})
                self.assertIn("east", wdirs)
                self.assertGreater(len(wdirs["east"].get("frames") or []), 0)

                # Build animation clips.
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), sw.SpriteWorkbenchHandler)
                except PermissionError:
                    self.skipTest("Sandbox does not allow binding a local socket.")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                    connection.request(
                        "POST",
                        f"/api/projects/{project_id}/pixellab/build-clips",
                        body=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp2 = connection.getresponse()
                    raw2 = resp2.read().decode("utf-8")
                    if resp2.status >= 400:
                        raise AssertionError(f"build-clips HTTP {resp2.status}: {raw2}")
                    self.assertTrue(json.loads(raw2).get("ok"))
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()

                clips_path = project_dir / "animation_clips.json"
                self.assertTrue(clips_path.exists())
                clips = json.loads(clips_path.read_text(encoding="utf-8"))
                self.assertIn("idle", clips)
                self.assertIn("walk", clips)
                self.assertIn("frames", clips["idle"])
                self.assertEqual(len(clips["idle"]["frames"]), 6)
                self.assertIn("animations/idle/east/frame_00.png", clips["idle"]["frames"][0])
                self.assertIn("frames", clips["walk"])
                self.assertGreater(len(clips["walk"]["frames"]), 0)

                # Phase 6: Pixel Lab QA + export integration.
                qa = sw.run_qa(project_id)
                self.assertEqual(qa.get("status"), "pass")
                export = sw.export_project(project_id)
                self.assertIn("spritesheet.png", export.get("files") or [])
                self.assertIn("atlas.json", export.get("files") or [])
                self.assertIn("animations.json", export.get("files") or [])
                self.assertIn("animation_sheets/idle.png", export.get("files") or [])
                self.assertIn("idle", export.get("animation_sheets") or {})
                self.assertIn("export_manifest.json", export.get("files") or [])
                self.assertIn("preview_idle.gif", export.get("files") or [])
                self.assertIn("preview_walk.gif", export.get("files") or [])
                self.assertEqual(export.get("preview_gif"), None)
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_pixellab_run_qa_fails_when_frame_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Pixellab QA Missing Frame",
                    "prompt_text": "a side-view lantern knight",
                    "backend_mode": "debug_procedural",
                    "last_ui_mode": "wizard",
                })
                project_id = project["project_id"]
                project_dir = sw.PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = sw.coerce_canvas_size(brief.get("canvas_size"), sw.DEFAULT_CANVAS_SIZE)
                frame_count = sw.ANIMATION_SPECS["idle"]["frame_count"]
                fps = sw.ANIMATION_SPECS["idle"]["fps"]
                walk_fc = sw.ANIMATION_SPECS["walk"]["frame_count"]
                walk_fps = sw.ANIMATION_SPECS["walk"]["fps"]

                directions = ["south", "west", "east", "north"]
                assets = sw.debug_pixellab_character_images(directions, canvas_size, seed=1)
                (project_dir / "character").mkdir(parents=True, exist_ok=True)
                for d, img in assets.items():
                    img.save(project_dir / "character" / ("%s.png" % d))

                char_payload = {
                    "character_id": "debug-char-qa",
                    "pixellab_character_approved": True,
                    "approved": True,
                    "directions": directions,
                    "image_size": {"width": canvas_size, "height": canvas_size},
                    "backend_name": "debug_procedural",
                    "seed": 1,
                    "images": {d: str((project_dir / "character" / ("%s.png" % d)).relative_to(project_dir)) for d in directions},
                }
                (project_dir / "pixellab_character.json").write_text(json.dumps(char_payload, indent=2), encoding="utf-8")

                # Write idle/east and walk/east frames (QA requires both clips in store).
                frames_dir = project_dir / "animations" / "idle" / "east"
                frames_dir.mkdir(parents=True, exist_ok=True)
                frame_rel_paths = []
                frames = sw.debug_pixellab_animation_frames(
                    animation_name="idle",
                    direction="east",
                    canvas_size=canvas_size,
                    frame_count=frame_count,
                    seed=3,
                    description_hint="qa",
                )
                for idx, img in enumerate(frames):
                    path = frames_dir / ("frame_%02d.png" % idx)
                    img.save(path)
                    frame_rel_paths.append(str(path.relative_to(project_dir)))

                walk_frames_dir = project_dir / "animations" / "walk" / "east"
                walk_frames_dir.mkdir(parents=True, exist_ok=True)
                walk_rel_paths = []
                walk_frames = sw.debug_pixellab_animation_frames(
                    animation_name="walk",
                    direction="east",
                    canvas_size=canvas_size,
                    frame_count=walk_fc,
                    seed=4,
                    description_hint="qa-walk",
                )
                for idx, img in enumerate(walk_frames):
                    path = walk_frames_dir / ("frame_%02d.png" % idx)
                    img.save(path)
                    walk_rel_paths.append(str(path.relative_to(project_dir)))

                # Create pixellab_animations.json with idle + walk.
                pix_store = {
                    "project_id": project_id,
                    "updated_at": sw.now_iso(),
                    "animations": {
                        "idle": {
                            "animation_name": "idle",
                            "fps": fps,
                            "frame_count": frame_count,
                            "loop": True,
                            "backend_name": "debug_procedural",
                            "seed": 3,
                            "template_animation_id": None,
                            "updated_at": sw.now_iso(),
                            "directions": {
                                "east": {
                                    "frames": frame_rel_paths,
                                    "frame_count": frame_count,
                                    "fps": fps,
                                    "updated_at": sw.now_iso(),
                                }
                            },
                        },
                        "walk": {
                            "animation_name": "walk",
                            "fps": walk_fps,
                            "frame_count": walk_fc,
                            "loop": True,
                            "backend_name": "debug_procedural",
                            "seed": 4,
                            "template_animation_id": None,
                            "updated_at": sw.now_iso(),
                            "directions": {
                                "east": {
                                    "frames": walk_rel_paths,
                                    "frame_count": walk_fc,
                                    "fps": walk_fps,
                                    "updated_at": sw.now_iso(),
                                }
                            },
                        },
                    },
                }
                (project_dir / "pixellab_animations.json").write_text(json.dumps(pix_store, indent=2), encoding="utf-8")

                # animation_clips.json is the canonical bridge.
                anim_clips = {
                    "idle": {
                        "fps": fps,
                        "loop": True,
                        "frame_count": frame_count,
                        "frames": frame_rel_paths,
                        "frames_by_direction": {"east": frame_rel_paths},
                    },
                    "walk": {
                        "fps": walk_fps,
                        "loop": True,
                        "frame_count": walk_fc,
                        "frames": walk_rel_paths,
                        "frames_by_direction": {"east": walk_rel_paths},
                    },
                }
                (project_dir / "animation_clips.json").write_text(json.dumps(anim_clips, indent=2), encoding="utf-8")

                # Delete one frame to force QA failure.
                missing = project_dir / frame_rel_paths[0]
                missing.unlink(missing_ok=True)

                with self.assertRaises(ValueError):
                    sw.run_qa(project_id)
            finally:
                sw.PROJECTS_ROOT = original_root

    def test_manual_animation_clip_create_persists_named_clip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Attack Slash",
                    "frame_count": 5,
                    "fps": 14,
                    "loop": False,
                })
                reloaded = sw.load_project(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        stored = reloaded["manual_animation_clips"]["clips"][clip["clip_id"]]
        self.assertEqual(stored["clip_name"], "Attack Slash")
        self.assertEqual(stored["frame_count"], 5)
        self.assertEqual(stored["fps"], 14)
        self.assertFalse(stored["loop"])
        self.assertEqual(len(stored["frames"]), 5)
        self.assertIn("transforms", stored["frames"][0])
        self.assertIn("part_repairs", stored["frames"][0])
        self.assertIn("corrective_patches", stored["frames"][0])
        self.assertEqual(stored["approval_status"], "draft")

    def test_manual_animation_clip_render_preview_and_approve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Attack Slash",
                    "frame_count": 4,
                    "fps": 12,
                })
                updated = sw.update_manual_animation_clip_frame(project["project_id"], clip["clip_id"], 0, {
                    "transforms": {
                        "root_offset": [6, -4],
                        "head_rotation": 8,
                        "shoulder_front_rotation": -12,
                        "hip_front_rotation": 10,
                        "weapon_rotation": 6,
                    },
                })
                rendered = sw.render_manual_animation_clip_preview(project["project_id"], clip["clip_id"])
                approved = sw.approve_manual_animation_clip(project["project_id"], clip["clip_id"], True)
                project_dir = sw.PROJECTS_ROOT / project["project_id"]
                gif_exists = (project_dir / rendered["preview_render"]["gif_path"]).exists()
                manifest_exists = (project_dir / rendered["preview_render"]["render_manifest_path"]).exists()
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(updated["frames"][0]["transforms"]["head_rotation"], 8.0)
        self.assertTrue(gif_exists)
        self.assertTrue(manifest_exists)
        self.assertEqual(rendered["preview_render"]["status"], "complete")
        self.assertTrue(rendered["preview_render_complete"])
        self.assertEqual(approved["approval_status"], "approved")
        self.assertIsNotNone(approved["approved_at"])

    def test_manual_animation_clip_frame_repair_generate_apply_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                repair_part = next(
                    (
                        part["part_name"]
                        for part in project["sprite_model"]["parts"]
                        if sw.canonical_sprite_part_role(part, project["rig"]["rig_profile"]) == "weapon"
                    ),
                    project["sprite_model"]["parts"][0]["part_name"],
                )
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Repair Slash",
                    "frame_count": 2,
                    "fps": 12,
                })
                generated = sw.generate_manual_animation_clip_frame_repair(project["project_id"], clip["clip_id"], 0, repair_part)
                self.assertGreaterEqual(len(generated["variants"]), 1)
                applied = sw.apply_manual_animation_clip_frame_repair(project["project_id"], clip["clip_id"], 0, repair_part, generated["variants"][0])
                rendered = sw.render_manual_animation_clip_preview(project["project_id"], clip["clip_id"])
                manifest = sw.load_json((Path(tmpdir) / project["project_id"] / rendered["preview_render"]["render_manifest_path"]))
                cleared = sw.clear_manual_animation_clip_frame_repair(project["project_id"], clip["clip_id"], 0, repair_part)
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertIn(repair_part, applied["frame"]["part_repairs"])
        self.assertEqual(rendered["preview_render"]["status"], "complete")
        self.assertTrue(rendered["preview_render"]["frames"][0].endswith(".png"))
        self.assertIn("part_repairs", manifest["frames"][0])
        self.assertIn(repair_part, manifest["frames"][0]["part_repairs"])
        self.assertNotIn(repair_part, cleared["frame"]["part_repairs"])

    def test_manual_animation_clip_frame_patch_generate_apply_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                ordered_parts = sorted(project["sprite_model"]["parts"], key=lambda item: int(item.get("draw_order", 0)))
                source_part = ordered_parts[0]["part_name"]
                keep_behind_part = next(
                    (
                        part["part_name"]
                        for part in ordered_parts[1:]
                        if int(part.get("draw_order", 0)) >= int(ordered_parts[0].get("draw_order", 0))
                    ),
                    ordered_parts[-1]["part_name"],
                )
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Patch Slash",
                    "frame_count": 2,
                    "fps": 12,
                })
                generated = sw.generate_manual_animation_clip_frame_patch(project["project_id"], clip["clip_id"], 0, source_part)
                self.assertGreaterEqual(len(generated["variants"]), 1)
                applied = sw.apply_manual_animation_clip_frame_patch(
                    project["project_id"],
                    clip["clip_id"],
                    0,
                    source_part,
                    {
                        **generated["variants"][0],
                        "keep_behind_part_name": keep_behind_part,
                    },
                )
                rendered = sw.render_manual_animation_clip_preview(project["project_id"], clip["clip_id"])
                manifest = sw.load_json((Path(tmpdir) / project["project_id"] / rendered["preview_render"]["render_manifest_path"]))
                cleared = sw.clear_manual_animation_clip_frame_patch(project["project_id"], clip["clip_id"], 0, source_part)
            finally:
                sw.PROJECTS_ROOT = original_root

        patch_id = "patch:%s" % source_part
        self.assertIn(patch_id, applied["frame"]["corrective_patches"])
        self.assertEqual(rendered["preview_render"]["status"], "complete")
        self.assertIn("corrective_patches", manifest["frames"][0])
        self.assertIn(patch_id, manifest["frames"][0]["corrective_patches"])
        draw_sequence = manifest["frames"][0]["render_meta"]["draw_sequence"]
        self.assertLess(draw_sequence.index(patch_id), draw_sequence.index(keep_behind_part))
        self.assertNotIn(patch_id, cleared["frame"]["corrective_patches"])

    def test_manual_animation_clip_stales_after_rig_rebuild_and_blocks_reapprove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Attack Slash",
                    "frame_count": 3,
                })
                sw.render_manual_animation_clip_preview(project["project_id"], clip["clip_id"])
                sw.approve_manual_animation_clip(project["project_id"], clip["clip_id"], True)
                sw.build_rig(project["project_id"])
                reloaded = sw.load_project(project["project_id"])

                stale = reloaded["manual_animation_clips"]["clips"][clip["clip_id"]]
                with self.assertRaisesRegex(ValueError, "re-rendered against the current rig and sprite model"):
                    sw.approve_manual_animation_clip(project["project_id"], clip["clip_id"], True)
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertTrue(stale["is_stale"])
        self.assertIn("rig changed", stale["stale_reasons"])

    def test_export_includes_approved_manual_clips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = self.build_debug_pipeline(tmpdir)
                clip = sw.create_manual_animation_clip(project["project_id"], {
                    "clip_name": "Attack Slash",
                    "frame_count": 4,
                    "fps": 12,
                })
                sw.render_manual_animation_clip_preview(project["project_id"], clip["clip_id"])
                sw.approve_manual_animation_clip(project["project_id"], clip["clip_id"], True)
                sw.render_animation(project["project_id"], "idle")
                sw.render_animation(project["project_id"], "walk")
                qa_report = sw.run_qa(project["project_id"])
                export_result = sw.export_project(project["project_id"])
                project_dir = sw.PROJECTS_ROOT / project["project_id"]
                animations_payload = sw.load_json(project_dir / export_result["export_dir"] / "animations.json", {})
                # Assert on disk before tempdir is torn down (with-block exit deletes tmpdir).
                self.assertEqual(qa_report["status"], "pass")
                self.assertIn(clip["clip_id"], animations_payload)
                self.assertEqual(animations_payload[clip["clip_id"]]["frame_count"], 4)
                self.assertIn("animation_sheets", export_result)
                self.assertIn(clip["clip_id"], export_result["animation_sheets"])
                self.assertTrue(any(name.startswith(f"frames/{clip['clip_id']}_") for name in export_result["files"]))
                ed = project_dir / export_result["export_dir"]
                self.assertTrue((ed / "animation_sheets" / f"{clip['clip_id']}.png").exists())
                self.assertTrue((ed / "preview_idle.gif").exists())
                self.assertTrue((ed / "preview_walk.gif").exists())
                self.assertTrue((ed / ("preview_%s.gif" % clip["clip_id"])).exists())
                self.assertFalse((ed / "preview.gif").exists())
            finally:
                sw.PROJECTS_ROOT = original_root


class PixelLabAnimationFrameExtractionTests(unittest.TestCase):
    """Regression: animation job parsing must accept WebP/JPEG, Base64Image dicts, small PNGs, and URL fallbacks."""

    def _tiny_png_b64(self) -> str:
        buf = io.BytesIO()
        Image.new("RGBA", (4, 4), (255, 0, 0, 128)).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _rgba_bytes_b64(self, color) -> str:
        return base64.b64encode(Image.new("RGBA", (4, 4), color).tobytes()).decode("ascii")

    def test_looks_like_accepts_png_data_url_and_plain_b64(self):
        png = self._tiny_png_b64()
        self.assertTrue(sw._looks_like_base64_image_string(png))
        self.assertTrue(sw._looks_like_base64_image_string("data:image/png;base64," + png))

    def test_find_extracts_nested_base64_image_objects(self):
        png = self._tiny_png_b64()
        payload = {"frames": [{"type": "base64", "base64": png, "format": "png"}]}
        found = sw._find_all_base64_png_like(payload)
        self.assertEqual(found, [png])

    def test_find_extracts_webp_when_available(self):
        buf = io.BytesIO()
        try:
            Image.new("RGBA", (2, 2), (0, 255, 0, 255)).save(buf, format="WEBP")
        except Exception:
            self.skipTest("WEBP encode not available in this PIL build")
        webp_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self.assertTrue(sw._looks_like_base64_image_string(webp_b64))
        found = sw._find_all_base64_png_like({"x": webp_b64})
        self.assertEqual(found, [webp_b64])

    def test_collect_pixellab_https_asset_urls_nested(self):
        urls = sw._collect_pixellab_https_asset_urls(
            {"out": [{"signed_url": "https://cdn.example/f1.webp"}, {"url": "http://legacy/x.png"}]}
        )
        self.assertEqual(urls, ["https://cdn.example/f1.webp", "http://legacy/x.png"])

    def test_collect_pixellab_https_storage_urls_list(self):
        urls = sw._collect_pixellab_https_asset_urls(
            {
                "storage_urls": [
                    "https://cdn.example/a.png",
                    "https://cdn.example/b.png",
                ],
                "nested": {"StorageUrls": {"0": "https://cdn.example/c.png"}},
            }
        )
        self.assertEqual(
            urls,
            ["https://cdn.example/a.png", "https://cdn.example/b.png", "https://cdn.example/c.png"],
        )

    def test_pixellab_animation_job_to_rgba_frames_prefers_images_over_quantized_images(self):
        frames = sw._pixellab_animation_job_to_rgba_frames(
            {
                "images": [
                    {"type": "rgba_bytes", "width": 4, "height": 4, "base64": self._rgba_bytes_b64((255, 0, 0, 255))}
                    for _ in range(4)
                ],
                "quantized_images": [
                    {"type": "rgba_bytes", "width": 4, "height": 4, "base64": self._rgba_bytes_b64((0, 255, 0, 255))}
                    for _ in range(4)
                ],
            },
            canvas_size=4,
            client=None,
        )
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[0].getpixel((0, 0)), (255, 0, 0, 255))

    def test_is_pixellab_api_url(self):
        self.assertTrue(sw._is_pixellab_api_url("https://api.pixellab.ai/v2/characters/x"))
        self.assertTrue(sw._is_pixellab_api_url("https://api.pixellab.ai:443/foo/bar"))
        self.assertFalse(sw._is_pixellab_api_url("https://backblaze.pixellab.ai/file/pixellab-characters/x.png"))
        self.assertFalse(sw._is_pixellab_api_url("https://supabase.pixellab.ai/storage/v1/object/public/x"))

    @patch.object(sw, "urlopen", autospec=True)
    def test_download_url_bytes_skips_bearer_on_cdn_host(self, mock_urlopen):
        inner = MagicMock()
        inner.read.return_value = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        mock_urlopen.return_value.__enter__.return_value = inner
        out = sw._download_url_bytes(
            "https://backblaze.pixellab.ai/file/pixellab-characters/bucket/key.png",
            bearer="pixellab-secret-key",
        )
        self.assertTrue(out.startswith(b"\x89PNG"))
        req = mock_urlopen.call_args[0][0]
        hdrs = dict(req.header_items())
        self.assertNotIn("Authorization", hdrs)

    @patch.object(sw, "urlopen", autospec=True)
    def test_download_url_bytes_sends_bearer_only_for_api_host(self, mock_urlopen):
        inner = MagicMock()
        inner.read.return_value = b"zip-bytes"
        mock_urlopen.return_value.__enter__.return_value = inner
        sw._download_url_bytes("https://api.pixellab.ai/v2/characters/uuid/zip", bearer="pixellab-secret-key")
        req = mock_urlopen.call_args[0][0]
        hdrs = dict(req.header_items())
        self.assertEqual(hdrs.get("Authorization"), "Bearer pixellab-secret-key")

    @patch.object(sw, "_download_url_bytes")
    def test_pixellab_animation_job_to_rgba_frames_url_fallback(self, mock_dl):
        png = self._tiny_png_b64()
        mock_dl.return_value = base64.b64decode(png)
        client = MagicMock()
        client.api_key = "test-key"
        frames = sw._pixellab_animation_job_to_rgba_frames(
            {"items": [{"url": "https://cdn.example/frame.png"}]},
            canvas_size=64,
            client=client,
        )
        self.assertEqual(len(frames), 1)
        # URL path decodes the PNG at its native size (canvas hint is for raw RGBA only).
        self.assertEqual(frames[0].size, (4, 4))
        mock_dl.assert_called_once_with("https://cdn.example/frame.png", bearer="test-key")

    @patch.object(sw, "_download_url_bytes")
    def test_pixellab_animation_job_to_rgba_frames_storage_urls(self, mock_dl):
        png = self._tiny_png_b64()
        raw = base64.b64decode(png)
        mock_dl.return_value = raw
        client = MagicMock()
        client.api_key = "test-key"
        frames = sw._pixellab_animation_job_to_rgba_frames(
            {
                "per_job_last_response": [
                    {"storage_urls": ["https://cdn.example/f0.png", "https://cdn.example/f1.png"]},
                ]
            },
            canvas_size=64,
            client=client,
        )
        self.assertEqual(len(frames), 2)
        self.assertEqual(mock_dl.call_count, 2)
        mock_dl.assert_any_call("https://cdn.example/f0.png", bearer="test-key")
        mock_dl.assert_any_call("https://cdn.example/f1.png", bearer="test-key")

    def test_merged_per_job_last_response_concatenates_frames(self):
        png = self._tiny_png_b64()
        merged = {
            "per_job_last_response": [
                {"type": "base64", "base64": png, "format": "png"},
                {"type": "base64", "base64": png, "format": "png"},
            ]
        }
        frames = sw._pixellab_animation_job_to_rgba_frames(
            merged,
            canvas_size=32,
            client=MagicMock(),
        )
        self.assertEqual(len(frames), 2)


if __name__ == "__main__":
    unittest.main()
