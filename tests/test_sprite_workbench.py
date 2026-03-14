import http.client
import base64
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from http.server import ThreadingHTTPServer

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

    def import_valid_manual_concept(self, project_id: str, *, import_mode: str = "local_path"):
        prompt = sw.generate_initial_prompt(project_id)
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
        project = sw.update_concept_validation(project_id, imported["concept_id"], "valid")
        sw.update_concept_review_state(project_id, imported["concept_id"], "approve", True)
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
            sw.generate_master_pose_candidates(project["project_id"])
            project = sw.load_project(project["project_id"])
            sw.select_master_pose(project["project_id"], project["master_pose_manifest"]["candidates"][0]["candidate_id"])
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
        self.assertEqual(project["step_statuses"]["references"], "active")

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
        self.assertIn("Mark at least one imported concept valid", before_valid["blocking_reasons"]["review"][0])
        self.assertEqual(project["step_statuses"]["review"], "complete")
        self.assertEqual(project["step_statuses"]["master_pose"], "ready")

    def test_master_pose_generation_and_selection_persist_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                project = sw.create_project({
                    "project_name": "Master Pose Hero",
                    "prompt_text": "a side-view armored pilgrim with a lantern",
                    "backend_mode": "debug_procedural",
                })
                project = self.import_valid_manual_concept(project["project_id"])
                manifest = sw.generate_master_pose_candidates(project["project_id"])
                self.assertEqual(len(manifest["candidates"]), 3)
                selected = sw.select_master_pose(project["project_id"], manifest["candidates"][0]["candidate_id"])
                self.assertEqual(selected["approved_candidate_id"], manifest["candidates"][0]["candidate_id"])
                self.assertTrue((sw.PROJECTS_ROOT / project["project_id"] / "master_pose" / "approved_master_pose.png").exists())
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
                sw.generate_master_pose_candidates(project["project_id"])
                project = sw.load_project(project["project_id"])
                sw.select_master_pose(project["project_id"], project["master_pose_manifest"]["candidates"][0]["candidate_id"])
                sprite_model = sw.build_sprite_model(project["project_id"])
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(sprite_model["status"], "pass")
        self.assertEqual(len(sprite_model["parts"]), len(sw.REQUIRED_PARTS))
        self.assertEqual(sprite_model["approved_master_pose"], "master_pose/approved_master_pose.png")
        self.assertIn("swatches", sprite_model["palette"])

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
                sw.generate_master_pose_candidates(project["project_id"])
                project = sw.load_project(project["project_id"])
                sw.select_master_pose(project["project_id"], project["master_pose_manifest"]["candidates"][0]["candidate_id"])
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

        self.assertIn("Role:", result["prompt_text"])
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

        self.assertIn("Preserve the core identity from this previous prompt", improved["prompt_text"])
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


if __name__ == "__main__":
    unittest.main()
