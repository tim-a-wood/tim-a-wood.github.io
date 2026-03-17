import http.client
import base64
import json
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from PIL import Image, ImageDraw

from scripts import sprite_workbench_server as sw


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

    def test_create_project_in_wizard_starts_reference_step(self):
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
        self.assertEqual(project["wizard_state"]["current_step"], "references")
        self.assertIn("brief", project["wizard_state"]["completed_steps"])
        self.assertIn(project["step_statuses"]["references"], {"active", "complete"})

    def test_update_project_brief_advances_wizard_from_project_to_references(self):
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

        self.assertEqual(project["wizard_state"]["current_step"], "references")
        self.assertIn("brief", project["wizard_state"]["completed_steps"])

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
        self.assertEqual(before_valid["step_statuses"]["review"], "locked")
        self.assertIn("Codex validated as valid", before_valid["blocking_reasons"]["review"][0])
        self.assertEqual(project["step_statuses"]["review"], "complete")
        self.assertIn(project["step_statuses"]["rig_layout"], {"active", "ready"})

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
        self.assertIn(project["step_statuses"]["rig_layout"], {"active", "ready"})
        if project["ai_workflow"]["enabled"]:
            self.assertEqual(project["ai_workflow"]["selected_assets"]["approved_concept_id"], imported["concept_id"])
        else:
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
            self.assertTrue((export_dir / "preview.gif").exists())
            self.assertTrue((export_dir / "export_manifest.json").exists())

    def test_ai_workflow_health_fails_cleanly_when_comfyui_is_down(self):
        with patch.object(sw.ComfyUIConceptBackend, "healthcheck", return_value={"ok": False, "error": "connection refused", "base_url": "http://127.0.0.1:8188"}):
            health = sw.ai_workflow_health_snapshot("comfyui")
        self.assertEqual(health["overall_status"], "fail")
        self.assertEqual(health["dependencies"]["comfyui"]["status"], "fail")
        self.assertIn("connection refused", health["dependencies"]["comfyui"]["detail"])

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
        self.assertEqual(imported["validation_status"], "pending")
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
        self.assertEqual(imported["validation_status"], "pending")
        self.assertTrue(imported["validation_error"])

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
                with self.assertRaisesRegex(ValueError, "Only valid imported concepts can be accepted"):
                    sw.update_concept_review_state(project["project_id"], imported["concept_id"], "approve", True)
                project = sw.update_concept_validation(project["project_id"], imported["concept_id"], "valid")
                accepted = sw.update_concept_review_state(project["project_id"], imported["concept_id"], "approve", True)
            finally:
                sw.PROJECTS_ROOT = original_root

        accepted_attempt = next(item for item in accepted["concepts"] if item["concept_id"] == imported["concept_id"])
        self.assertEqual(accepted["selected_concept_id"], imported["concept_id"])
        self.assertTrue(accepted_attempt["accepted_for_review"])

    def test_prepare_workflow_prompt_shapes_request(self):
        template = sw.load_workflow_template("concept_txt2img.json")
        request = sw.ConceptRequest(
            project_id="demo-project",
            positive_prompt="positive prompt",
            negative_prompt="negative prompt",
            width=640,
            height=768,
            seed=1234,
            count=1,
            references=[],
            mode="initial",
        )
        prompt = sw.prepare_workflow_prompt(template, request, "demo/run", "checkpoint.safetensors", None)
        self.assertEqual(prompt["1"]["inputs"]["ckpt_name"], "checkpoint.safetensors")
        self.assertEqual(prompt["2"]["inputs"]["text"], "positive prompt")
        self.assertEqual(prompt["3"]["inputs"]["text"], "negative prompt")
        self.assertEqual(prompt["4"]["inputs"]["width"], 640)
        self.assertEqual(prompt["4"]["inputs"]["height"], 768)
        self.assertEqual(prompt["5"]["inputs"]["seed"], 1234)
        self.assertEqual(prompt["7"]["inputs"]["filename_prefix"], "demo/run")

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
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(qa_report["status"], "pass")
        self.assertIn(clip["clip_id"], animations_payload)
        self.assertEqual(animations_payload[clip["clip_id"]]["frame_count"], 4)
        self.assertTrue(any(name.startswith(f"frames/{clip['clip_id']}_") for name in export_result["files"]))


if __name__ == "__main__":
    unittest.main()
