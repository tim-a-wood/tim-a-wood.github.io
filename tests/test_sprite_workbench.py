import http.client
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from scripts import sprite_workbench_server as sw


class SpriteWorkbenchTests(unittest.TestCase):
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
            sw.generate_run(project["project_id"], "initial")
            project = sw.load_project(project["project_id"])
            approved_concept = project["concepts"][0]["concept_id"]
            sw.update_concept_review_state(project["project_id"], approved_concept, "approve", True)
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

    def test_refine_again_does_not_complete_refine_or_unlock_master_pose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = sw.PROJECTS_ROOT
            sw.PROJECTS_ROOT = Path(tmpdir)
            try:
                created = sw.create_project({
                    "project_name": "Refine Wizard",
                    "prompt_text": "a dune guard with a curved blade",
                    "last_ui_mode": "wizard",
                })
                project = sw.load_project(created["project_id"])
                project["history"]["events"].append({
                    "type": "concept_run",
                    "run_id": "run-001",
                    "run_kind": "initial",
                    "created_at": sw.now_iso(),
                })
                project["selected_concept_id"] = "concept-0001"
                project["wizard_state"] = {
                    "current_step": "refine",
                    "completed_steps": ["project", "brief", "references", "concepts", "review"],
                    "skipped_optional_steps": ["references"],
                    "last_completed_step": "review",
                    "last_refine_decision": None,
                    "show_advanced": False,
                }
                sw.save_project(project)
                updated = sw.update_wizard_state(project["project_id"], {
                    "current_step": "refine",
                    "last_refine_decision": "refine_again",
                    "last_ui_mode": "wizard",
                })
            finally:
                sw.PROJECTS_ROOT = original_root

        self.assertEqual(updated["wizard_state"]["last_refine_decision"], "refine_again")
        self.assertNotIn("refine", updated["wizard_state"]["completed_steps"])
        self.assertEqual(updated["step_statuses"]["refine"], "active")
        self.assertEqual(updated["step_statuses"]["master_pose"], "locked")

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
                sw.generate_run(project["project_id"], "initial")
                project = sw.load_project(project["project_id"])
                sw.update_concept_review_state(project["project_id"], project["concepts"][0]["concept_id"], "approve", True)
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
                sw.generate_run(project["project_id"], "initial")
                project = sw.load_project(project["project_id"])
                sw.update_concept_review_state(project["project_id"], project["concepts"][0]["concept_id"], "approve", True)
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
                sw.generate_run(project["project_id"], "initial")
                project = sw.load_project(project["project_id"])
                sw.update_concept_review_state(project["project_id"], project["concepts"][0]["concept_id"], "approve", True)
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

    def test_refinement_strength_mapping(self):
        self.assertEqual(sw.REFINEMENT_STRENGTHS["subtle"], 0.25)
        self.assertEqual(sw.REFINEMENT_STRENGTHS["medium"], 0.45)
        self.assertEqual(sw.REFINEMENT_STRENGTHS["strong"], 0.65)

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
