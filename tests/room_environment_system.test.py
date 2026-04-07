from __future__ import annotations

import base64
import copy
import hashlib
import io
import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import room_environment_system as envsys
from scripts import room_environment_v3 as envv3
from scripts.environment_v3 import persistence as envv3_persistence


class RoomEnvironmentSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects_root = self.root / "tools" / "2d-sprite-and-animation" / "projects-data"
        self._old_gemini_api_key = envsys.os.environ.get("GEMINI_API_KEY")
        self._old_google_api_key = envsys.os.environ.get("GOOGLE_API_KEY")
        self._old_gemini_generate_content_rest = envsys._gemini_generate_content_rest
        # Unit tests should never spend live Gemini quota; use local stubbed responses.
        envsys.os.environ["GEMINI_API_KEY"] = "test-key"
        envsys.os.environ["GOOGLE_API_KEY"] = ""
        if not self._testMethodName.startswith("test_gemini_"):
            def _fake_gemini_generate_content_rest(_model: str, _parts, response_modalities=None):
                if response_modalities and "IMAGE" in response_modalities:
                    img = envsys.Image.new("RGBA", (96, 96), (64, 74, 86, 255))
                    out = io.BytesIO()
                    img.save(out, format="PNG")
                    payload = {
                        "candidates": [{
                            "finishReason": "STOP",
                            "content": {
                                "parts": [{
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(out.getvalue()).decode("ascii"),
                                    }
                                }]
                            },
                        }]
                    }
                    return payload, None
                payload = {
                    "candidates": [{
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "{}"}]},
                    }]
                }
                return payload, None
            envsys._gemini_generate_content_rest = _fake_gemini_generate_content_rest
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
        if self._old_gemini_api_key is None:
            envsys.os.environ.pop("GEMINI_API_KEY", None)
        else:
            envsys.os.environ["GEMINI_API_KEY"] = self._old_gemini_api_key
        if self._old_google_api_key is None:
            envsys.os.environ.pop("GOOGLE_API_KEY", None)
        else:
            envsys.os.environ["GOOGLE_API_KEY"] = self._old_google_api_key
        envsys._gemini_generate_content_rest = self._old_gemini_generate_content_rest
        self.tmp.cleanup()

    def _fake_ai_generate(self, output_path, prompt, refs, size, transparent, component_type=None):
        if output_path.name in {"foreground_frame.png", "foreground_frame-candidate.png"} or component_type in {
            "foreground_frame",
            "room_shell_foreground",
        }:
            img = envsys.Image.new("RGBA", size, envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
            draw = envsys.ImageDraw.Draw(img)
            draw.rectangle((0, 0, size[0], int(size[1] * 0.20)), fill=(84, 74, 64, 255))
            draw.rectangle((0, 0, int(size[0] * 0.20), size[1]), fill=(26, 20, 18, 255))
            draw.rectangle((int(size[0] * 0.80), 0, size[0], size[1]), fill=(26, 20, 18, 255))
            draw.rectangle((0, int(size[1] * 0.90), size[0], size[1]), fill=(90, 80, 70, 255))
            for x in range(24, int(size[0] * 0.18), 72):
                draw.line((x, int(size[1] * 0.18), x, int(size[1] * 0.88)), fill=(16, 18, 22, 255), width=4)
            for x in range(int(size[0] * 0.82), size[0] - 24, 72):
                draw.line((x, int(size[1] * 0.18), x, int(size[1] * 0.88)), fill=(16, 18, 22, 255), width=4)
        else:
            img = envsys.Image.new("RGBA", size, (40, 50, 60, 0 if transparent else 255))
        img.save(output_path)
        return True, None

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
                "top_band_darkness": 0.01,
                "top_band_contrast": 0.03,
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
        border_first = result["art_direction"]["biome_packs"][0]["border_first_contract"]
        self.assertEqual(border_first["contract_version"], envsys.BORDER_FIRST_CONTRACT_VERSION)
        self.assertEqual(border_first["status"], "schema_only")
        self.assertFalse(border_first["authoritative"])
        self.assertEqual(border_first["canonical_shell_template"], "border_piece")
        self.assertEqual(border_first["biome_component_types"], list(envsys.BORDER_FIRST_BIOME_COMPONENT_TYPES))
        self.assertEqual(border_first["room_asset_types"], list(envsys.BORDER_FIRST_ROOM_ASSET_TYPES))
        self.assertEqual(border_first["compositing"]["mode"], "deterministic_mask_composite")
        self.assertFalse(border_first["compositing"]["procedural_generation_allowed"])
        self.assertTrue(border_first["legacy_split_shell_reference_only"])
        self.assertEqual(
            [item["component_type"] for item in border_first["biome_component_specs"]],
            list(envsys.BORDER_FIRST_BIOME_COMPONENT_TYPES),
        )
        self.assertEqual(border_first["biome_templates"]["door_piece"], f"{result['art_direction']['biome_packs'][0]['biome_id']}-door_piece")
        room = self.saved["room_layout"]["rooms"][0]
        self.assertEqual(room["environment"]["preview"]["status"], "outdated")

    def test_generate_biome_pack_visuals_requires_confirm(self):
        out = envsys.generate_biome_pack_visuals(self.project_id, {})
        self.assertFalse(out.get("ok"))
        self.assertIn("confirm_overwrite", str(out.get("error", "")))

    def test_find_curated_template_source_ignores_structural_room_outputs(self):
        room_root = self.projects_root / self.project_id / "room_environment_assets" / "R1"
        room_root.mkdir(parents=True, exist_ok=True)
        (room_root / "foreground_frame.png").write_bytes(b"fake")
        self.assertIsNone(envsys._find_curated_template_source(self.project_id, "foreground_frame"))

    def test_generate_biome_pack_visuals_marks_templates_and_skips_refresh_overwrite(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_structural_biome_source", return_value=(True, [])), \
             mock.patch.object(envsys, "_validate_foreground_frame_source", return_value=(True, [])), \
             mock.patch.object(envsys, "_foreground_frame_matches_fallback_seed", return_value=False):
            out = envsys.generate_biome_pack_visuals(self.project_id, {"confirm_overwrite": True})
        self.assertTrue(out["ok"])
        self.assertTrue(out["used_ai"])
        generated_components = {row["component_type"] for row in out["results"]}
        for row in out["results"]:
            self.assertTrue(row.get("ok"), row)
        pack = out["art_direction"]["biome_packs"][0]
        for t in pack["template_library"]:
            if t["component_type"] in generated_components:
                self.assertTrue(str(t.get("biome_visual_generated_at") or "").strip())
                self.assertEqual(t.get("source_template_kind"), "gemini_biome")
        first_rel = pack["template_library"][0]["image_path"]
        path = self.projects_root / self.project_id / first_rel
        self.assertTrue(path.exists())
        marker = b"KEEP-BIOME-VISUAL"
        path.write_bytes(marker)
        envsys.get_project_art_direction(self.project_id)
        self.assertEqual(path.read_bytes(), marker)

    def test_default_biome_pack_includes_pending_border_first_templates(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        direction = envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )["art_direction"]
        pack = direction["biome_packs"][0]
        template_by_component = {
            item["component_type"]: item
            for item in pack["template_library"]
        }

        for component_type in ("border_piece", "background_far_piece", "platform_piece"):
            self.assertIn(component_type, template_by_component)
            self.assertEqual(template_by_component[component_type]["source_template_kind"], "pending_generation")
            self.assertFalse(template_by_component[component_type]["approved"])

        contract = pack["border_first_contract"]
        self.assertEqual(contract["status"], "schema_only")
        self.assertEqual(contract["biome_templates"]["border_piece"], template_by_component["border_piece"]["template_id"])
        self.assertEqual(contract["biome_templates"]["door_piece"], template_by_component["door_piece"]["template_id"])

    def test_room_environment_manifest_exposes_border_first_contract(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        spec = envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with a strong central route."},
        )
        runtime = spec["environment"]["runtime"]
        bespoke = runtime["bespoke_asset_manifest"]

        self.assertEqual(runtime["next_generation_contract"]["canonical_shell_template_type"], "border_piece")
        self.assertIn("room_border_shell", runtime["next_generation_contract"]["room_asset_types"])
        self.assertEqual(bespoke["next_generation_contract"]["canonical_shell_template_type"], "border_piece")

    def test_generate_biome_pack_visuals_can_target_specific_components_only(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        targeted = {"wall_piece", "ceiling_piece"}
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_structural_biome_source", return_value=(True, [])):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": sorted(targeted)},
            )
        self.assertTrue(out["ok"])
        self.assertEqual(set(out["component_types"]), targeted)
        self.assertEqual({row["component_type"] for row in out["results"]}, targeted)
        pack = out["art_direction"]["biome_packs"][0]
        marked = {
            t["component_type"]
            for t in pack["template_library"]
            if str(t.get("biome_visual_generated_at") or "").strip()
        }
        self.assertEqual(marked, targeted)

    def test_generate_biome_pack_visuals_can_target_foreground_frame_only(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )
        self.assertTrue(out["ok"])
        self.assertEqual(out["component_types"], ["foreground_frame"])
        self.assertEqual([row["component_type"] for row in out["results"]], ["foreground_frame"])

    def test_generate_biome_pack_visuals_can_target_border_first_components_from_pending_templates(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        targeted = {"border_piece", "background_far_piece", "platform_piece"}
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_structural_biome_source", return_value=(True, [])):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": sorted(targeted)},
            )
        self.assertTrue(out["ok"])
        self.assertEqual(set(out["component_types"]), targeted)
        self.assertEqual({row["component_type"] for row in out["results"]}, targeted)
        pack = out["art_direction"]["biome_packs"][0]
        template_by_component = {
            item["component_type"]: item
            for item in pack["template_library"]
        }
        for component_type in targeted:
            template = template_by_component[component_type]
            self.assertTrue(str(template.get("biome_visual_generated_at") or "").strip())
            self.assertEqual(template.get("source_template_kind"), "gemini_biome")
            self.assertTrue((self.projects_root / self.project_id / str(template.get("image_path") or "")).exists())

    def test_generate_biome_pack_visuals_fails_cleanly_without_gemini_key(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        with mock.patch.dict(envsys.os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )
        self.assertFalse(out["ok"])
        self.assertFalse(out["used_ai"])
        self.assertIn("GEMINI_API_KEY", out["error"])
        self.assertEqual(out["results"], [])

    def test_generate_biome_pack_visuals_uses_ephemeral_foreground_frame_guide_only_for_generation(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            key = str(component_type or output_path.stem)
            calls[key] = [path.name for path in refs]
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )

        self.assertTrue(out["ok"])
        self.assertIn("foreground_frame-guide.png", calls["foreground_frame"])
        self.assertIn("foreground_frame-style.png", calls["foreground_frame"])
        self.assertFalse((self.projects_root / self.project_id / ".tmp_biome_generation_refs" / "foreground_frame-guide.png").exists())
        self.assertFalse((self.projects_root / self.project_id / ".tmp_biome_generation_refs" / "foreground_frame-style.png").exists())
        pack = out["art_direction"]["biome_packs"][0]
        self.assertFalse(any(".tmp_biome_generation_refs" in str(t.get("image_path") or "") for t in pack["template_library"]))

    def test_generate_biome_pack_visuals_labels_foreground_frame_fallback_seed_matches(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            direction = envsys.normalize_art_direction(self.saved.get("art_direction"), self.saved.get("art_direction"))
            palette = copy.deepcopy(direction.get("palette") or {})
            spec = {
                "theme_id": str(direction.get("template_id") or ""),
                "description": str(direction.get("high_level_direction") or ""),
                "mood": str(direction.get("style_family") or ""),
                "lighting": ", ".join(direction.get("lighting_rules") or []),
                "tags": ["ruined-gothic"],
                "components": {},
            }
            flags = envsys._environment_style_flags(spec)
            shell_family = envsys._infer_shell_family(spec)
            envsys._fallback_foreground_frame_asset(output_path, palette, flags, shell_family)
            return True, None

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )

        self.assertTrue(out["ok"])
        self.assertTrue(out["used_ai"])
        self.assertEqual(out["results"][0]["error"], "foreground_frame_source_invalid")
        self.assertIn("foreground_frame_matches_fallback_seed", out["results"][0]["validation_errors"])

    def test_generate_biome_pack_visuals_does_not_self_reference_saved_foreground_frame(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            key = str(component_type or output_path.name.replace("-candidate", ""))
            calls[key] = [path.name for path in refs]
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )

        self.assertTrue(out["ok"])
        self.assertNotIn("foreground_frame.png", calls["foreground_frame"])
        self.assertIn("foreground_frame-guide.png", calls["foreground_frame"])

    def test_generate_biome_pack_visuals_does_not_feed_structural_sibling_refs_to_foreground_frame(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            key = str(component_type or output_path.name.replace("-candidate", ""))
            calls[key] = [path.name for path in refs]
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )

        self.assertTrue(out["ok"])
        names = next(iter(calls.values()))
        self.assertNotIn("primary_floor_piece.png", names)
        self.assertNotIn("wall_piece.png", names)
        self.assertNotIn("ceiling_piece.png", names)
        self.assertNotIn("hero_platform_piece.png", names)
        self.assertIn("foreground_frame-guide.png", names)

    def test_generate_biome_pack_visuals_does_not_feed_frozen_concepts_to_structural_components(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            calls[output_path.name] = [path.name for path in refs]
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["wall_piece"]},
            )

        self.assertTrue(out["ok"])
        names = next(iter(calls.values()))
        self.assertNotIn("art-direction-01.png", names)

    def test_generate_biome_pack_visuals_uses_pack_locked_concepts_for_scenic_components(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        self.saved["art_direction"]["biome_packs"][0]["locked_concept_ids"] = ["art-direction-02"]
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            calls[output_path.name] = [path.name for path in refs]
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["background_plate"]},
            )

        self.assertTrue(out["ok"])
        names = calls["background_plate.png"]
        self.assertIn("art-direction-02.png", names)
        self.assertNotIn("art-direction-01.png", names)

    def test_room_environment_preview_uses_pack_locked_concepts_when_present(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        self.saved["art_direction"]["biome_packs"][0]["locked_concept_ids"] = ["art-direction-02"]
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        captured = []

        def capture_frozen(*args, **kwargs):
            frozen = kwargs.get("frozen_concepts")
            captured.append([item.get("concept_id") for item in (frozen or [])])
            return False

        with mock.patch.object(envsys, "_generate_level3_image_with_gemini", side_effect=capture_frozen):
            envsys.generate_room_environment_previews(self.project_id, "R1", {})
        self.assertEqual(len(captured), 3)
        self.assertEqual(captured[0], ["art-direction-02"])
        scene = self.saved["room_layout"]["rooms"][0]["environment"]["preview"]["scene_plan"]
        self.assertEqual(scene.get("preview_frozen_concept_ids"), ["art-direction-02"])
        self.assertIn("ruined-gothic", scene.get("preview_biome_id") or "")

    def test_room_environment_preview_falls_back_to_global_frozen_when_pack_has_no_locked_concepts(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        self.saved["art_direction"]["biome_packs"][0]["locked_concept_ids"] = []
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        captured = []

        def capture_frozen(*args, **kwargs):
            frozen = kwargs.get("frozen_concepts")
            captured.append([item.get("concept_id") for item in (frozen or [])])
            return False

        with mock.patch.object(envsys, "_generate_level3_image_with_gemini", side_effect=capture_frozen):
            envsys.generate_room_environment_previews(self.project_id, "R1", {})
        self.assertEqual(captured[0], ["art-direction-01"])
        scene = self.saved["room_layout"]["rooms"][0]["environment"]["preview"]["scene_plan"]
        self.assertEqual(scene.get("preview_frozen_concept_ids"), ["art-direction-01"])

    def test_foreground_frame_generation_guide_emphasizes_cap_and_floor_bands(self):
        project_dir = self.projects_root / self.project_id
        guide_path = envsys._write_foreground_frame_generation_guide(project_dir)
        guide = envsys.Image.open(guide_path).convert("RGB")

        top = guide.getpixel((guide.width // 2, 40))
        bottom = guide.getpixel((guide.width // 2, 1090))
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fy = envsys.ATLAS_HEIGHT - envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        left = guide.getpixel((120, (ft + fy) // 2))
        right = guide.getpixel((guide.width - 120, (ft + fy) // 2))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        center = guide.getpixel(((il + ir) // 2, (itop + ib) // 2))

        # Cap/floor bands must read lighter than side walls for Gemini, but stay well below paper-white (no edge halos).
        self.assertGreater(top[0], left[0] + 40)
        self.assertGreater(bottom[0], left[0] + 40)
        self.assertLess(max(top), 230)
        self.assertLess(max(bottom), 230)
        self.assertGreater(center[1], 220)
        self.assertLess(center[0], 40)
        self.assertLess(center[2], 40)
        self.assertGreater(center[1], left[1] + 140)
        self.assertGreater(center[1], right[1] + 140)

    def test_foreground_frame_generation_guide_is_not_fallback_seed_render(self):
        project_dir = self.projects_root / self.project_id
        guide_path = envsys._write_foreground_frame_generation_guide(project_dir)
        direction = {
            "template_id": "ruined-gothic",
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "style_family": "dark fantasy ruins",
            "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
            "palette": {
                "dominant": ["#11161d", "#24343a", "#6f7f79"],
                "accent": ["#b58f52"],
                "avoid": ["#ffffff", "#ff3bf1"],
            },
        }
        self.assertFalse(envsys._foreground_frame_matches_fallback_seed(guide_path, direction))

    def test_foreground_frame_style_swatch_avoids_hard_top_separator_bar(self):
        project_dir = self.projects_root / self.project_id
        direction = {
            "template_id": "ruined-gothic",
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "style_family": "dark fantasy ruins",
            "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
            "palette": {
                "dominant": ["#11161d", "#24343a", "#6f7f79"],
                "accent": ["#b58f52"],
                "avoid": ["#ffffff", "#ff3bf1"],
            },
        }
        swatch_path = envsys._write_foreground_frame_style_swatch(project_dir, direction)
        self.assertIsNotNone(swatch_path)
        swatch = envsys.Image.open(swatch_path).convert("RGB")
        ceiling_sample = swatch.getpixel((swatch.width // 2, 79))
        seam_sample = swatch.getpixel((swatch.width // 2, 88))
        wall_sample = swatch.getpixel((swatch.width // 2, 108))
        self.assertGreater(sum(seam_sample), 90)
        self.assertGreater(sum(seam_sample), sum(wall_sample) - 40)
        self.assertLess(abs(sum(ceiling_sample) - sum(seam_sample)), 80)

    def test_foreground_frame_style_swatch_uses_clean_fallback_ceiling_row(self):
        project_dir = self.projects_root / self.project_id
        biome_root = project_dir / "art_direction_biomes" / "ruined-gothic-v1"
        biome_root.mkdir(parents=True, exist_ok=True)
        ceiling_path = biome_root / "ceiling_piece.png"
        wall_path = biome_root / "wall_piece.png"
        bad_ceiling = envsys.Image.new("RGBA", (1600, 224), (28, 34, 40, 255))
        draw = envsys.ImageDraw.Draw(bad_ceiling)
        draw.rectangle((0, 0, 1600, 224), fill=(28, 34, 40, 255))
        draw.rectangle((520, 96, 760, 180), fill=(210, 210, 210, 255))
        bad_ceiling.save(ceiling_path)
        good_wall = envsys.Image.new("RGBA", (512, 1200), (34, 42, 50, 255))
        good_wall.save(wall_path)
        direction = {
            "template_id": "ruined-gothic",
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "style_family": "dark fantasy ruins",
            "lighting_rules": ["low-key lighting"],
            "palette": {
                "dominant": ["#11161d", "#24343a", "#6f7f79"],
                "accent": ["#b58f52"],
                "avoid": ["#ffffff", "#ff3bf1"],
            },
        }
        swatch_path = envsys._write_foreground_frame_style_swatch(project_dir, direction)
        self.assertIsNotNone(swatch_path)
        swatch = envsys.Image.open(swatch_path).convert("RGB")
        top_mid = swatch.getpixel((swatch.width // 2, 56))
        self.assertLess(sum(top_mid), 180)

    def test_foreground_frame_match_detector_requires_equal_dimensions(self):
        direction = {
            "template_id": "ruined-gothic",
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "style_family": "dark fantasy ruins",
            "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
            "palette": {
                "dominant": ["#11161d", "#24343a", "#6f7f79"],
                "accent": ["#b58f52"],
                "avoid": ["#ffffff", "#ff3bf1"],
            },
        }
        fallback = self.root / "foreground-frame-fallback.png"
        envsys._fallback_foreground_frame_asset(fallback, direction["palette"], {})
        resized = self.root / "foreground-frame-fallback-resized.png"
        envsys.Image.open(fallback).resize((1024, 1024), envsys.Image.Resampling.LANCZOS).save(resized)
        self.assertFalse(envsys._foreground_frame_matches_fallback_seed(resized, direction))

    def test_fit_foreground_frame_image_to_size_trims_edge_padding_before_resize(self):
        raw = self.root / "foreground-frame-raw.png"
        img = envsys.Image.new("RGBA", (1184, 864), (248, 248, 248, 255))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((0, 120, 1184, 720), fill=(26, 30, 36, 255))
        draw.rectangle((0, 120, 152, 720), fill=(14, 16, 20, 255))
        draw.rectangle((1032, 120, 1184, 720), fill=(14, 16, 20, 255))
        draw.rectangle((152, 120, 1032, 720), fill=(84, 84, 84, 255))
        img.save(raw)

        envsys._fit_foreground_frame_image_to_size(raw, (1600, 1200))
        fitted = envsys.Image.open(raw).convert("RGB")

        top = fitted.getpixel((fitted.width // 2, 24))
        left = fitted.getpixel((60, fitted.height // 2))
        center = fitted.getpixel((fitted.width // 2, fitted.height // 2))
        self.assertLess(sum(top), 720)
        self.assertLess(sum(left), sum(center))

    def test_fallback_foreground_frame_seed_stays_border_only(self):
        path = self.root / "foreground-frame-seed.png"
        envsys._fallback_foreground_frame_asset(
            path,
            {"dominant": ["#11161d", "#24343a"]},
            {},
        )
        img = envsys.Image.open(path).convert("RGB")
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        center = img.getpixel(((il + ir) // 2, (itop + ib) // 2))
        top = img.getpixel((img.width // 2, 80))
        bottom = img.getpixel((img.width // 2, 1120))
        left = img.getpixel((120, (itop + ib) // 2))
        center_edge = img.getpixel((il - 1, (itop + ib) // 2))
        self.assertGreater(center[1], 220)
        self.assertLess(center[0], 40)
        self.assertLess(center[2], 40)
        self.assertLess(sum(left), sum(center))
        self.assertNotEqual(top, center)
        self.assertNotEqual(bottom, center)
        self.assertNotEqual(left, center_edge)

    def test_generate_biome_pack_visuals_generates_floor_before_other_structural_parts(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        call_order = []

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            call_order.append(output_path.name)
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["ceiling_piece", "primary_floor_piece", "wall_piece"]},
            )

        self.assertTrue(out["ok"])
        self.assertTrue(call_order[0].startswith("primary_floor_piece"))

    def test_generate_biome_pack_visuals_keeps_core_structural_templates_seed_only(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        calls = {}

        def fake_generate(output_path, prompt, refs, size, transparent, component_type=None):
            key = str(component_type or output_path.name.replace("-candidate", ""))
            calls[key] = {
                "prompt": prompt,
                "refs": [path.name for path in refs],
            }
            return self._fake_ai_generate(output_path, prompt, refs, size, transparent)

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate), \
             mock.patch.object(envsys, "_validate_structural_biome_source", return_value=(True, [])):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["primary_floor_piece", "wall_piece", "ceiling_piece"]},
            )

        self.assertTrue(out["ok"])
        self.assertIn("wall_piece-seed.png", calls["wall_piece"]["refs"])
        self.assertIn("ceiling_piece-seed.png", calls["ceiling_piece"]["refs"])
        self.assertIn("primary_floor_piece-seed.png", calls["primary_floor_piece"]["refs"])
        self.assertNotIn("primary_floor_piece.png", calls["wall_piece"]["refs"])
        self.assertNotIn("primary_floor_piece.png", calls["ceiling_piece"]["refs"])
        self.assertNotIn("foreground_frame.png", calls["wall_piece"]["refs"])
        self.assertNotIn("foreground_frame.png", calls["ceiling_piece"]["refs"])
        self.assertNotIn("direct material and proportion anchors", calls["wall_piece"]["prompt"])

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
        self.assertTrue(bespoke["structural_review_bundle"]["sources"])
        self.assertTrue(bespoke["structural_review_bundle"]["contact_sheet"]["url"])
        self.assertEqual(bespoke["border_first_contract"]["contract_version"], envsys.BORDER_FIRST_CONTRACT_VERSION)
        self.assertEqual(bespoke["border_first_contract"]["status"], "schema_only")
        self.assertEqual(bespoke["border_first_contract"]["canonical_shell_template"], "border_piece")
        self.assertEqual(bespoke["border_first_contract"]["compositing"]["center_handling"], "mask_based_extraction")
        self.assertEqual(
            bespoke["border_first_contract"]["room_assets"],
            {
                "room_border_shell": "planned",
                "room_background": "planned",
                "room_platforms": "planned",
                "room_doors": "planned",
            },
        )
        self.assertEqual(bespoke["runtime_review"]["status"], "pass")
        self.assertTrue(bespoke["runtime_review"]["screenshot_url"])
        self.assertEqual(asset_pack["environment"]["runtime"]["status"], "ready")
        self.assertTrue(bespoke["used_ai"])
        helpfulness = asset_pack["environment"]["ai_helpfulness"]
        self.assertEqual(helpfulness["summary"]["funnel"]["requested"], 1)
        self.assertEqual(helpfulness["summary"]["funnel"]["accepted"], 1)
        suggestion = helpfulness["suggestions"][0]
        self.assertTrue(suggestion["suggestion_id"])
        self.assertEqual(suggestion["decision"]["outcome"], "accept")
        self.assertEqual(suggestion["context"]["room_complexity_bucket"], "light")
        self.assertEqual(suggestion["previews"]["render_level"], "level3")

    def test_build_spec_supports_v3_environment_contract(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        spec = envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A quiet stone threshold with a readable route, dark shell, and restrained atmosphere.",
            },
        )
        env = spec["environment"]
        self.assertEqual(env["environment_pipeline_version"], "v3")
        self.assertIn("room_intent", env)
        self.assertIn("component_contracts", env)
        self.assertIn("assembly_plan", env)
        self.assertIn("review_state", env)
        self.assertIn("ceiling", env["spec"]["component_schemas"])
        self.assertIn("backwall_panel", env["spec"]["component_schemas"])
        self.assertEqual(env["room_intent"]["room_role"], "threshold")
        self.assertIn("ceiling", env["component_contracts"])
        self.assertIn("backwall_panel", env["component_contracts"])
        self.assertIn("runtime_review_pending", env["review_state"]["validation_status"]["issues"])
        self.assertIn("reference_pack", env)
        self.assertIn("stylepack", env)
        self.assertIn("room_semantics", env)
        self.assertIn("environment_kit", env)
        self.assertIn("environment_manifest", env)
        self.assertIn("validation_report", env)
        self.assertIn("editor_results_payload", env)
        self.assertIn("staged_artifacts", env)
        self.assertEqual(env["editor_results_payload"]["semantics"]["counts"]["top_count"], 1)
        self.assertEqual(env["environment_kit"]["source"]["semantic_source"]["room_role"], env["room_semantics"]["room_role"])
        self.assertEqual(
            env["environment_kit"]["summary"]["structural_count"],
            env["environment_manifest"]["generation_metadata"]["structural_count"],
        )
        self.assertEqual(
            env["environment_kit"]["summary"]["background_count"],
            env["environment_manifest"]["generation_metadata"]["background_count"],
        )
        self.assertEqual(env["environment_kit"]["summary"]["component_count_by_type"], env["environment_kit"]["component_count_by_type"])
        self.assertEqual(env["editor_results_payload"]["kit"]["component_count_by_type"], env["environment_kit"]["component_count_by_type"])
        self.assertIn("taxonomy", env["editor_results_payload"]["kit"])
        self.assertEqual(env["environment_manifest"]["layer_order"], ["structural", "background", "decor"])
        self.assertEqual(env["environment_manifest"]["generation_metadata"]["pass_order"], ["structural", "background", "decor"])
        self.assertTrue(env["environment_manifest"]["deterministic_replay"]["replay_key"])
        self.assertEqual(
            env["environment_manifest"]["placement_summary"]["total_count"],
            env["environment_manifest"]["generation_metadata"]["placement_count"],
        )
        self.assertEqual(env["editor_results_payload"]["manifest"]["layer_order"], ["structural", "background", "decor"])
        self.assertIn("blocker_count", env["validation_report"])
        self.assertIn("validation_highlights", env["validation_report"])
        self.assertIsInstance(env["validation_report"]["findings"]["warnings"], list)
        self.assertEqual(env["editor_results_payload"]["validation"]["status"], "ready")
        self.assertIn("findings", env["editor_results_payload"]["validation"])
        self.assertEqual(env["environment_kit"]["summary"]["component_count"], 0)
        self.assertEqual(env["environment_kit"]["source"]["semantic_source"]["room_role"], env["room_intent"]["room_role"])
        self.assertEqual(env["staged_artifacts"]["stylepack"]["status"], "ready")

    def test_v3_build_persists_derived_artifacts_to_disk(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A quiet stone threshold with readable shell definition and restrained background depth.",
            },
        )
        artifact_root = self.projects_root / self.project_id / "room_environment_assets" / "R1" / envv3_persistence.DERIVED_SUBDIR
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_REFERENCE_PACK).exists())
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_STYLEPACK).exists())
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_ROOM_SEMANTICS).exists())
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_ENVIRONMENT_KIT).exists())
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_ENVIRONMENT_MANIFEST).exists())
        self.assertTrue((artifact_root / envv3_persistence.ARTIFACT_VALIDATION_REPORT).exists())

    def test_v3_reopen_hydrates_persisted_artifacts_when_env_state_is_missing(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A quiet stone threshold with readable shell definition and restrained background depth.",
            },
        )
        manifest_path = envv3_persistence.artifact_path(
            self.projects_root,
            self.project_id,
            "R1",
            "environment_manifest",
        )
        manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_doc["persistence_probe"] = "disk-backed-manifest"
        manifest_path.write_text(json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8")

        room_env = self.saved["room_layout"]["rooms"][0]["environment"]
        for key in [
            "reference_pack",
            "stylepack",
            "room_semantics",
            "environment_kit",
            "environment_manifest",
            "validation_report",
            "editor_results_payload",
            "staged_artifacts",
        ]:
            room_env.pop(key, None)

        reopened_room = envsys._find_room(self.saved, "R1")
        reopened_env = reopened_room["environment"]
        self.assertEqual(reopened_env["environment_manifest"]["persistence_probe"], "disk-backed-manifest")
        self.assertEqual(reopened_env["staged_artifacts"]["environment_manifest"]["status"], "ready")
        self.assertEqual(
            reopened_env["staged_artifacts"]["environment_manifest"]["relative_path"],
            f"derived/v3/{envv3_persistence.ARTIFACT_ENVIRONMENT_MANIFEST}",
        )
        self.assertEqual(
            reopened_env["editor_results_payload"]["manifest"]["generation_metadata"],
            reopened_env["environment_manifest"]["generation_metadata"],
        )

    def test_v3_reopen_hydrates_multiple_persisted_artifacts_into_results_payload(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A quiet stone threshold with readable shell definition and restrained background depth.",
            },
        )
        stylepack_path = envv3_persistence.artifact_path(
            self.projects_root,
            self.project_id,
            "R1",
            "stylepack",
        )
        stylepack_doc = json.loads(stylepack_path.read_text(encoding="utf-8"))
        stylepack_doc["summary"] = "disk-backed-stylepack"
        stylepack_path.write_text(json.dumps(stylepack_doc, indent=2) + "\n", encoding="utf-8")

        validation_path = envv3_persistence.artifact_path(
            self.projects_root,
            self.project_id,
            "R1",
            "validation_report",
        )
        validation_doc = json.loads(validation_path.read_text(encoding="utf-8"))
        validation_doc["info_count"] = 42
        validation_doc["findings"]["info"].append(
            {
                "severity": "info",
                "code": "disk_backed_probe",
                "message": "Loaded from persisted validation report.",
            }
        )
        validation_path.write_text(json.dumps(validation_doc, indent=2) + "\n", encoding="utf-8")

        room_env = self.saved["room_layout"]["rooms"][0]["environment"]
        for key in [
            "reference_pack",
            "stylepack",
            "room_semantics",
            "environment_kit",
            "environment_manifest",
            "validation_report",
            "editor_results_payload",
            "staged_artifacts",
        ]:
            room_env.pop(key, None)

        reopened_room = envsys._find_room(self.saved, "R1")
        reopened_env = reopened_room["environment"]
        self.assertEqual(reopened_env["stylepack"]["summary"], "disk-backed-stylepack")
        self.assertEqual(reopened_env["validation_report"]["info_count"], 42)
        self.assertTrue(
            any(
                item.get("code") == "disk_backed_probe"
                for item in reopened_env["editor_results_payload"]["validation"]["info"]
            )
        )
        self.assertEqual(
            reopened_env["editor_results_payload"]["validation"]["info_count"],
            reopened_env["validation_report"]["info_count"],
        )

    def test_v2_rooms_do_not_silently_upgrade_or_hydrate_v3_artifacts_on_reopen(self):
        room = self.saved["room_layout"]["rooms"][0]
        room["environment"] = {
            "environment_pipeline_version": "v2",
            "spec": {
                "description": "Legacy environment payload",
                "components": {},
                "component_schemas": {},
                "scene_schema": {},
            },
            "preview": {"status": "idle", "images": []},
            "runtime": {"status": "idle", "bespoke_asset_manifest": {"status": "idle"}},
        }
        envv3_persistence.save_artifact(
            self.projects_root,
            self.project_id,
            "R1",
            "stylepack",
            {"stylepack_id": "stylepack-r1", "summary": "should-not-hydrate"},
        )

        reopened_room = envsys._find_room(self.saved, "R1")
        reopened_env = reopened_room["environment"]
        self.assertEqual(reopened_env["environment_pipeline_version"], "v2")
        self.assertNotIn("stylepack", reopened_env)
        self.assertNotIn("staged_artifacts", reopened_env)
        self.assertNotIn("editor_results_payload", reopened_env)

    def test_v3_runtime_review_controls_approval_state(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "overgrown-shrine", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A shrine threshold with a readable floor, clear door framing, and quiet background depth.",
            },
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            asset_pack = envsys.generate_room_environment_asset_pack(
                self.project_id,
                "R1",
                {"preview_id": preview_id},
            )
        review_state = asset_pack["environment"]["review_state"]
        self.assertEqual(review_state["runtime_review"]["status"], "pass")
        self.assertEqual(review_state["validation_status"]["status"], "complete")
        self.assertEqual(review_state["approval_status"], "approved")

    def test_v3_preview_generation_populates_planner_backed_results_surface(self):
        room = self.saved["room_layout"]["rooms"][0]
        room["doors"] = [
            {"id": "R1-D1", "x": 160, "y": 960, "kind": "transition"},
            {"id": "R1-D2", "x": 1440, "y": 960, "kind": "transition"},
        ]
        room["platforms"] = [
            {"id": "R1-P1", "x": 192, "y": 960, "len": 28},
            {"id": "R1-P2", "x": 544, "y": 704, "len": 8},
        ]
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A ruined hall with readable thresholds, layered shell depth, and clear traversal surfaces.",
            },
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        env = generated["environment"]
        self.assertGreater(len(env["assembly_plan"]["slots"]), 0)
        self.assertEqual(env["assembly_plan"]["planner_coverage_summary"]["status"], "pass")
        self.assertGreater(env["environment_manifest"]["generation_metadata"]["structural_count"], 0)
        self.assertGreater(env["environment_kit"]["summary"]["structural_count"], 0)
        self.assertEqual(env["editor_results_payload"]["manifest"]["generation_metadata"]["structural_count"], env["environment_manifest"]["generation_metadata"]["structural_count"])
        self.assertGreaterEqual(env["editor_results_payload"]["validation"]["blocker_count"], 1)

    def test_v3_planner_covers_all_doors_and_major_platforms(self):
        room = self.saved["room_layout"]["rooms"][0]
        room["doors"] = [
            {"id": "R1-D1", "x": 160, "y": 960, "kind": "transition"},
            {"id": "R1-D2", "x": 1440, "y": 960, "kind": "transition"},
            {"id": "R1-D3", "x": 800, "y": 192, "kind": "transition"},
        ]
        room["platforms"] = [
            {"id": "R1-P1", "x": 160, "y": 960, "len": 36},
            {"id": "R1-P2", "x": 288, "y": 736, "len": 10},
            {"id": "R1-P3", "x": 832, "y": 608, "len": 9},
            {"id": "R1-P4", "x": 448, "y": 416, "len": 8},
        ]
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {
                "environment_pipeline_version": "v3",
                "description": "A vertical traversal room with multiple thresholds, readable shell framing, and strong route clarity.",
            },
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})
        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            result = envsys.generate_room_environment_asset_pack(
                self.project_id,
                "R1",
                {"preview_id": preview_id},
            )
        assembly_plan = result["environment"]["assembly_plan"]
        slots = assembly_plan["slots"]
        door_slots = [slot for slot in slots if slot["schema_key"] == "doors"]
        traversal_top_slots = [
            slot for slot in slots
            if slot["component_type"] in {"main_floor_top", "hero_platform_top"}
        ]
        self.assertEqual(len(door_slots), 3)
        self.assertEqual(len(traversal_top_slots), 4)
        self.assertTrue(any(slot["schema_key"] == "ceiling" for slot in slots))
        self.assertTrue(any(slot["schema_key"] == "backwall_panel" for slot in slots))
        self.assertEqual(assembly_plan["planner_coverage_summary"]["status"], "pass")
        self.assertEqual(
            assembly_plan["planner_coverage_summary"]["major_structures"]["planned_door_slots"],
            3,
        )
        self.assertEqual(
            assembly_plan["planner_coverage_summary"]["major_structures"]["planned_platform_slots"],
            4,
        )

    def test_v3_planner_marks_top_threshold_doors_with_top_placement(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["size"] = {"width": 1184, "height": 1888}
        room["doors"] = [
            {"id": "R1-D1", "x": 592, "y": 128, "kind": "transition"},
            {"id": "R1-D2", "x": 224, "y": 1664, "kind": "transition"},
        ]
        planner = envsys.envv3.build_generation_plan(
            room,
            "preview-1",
            self._mock_biome_pack(),
            "2026-03-28T12:00:00Z",
        )
        top_door = next(item for item in planner["plan"] if item["slot_id"] == "R1-door-1")
        bottom_door = next(item for item in planner["plan"] if item["slot_id"] == "R1-door-2")
        self.assertEqual(top_door["orientation"], "horizontal")
        self.assertEqual(top_door["placement"]["origin_y"], 0)
        self.assertEqual(bottom_door["orientation"], "vertical")
        self.assertEqual(bottom_door["placement"]["origin_y"], 1)

    def test_v3_semantics_derives_overlay_counts_from_room_geometry(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["platforms"].append({"id": "R1-P2", "x": 640, "y": 704, "len": 8})
        room["doors"].append({"id": "R1-D2", "x": 1440, "y": 960, "kind": "transition"})
        semantics_doc = envv3.semantics.derive_room_semantics(room)
        self.assertEqual(semantics_doc["summary"]["top_count"], 2)
        self.assertEqual(semantics_doc["summary"]["opening_count"], 2)
        self.assertEqual(len(semantics_doc["overlay_geometry"]["platform_tops"]), 2)
        self.assertGreaterEqual(len(semantics_doc["anchor_positions"]), 4)
        anchor_types = {item["anchor_type"] for item in semantics_doc["anchor_positions"]}
        self.assertIn("platform_center", anchor_types)
        self.assertTrue(any(anchor_type.endswith("threshold") for anchor_type in anchor_types))

    def test_v3_persistence_helpers_round_trip_staged_artifacts(self):
        payload = {"stylepack_id": "stylepack-r1", "status": "locked"}
        path = envv3.persistence.save_artifact(
            self.projects_root,
            self.project_id,
            "R1",
            "stylepack",
            payload,
        )
        self.assertTrue(path.exists())
        self.assertEqual(
            path,
            self.projects_root / self.project_id / "room_environment_assets" / "R1" / "derived" / "v3" / "stylepack.json",
        )
        loaded = envv3.persistence.load_artifact(
            self.projects_root,
            self.project_id,
            "R1",
            "stylepack",
        )
        self.assertEqual(loaded, payload)

    def test_v3_planner_splits_backwall_panels_for_wide_ruined_halls(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["size"] = {"width": 2112, "height": 1248}
        room["doors"] = [
            {"id": "R1-D1", "x": 128, "y": 1024, "kind": "transition"},
            {"id": "R1-D2", "x": 1984, "y": 1024, "kind": "transition"},
        ]
        planner = envsys.envv3.build_generation_plan(
            room,
            "preview-2",
            self._mock_biome_pack(),
            "2026-03-28T12:00:00Z",
        )
        panels = [item for item in planner["plan"] if item["component_type"] == "backwall_panel"]
        self.assertGreaterEqual(len(panels), 2)

    def test_v3_planner_omits_backwall_panel_when_env_disabled(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["size"] = {"width": 1600, "height": 1200}
        with mock.patch.dict(os.environ, {"MV_V3_BACKWALL_PANEL": "0"}, clear=False):
            planner = envv3.build_generation_plan(
                room,
                "preview-no-backwall",
                self._mock_biome_pack(),
                "2026-04-06T12:00:00Z",
            )
        panels = [item for item in planner["plan"] if item["component_type"] == "backwall_panel"]
        self.assertEqual(len(panels), 0)

    def test_v3_planner_unified_shell_env_replaces_ceiling_walls_and_main_floor(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["size"] = {"width": 1600, "height": 1200}
        with mock.patch.dict(os.environ, {"MV_ROOM_SHELL_FOREGROUND": "1"}, clear=False):
            planner = envv3.build_generation_plan(
                room,
                "preview-shell",
                self._mock_biome_pack(),
                "2026-04-07T12:00:00Z",
            )
        types = [item["component_type"] for item in planner["plan"]]
        self.assertIn("room_shell_foreground", types)
        self.assertNotIn("ceiling_band", types)
        self.assertNotIn("wall_module_left", types)
        self.assertNotIn("main_floor_top", types)
        shell = next(item for item in planner["plan"] if item["component_type"] == "room_shell_foreground")
        self.assertEqual(shell["source_template_component_type"], "foreground_frame")
        self.assertEqual(shell["transparency_mode"], "alpha")
        td = shell["target_dimensions"]
        self.assertEqual(td["width"], 1280)
        self.assertEqual(td["height"], 880)

    def test_apply_walkable_interior_punchout_clears_polygon_interior(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        w, h = 400, 320
        path = self.root / "shell-punch.png"
        img = envsys.Image.new("RGBA", (w, h), (80, 90, 100, 255))
        img.save(path)
        envsys._apply_walkable_interior_punchout(path, geom)
        out = envsys.Image.open(path).convert("RGBA")
        px = out.load()
        # Center of chamber (polygon interior) should be punched transparent
        cx, cy = w // 2, h // 2
        self.assertLess(px[cx, cy][3], 16)

    def test_inset_polygon_vertices_toward_centroid_moves_corners_inward(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        out = envsys._inset_polygon_vertices_toward_centroid(pts, 10.0)
        self.assertEqual(len(out), 4)
        self.assertGreater(out[0][0], pts[0][0])
        self.assertGreater(out[0][1], pts[0][1])
        self.assertLess(out[1][0], pts[1][0])

    def test_room_shell_punch_inset_px_reads_env(self):
        with mock.patch.dict(os.environ, {"MV_ROOM_SHELL_PUNCH_INSET_PX": "12"}, clear=False):
            self.assertEqual(envsys._room_shell_punch_inset_px(), 12)
        with mock.patch.dict(os.environ, {"MV_ROOM_SHELL_PUNCH_INSET_PX": "99"}, clear=False):
            self.assertEqual(envsys._room_shell_punch_inset_px(), 48)

    def test_opaque_pixel_fraction_counts_visible_mass(self):
        path = self.root / "opaque-frac.png"
        envsys.Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(path)
        self.assertLess(envsys._opaque_pixel_fraction(path), 0.018)
        img = envsys.Image.open(path).convert("RGBA")
        px = img.load()
        for x in range(100):
            for y in range(20):
                px[x, y] = (100, 110, 120, 255)
        img.save(path)
        self.assertGreaterEqual(envsys._opaque_pixel_fraction(path), 0.018)

    def test_validate_room_shell_after_punchout_rejects_hairline_mass(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        path = self.root / "shell-hairline-mass.png"
        envsys.Image.new("RGBA", (400, 320), (0, 0, 0, 0)).save(path)
        ok, errors = envsys._validate_room_shell_after_punchout(path, geom, (400, 320))
        self.assertFalse(ok)
        self.assertIn("shell_rim_mass_low", errors)

    def test_validate_room_shell_after_punchout_rejects_near_black_shell_tone(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        path = self.root / "shell-too-dark.png"
        img = envsys.Image.new("RGBA", (400, 320), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((0, 0, 399, 70), fill=(8, 8, 8, 255))
        draw.rectangle((0, 250, 399, 319), fill=(8, 8, 8, 255))
        draw.rectangle((0, 70, 70, 250), fill=(8, 8, 8, 255))
        draw.rectangle((329, 70, 399, 250), fill=(8, 8, 8, 255))
        img.save(path)
        ok, errors = envsys._validate_room_shell_after_punchout(path, geom, (400, 320))
        self.assertFalse(ok)
        self.assertIn("shell_tone_too_dark", errors)

    def test_validate_room_shell_before_punchout_tolerates_dark_top_band(self):
        path = self.root / "shell-pre-top-gap.png"
        img = envsys.Image.new("RGBA", (400, 320), (30, 38, 48, 255))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((0, 0, 399, 70), fill=(62, 70, 82, 255))
        draw.rectangle((0, 250, 399, 319), fill=(62, 70, 82, 255))
        draw.rectangle((0, 70, 70, 250), fill=(58, 66, 78, 255))
        draw.rectangle((329, 70, 399, 250), fill=(58, 66, 78, 255))
        # Dark top ledge should not hard-fail pre-validation; post checks are authoritative.
        draw.rectangle((16, 0, 384, 112), fill=(0, 0, 0, 255))
        img.save(path)
        ok, errors = envsys._validate_room_shell_before_punchout(path, (400, 320))
        self.assertTrue(ok)
        self.assertNotIn("shell_top_edge_gap_pre", errors)

    def test_validate_room_shell_after_punchout_rejects_corner_gap(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        path = self.root / "shell-post-corner-gap.png"
        img = envsys.Image.new("RGBA", (400, 320), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((0, 0, 399, 70), fill=(62, 70, 82, 255))
        draw.rectangle((0, 250, 399, 319), fill=(62, 70, 82, 255))
        draw.rectangle((0, 70, 70, 250), fill=(58, 66, 78, 255))
        draw.rectangle((329, 70, 399, 250), fill=(58, 66, 78, 255))
        # Punch out a hard corner void.
        draw.rectangle((0, 0, 96, 100), fill=(0, 0, 0, 0))
        img.save(path)
        ok, errors = envsys._validate_room_shell_after_punchout(path, geom, (400, 320))
        self.assertFalse(ok)
        self.assertIn("shell_corner_gap_post", errors)

    def test_room_shell_silhouette_band_mask_creates_border_zone(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        mask = envsys._room_shell_silhouette_band_mask(geom, (400, 320), pad=24)
        self.assertEqual(mask.size, (400, 320))
        px = mask.load()
        self.assertGreater(px[10, 10], 0)
        self.assertEqual(px[200, 180], 0)

    def test_validate_room_shell_after_punchout_rejects_silhouette_overreach(self):
        geom = envsys._room_geometry(copy.deepcopy(self.saved["room_layout"]["rooms"][0]))
        path = self.root / "shell-post-overreach.png"
        img = envsys.Image.new("RGBA", (400, 320), (80, 90, 102, 255))
        img.save(path)
        ok, errors = envsys._validate_room_shell_after_punchout(path, geom, (400, 320))
        self.assertFalse(ok)
        self.assertIn("shell_silhouette_overreach", errors)

    def test_v3_planner_uses_component_specific_structural_slots(self):
        room = copy.deepcopy(self.saved["room_layout"]["rooms"][0])
        room["size"] = {"width": 1184, "height": 1888}
        room["platforms"].append({"id": "R1-P2", "x": 352, "y": 1088, "len": 7})
        planner = envsys.envv3.build_generation_plan(
            room,
            "preview-3",
            self._mock_biome_pack(),
            "2026-03-28T12:00:00Z",
        )
        ceiling = next(item for item in planner["plan"] if item["component_type"] == "ceiling_band")
        left_wall = next(item for item in planner["plan"] if item["component_type"] == "wall_module_left")
        left_trim = next(item for item in planner["plan"] if item["component_type"] == "wall_base_trim_left")
        floor_top = next(item for item in planner["plan"] if item["component_type"] == "main_floor_top")
        platform_top = next(item for item in planner["plan"] if item["component_type"] == "hero_platform_top")
        self.assertEqual(ceiling["source_template_component_type"], "ceiling_piece")
        self.assertEqual(left_wall["source_template_component_type"], "wall_piece")
        self.assertEqual(left_trim["source_template_component_type"], "wall_piece")
        self.assertEqual(floor_top["source_template_component_type"], "primary_floor_piece")
        self.assertEqual(platform_top["source_template_component_type"], "hero_platform_piece")

    def test_room_helpfulness_feedback_tracks_view_revise_and_persistence(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with a calm center and strong traversal edges."},
        )
        first = envsys.generate_room_environment_previews(
            self.project_id,
            "R1",
            {"session_id": "sess-1", "task_id": "task-1", "workflow_step": "results"},
        )
        suggestion_id = first["environment"]["preview"]["suggestion_id"]
        envsys.record_room_environment_feedback_event(
            self.project_id,
            "R1",
            {"event_type": "preview_viewed", "suggestion_id": suggestion_id},
        )
        envsys.revise_room_environment(
            self.project_id,
            "R1",
            {"instruction": "Make the center route easier to read.", "reason_codes": ["confusing_layout"]},
        )
        second = envsys.generate_room_environment_previews(
            self.project_id,
            "R1",
            {"session_id": "sess-1", "task_id": "task-1", "workflow_step": "results", "request_kind": "revise"},
        )
        second_id = second["environment"]["preview"]["suggestion_id"]
        first_record = second["environment"]["ai_helpfulness"]["suggestions"][0]
        self.assertEqual(first_record["decision"]["outcome"], "tweak")
        self.assertEqual(first_record["effort"]["preview_views"], 1)
        approved = envsys.approve_room_environment_preview(
            self.project_id,
            "R1",
            {"preview_id": second["environment"]["preview"]["images"][0]["preview_id"], "reason_codes": ["style_mismatch"]},
        )
        room = self.saved["room_layout"]["rooms"][0]
        room["platforms"].append({"id": "R1-P2", "x": 640, "y": 768, "len": 6})
        envsys.refresh_room_environment_helpfulness_on_layout_save(room)
        second_record = next(item for item in approved["environment"]["ai_helpfulness"]["suggestions"] if item["suggestion_id"] == second_id)
        refreshed = room["environment"]["ai_helpfulness"]
        refreshed_second = next(item for item in refreshed["suggestions"] if item["suggestion_id"] == second_id)
        self.assertEqual(second_record["decision"]["outcome"], "accept")
        self.assertEqual(refreshed["summary"]["funnel"]["requested"], 2)
        self.assertEqual(refreshed["summary"]["funnel"]["tweaked"], 1)
        self.assertEqual(refreshed["summary"]["funnel"]["accepted"], 1)
        self.assertEqual(refreshed_second["persistence"]["status"], "persisted")
        self.assertEqual(refreshed_second["tweak_magnitude"]["bucket"], "small")

    def _mock_biome_pack(self):
        template_library = []
        for component_type, template_id in [
            ("background_plate", "tmpl-bg"),
            ("midground_frame", "tmpl-mid"),
            ("foreground_frame", "tmpl-foreground"),
            ("wall_piece", "tmpl-wall"),
            ("ceiling_piece", "tmpl-ceiling"),
            ("primary_floor_piece", "tmpl-floor"),
            ("hero_platform_piece", "tmpl-platform"),
            ("door_piece", "tmpl-door"),
        ]:
            template_library.append({
                "component_type": component_type,
                "template_id": template_id,
            })
        return {"template_library": template_library}

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

    def test_generate_assets_iterate_requires_slot_id(self):
        with self.assertRaisesRegex(ValueError, "iterate_from_current requires slot_id"):
            envsys.generate_room_environment_asset_pack(
                self.project_id,
                "R1",
                {"preview_id": "any-preview", "iterate_from_current": True},
            )

    def test_generate_assets_unknown_slot_id_raises(self):
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
            envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})
        with self.assertRaisesRegex(ValueError, "Unknown slot_id"):
            envsys.generate_room_environment_asset_pack(
                self.project_id,
                "R1",
                {"preview_id": preview_id, "slot_id": "definitely-not-a-real-slot-id"},
            )

    def test_prefix_iteration_reference_refs_prepends_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path_a = root / "a.png"
            path_b = root / "b.png"
            path_a.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
            path_b.write_bytes(path_a.read_bytes())
            out = envsys._prefix_iteration_reference_refs([path_b, path_a], path_a)
            self.assertEqual(out[0], path_a)
            self.assertEqual(len(out), 2)
            self.assertIn(path_b, out)

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

        def fake_template_render(template_path, output_path, size, transparent, component_type):
            img = envsys.Image.new("RGBA", size, (40, 50, 60, 0 if transparent else 255))
            img.save(output_path)
            return True

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=self._fake_ai_generate), \
             mock.patch.object(envsys, "_render_bespoke_component_from_template", side_effect=fake_template_render), \
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

        original_render = envsys._render_bespoke_component_from_template

        def fail_background(template_path, output_path, size, transparent, component_type=None):
            if component_type == "background_far_plate":
                return False
            return original_render(template_path, output_path, size, transparent, component_type)

        with mock.patch.object(envsys, "_render_bespoke_component_from_template", side_effect=fail_background):
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
        self.assertIn("visible enclosing wall faces in the outer thirds", prompt)
        self.assertIn("tighter dungeon passage shell", prompt)
        self.assertIn("Avoid a broad bright fog bank across the lower half", prompt)
        self.assertIn("continuous side-wall enclosure", prompt)

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
        self.assertIn("upper edge of a chamber border", floor_prompt)

        wall_prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Quiet ruined hall", "negative_direction": "busy focal shrine scenes"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A hall with a clear route.",
                "component_schemas": {"walls": envsys._default_component_schema("walls", "A hall with a clear route.")},
            },
            {
                "component_type": "wall_module_left",
                "schema_key": "walls",
                "target_dimensions": {"width": 320, "height": 960},
                "orientation": "vertical",
                "tile_mode": "stretch",
                "border_treatment": "side_only",
                "protected_zones": [{"type": "center_lane", "x": 480, "y": 0, "width": 640, "height": 1200}],
            },
            {"variant_family": "walls", "orientation": "vertical"},
        )
        self.assertIn("solid opaque enclosure stone", wall_prompt)
        self.assertIn("one broad wall face", wall_prompt)
        self.assertIn("No arch cutout", wall_prompt)
        self.assertIn("no visible opening", wall_prompt)

        floor_face_prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Quiet ruined hall", "negative_direction": "busy focal shrine scenes"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A hall with a clear route.",
                "component_schemas": {"floor": envsys._default_component_schema("floor", "A hall with a clear route.")},
            },
            {
                "component_type": "main_floor_face",
                "schema_key": "floor",
                "target_dimensions": {"width": 704, "height": 128},
                "orientation": "horizontal",
                "tile_mode": "tile_x",
                "border_treatment": "face_plane_separation",
                "protected_zones": [{"type": "platform_face", "x": 224, "y": 960, "width": 704, "height": 96}],
            },
            {"variant_family": "floor", "orientation": "horizontal"},
        )
        self.assertIn("heavy retaining border wall", floor_face_prompt)
        self.assertIn("broad darker masonry blocks", floor_face_prompt)
        self.assertIn("visibly lighter than the face beneath it", floor_prompt)

    def test_bespoke_prompt_requires_transparent_cutout_for_door_frame(self):
        prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Ruined gothic threshold", "negative_direction": "busy scenic chambers"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A doorway set into a ruined hall.",
                "component_schemas": {"doors": envsys._default_component_schema("doors", "A doorway set into a ruined hall.")},
            },
            {
                "component_type": "door_frame",
                "schema_key": "doors",
                "target_dimensions": {"width": 192, "height": 288},
                "orientation": "vertical",
                "tile_mode": "stretch",
                "border_treatment": "threshold_clearance",
                "protected_zones": [{"type": "door_mouth", "x": 64, "y": 48, "width": 64, "height": 160}],
            },
            {"variant_family": "door", "orientation": "vertical"},
        )
        self.assertIn("isolated doorway component", prompt)
        self.assertIn("transparent pixels outside the frame", prompt)
        self.assertIn("through the doorway opening", prompt)

    def test_bespoke_prompt_ceiling_band_rejects_composite_arcade_read(self):
        prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Ruined gothic vault", "negative_direction": "busy scenic chambers"},
            {
                "mood": "somber",
                "lighting": "low-key",
                "description": "A narrow stone passage under a heavy cap.",
                "component_schemas": {"ceiling": envsys._default_component_schema("ceiling", "A narrow stone passage under a heavy cap.")},
            },
            {
                "component_type": "ceiling_band",
                "schema_key": "ceiling",
                "target_dimensions": {"width": 1600, "height": 224},
                "orientation": "horizontal",
                "tile_mode": "stretch",
                "border_treatment": "full_frame",
                "protected_zones": [],
            },
            {"variant_family": "ceiling", "orientation": "horizontal"},
        )
        self.assertIn("one horizontal opaque stone band", prompt)
        self.assertIn("not a collage of separate pieces", prompt)
        self.assertIn("no row of separate arched windows", prompt)
        self.assertIn("ceiling_fields:", prompt)
        self.assertIn("ceiling_span_profile=", prompt)
        self.assertIn("multi-arch arcade", prompt.lower())

    def test_biome_template_prompt_strengthens_background_and_door_contracts(self):
        direction = {
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "negative_direction": "clean sci-fi surfaces, cartoon props, glossy plastics, bright cheerful saturation",
            "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
        }
        background = envsys._build_biome_template_prompt("background_plate", direction, "")
        door = envsys._build_biome_template_prompt("door_piece", direction, "")
        self.assertIn("medieval castle / dungeon hall", background)
        self.assertIn("No bright floor pool", background)
        self.assertIn("transparent background", door)
        self.assertIn("Preserve transparent pixels outside the frame", door)

    def test_biome_template_prompt_keeps_structural_templates_generic_and_reference_led(self):
        direction = {
            "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
            "negative_direction": "clean sci-fi surfaces, cartoon props, glossy plastics, bright cheerful saturation",
            "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
        }
        wall = envsys._build_biome_template_prompt("wall_piece", direction, "")
        ceiling = envsys._build_biome_template_prompt("ceiling_piece", direction, "")
        floor = envsys._build_biome_template_prompt("primary_floor_piece", direction, "")

        self.assertIn("The provided reference image is a generic component template", wall)
        self.assertIn("Do not invent arches", wall)
        self.assertIn("preserve its overall silhouette", ceiling)
        self.assertIn("Do not invent arches, ribs", ceiling)
        self.assertIn("Do not reinterpret the template as a full room slice", floor)
        self.assertIn("Do not depict a perspective slab", floor)

    def test_door_frame_uses_direct_adaptation_mode(self):
        self.assertEqual(envsys._component_adaptation_mode("door_frame"), "direct")

    def test_room_aware_v2_slots_use_expected_adaptation_modes(self):
        self.assertEqual(envsys._component_adaptation_mode("background_far_plate"), "gemini")
        self.assertEqual(envsys._component_adaptation_mode("midground_side_frame"), "direct")

    def test_ceiling_band_uses_gemini_adaptation_mode(self):
        self.assertEqual(envsys._component_adaptation_mode("ceiling_band"), "gemini")

    def test_core_structural_biome_templates_do_not_use_sibling_anchor_refs(self):
        biome_pack = {
            "template_library": [
                {"component_type": "wall_piece", "image_path": "art_direction_biomes/test/wall_piece.png"},
                {"component_type": "ceiling_piece", "image_path": "art_direction_biomes/test/ceiling_piece.png"},
                {"component_type": "primary_floor_piece", "image_path": "art_direction_biomes/test/primary_floor_piece.png"},
            ]
        }
        generated_paths = {
            "wall_piece": self.root / "wall_piece.png",
            "ceiling_piece": self.root / "ceiling_piece.png",
            "primary_floor_piece": self.root / "primary_floor_piece.png",
        }
        for path in generated_paths.values():
            envsys.Image.new("RGBA", (16, 16), (80, 90, 100, 255)).save(path)

        self.assertEqual(
            envsys._biome_structural_reference_paths("wall_piece", biome_pack, self.root, generated_paths),
            [],
        )
        self.assertEqual(
            envsys._biome_structural_reference_paths("ceiling_piece", biome_pack, self.root, generated_paths),
            [],
        )
        self.assertEqual(
            envsys._biome_structural_reference_paths("primary_floor_piece", biome_pack, self.root, generated_paths),
            [],
        )

    def test_apply_door_cutout_alpha_removes_checkerboard_and_opening(self):
        candidate = self.root / "door-source.png"
        image = envsys.Image.new("RGBA", (96, 144), (220, 220, 220, 255))
        draw = envsys.ImageDraw.Draw(image)
        for y in range(0, 144, 12):
            for x in range(0, 96, 12):
                if ((x // 12) + (y // 12)) % 2 == 0:
                    draw.rectangle((x, y, x + 11, y + 11), fill=(242, 242, 242, 255))
        draw.rounded_rectangle((18, 10, 78, 134), radius=12, fill=(58, 66, 74, 255))
        draw.rounded_rectangle((32, 24, 64, 118), radius=8, fill=(0, 0, 0, 255))
        image.save(candidate)

        cutout = envsys._apply_door_cutout_alpha(image)
        cutout.save(candidate)

        self.assertGreater(envsys._alpha_ratio(candidate), 0.2)

    def test_component_reference_guides_use_geometry_guides_for_room_aware_slots(self):
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
        self.assertTrue(background_refs[-1].exists())
        self.assertEqual(len(background_refs), 2)
        self.assertEqual(background_refs[0], template)
        self.assertNotEqual(background_refs[-1], template)
        self.assertLess(envsys._region_alpha_ratio(midground_refs[-1], (0.36, 0.18, 0.64, 0.82)), 0.15)
        self.assertEqual(len(floor_refs), 2)
        self.assertEqual(floor_refs[0], template)
        self.assertTrue(floor_refs[-1].exists())
        self.assertEqual(len(door_refs), 1)
        self.assertNotEqual(door_refs[0], template)

    def test_bespoke_reference_prepends_room_silhouette_for_scenic_slots(self):
        refs_root = self.root / "refs-sil"
        template = self.root / "template-sil.png"
        preview = self.root / "preview-sil.png"
        envsys.Image.new("RGBA", (160, 120), (120, 140, 155, 255)).save(template)
        envsys.Image.new("RGBA", (160, 120), (90, 105, 118, 255)).save(preview)
        l_room = {
            "id": "RX",
            "size": {"width": 320, "height": 240},
            "polygon": [[0, 0], [320, 0], [320, 120], [160, 120], [160, 240], [0, 240]],
            "platforms": [{"x": 64, "y": 200, "len": 4}],
            "doors": [{"x": 24, "y": 200, "kind": "transition"}],
        }
        bg = envsys._bespoke_reference_images_for_component(
            "background_far_plate",
            template,
            preview,
            [],
            refs_root,
            (160, 120),
            False,
            room=l_room,
        )
        mg = envsys._bespoke_reference_images_for_component(
            "midground_side_frame",
            template,
            preview,
            [],
            refs_root,
            (160, 120),
            True,
            room=l_room,
        )
        self.assertEqual(len(bg), 3)
        self.assertTrue(str(bg[0]).endswith("-silhouette.png"))
        self.assertEqual(bg[1], template)
        self.assertEqual(len(mg), 3)
        self.assertTrue(str(mg[0]).endswith("-silhouette.png"))
        self.assertEqual(mg[1], template)
        with envsys.Image.open(bg[0]) as sil:
            self.assertEqual(sil.size, (160, 120))

    def test_room_shell_references_use_silhouette_and_preview(self):
        refs_root = self.root / "refs-shell"
        template = self.root / "template-shell.png"
        preview = self.root / "preview-shell.png"
        envsys.Image.new("RGBA", (320, 240), (110, 120, 130, 255)).save(template)
        envsys.Image.new("RGBA", (320, 240), (70, 82, 95, 255)).save(preview)
        l_room = {
            "id": "RX",
            "size": {"width": 320, "height": 240},
            "polygon": [[0, 0], [320, 0], [320, 120], [160, 120], [160, 240], [0, 240]],
            "platforms": [{"x": 64, "y": 200, "len": 4}],
            "doors": [{"x": 24, "y": 200, "kind": "transition"}],
        }
        shell_refs = envsys._bespoke_reference_images_for_component(
            "room_shell_foreground",
            template,
            preview,
            [],
            refs_root,
            (320, 240),
            True,
            room=l_room,
        )
        self.assertEqual(len(shell_refs), 2)
        self.assertTrue(str(shell_refs[0]).endswith("-silhouette.png"))
        self.assertEqual(shell_refs[1], preview)

    def test_write_bespoke_room_silhouette_reference_requires_polygon(self):
        out = self.root / "sil-empty.png"
        self.assertFalse(
            envsys._write_bespoke_room_silhouette_reference({"polygon": [], "chamber_width": 100, "chamber_height": 100}, out, (64, 64))
        )

    def test_bespoke_room_silhouette_reference_uses_dark_clear_not_white(self):
        l_room = {
            "id": "RX",
            "size": {"width": 320, "height": 240},
            "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
        }
        geom = envsys._room_geometry(l_room)
        out = self.root / "sil-dark-clear.png"
        self.assertTrue(envsys._write_bespoke_room_silhouette_reference(geom, out, (320, 240)))
        img = envsys.Image.open(out).convert("RGB")
        pixels = list(img.getdata())
        paper_white = sum(1 for r, g, b in pixels if r >= 250 and g >= 250 and b >= 250)
        self.assertEqual(paper_white, 0)
        self.assertEqual(img.getpixel((0, 0)), envsys.ROOM_SHELL_SILHOUETTE_CLEAR_RGB)

    def test_layout_conditioning_reference_avoids_cyan_outline(self):
        geom = {
            "width": 320,
            "height": 240,
            "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
            "platforms": [{"x": 64, "y": 180, "len": 4}],
            "door_positions": [{"x": 24, "y": 180}],
        }
        png_bytes = envsys._render_room_layout_conditioning_image(geom, {"theme_id": "ruins", "tags": []}, 0)
        img = envsys.Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        pixels = list(img.getdata())
        cyan_like = sum(1 for r, g, b, a in pixels if a > 0 and g >= 210 and b >= 180 and r <= 50)
        self.assertEqual(cyan_like, 0)

    def test_level1_fallback_preview_has_no_accent_cyan_outline(self):
        out = self.root / "lvl1-fallback.png"
        envsys._render_level1_image(
            out,
            {"style_family": "dark fantasy ruins"},
            {"theme_id": "ruins", "tags": [], "description": "x"},
        )
        img = envsys.Image.open(out).convert("RGBA")
        pixels = list(img.getdata())
        cyan_like = sum(1 for r, g, b, a in pixels if a > 0 and g >= 210 and b >= 180 and r <= 50)
        self.assertEqual(cyan_like, 0)

    def test_build_bespoke_prompt_includes_footprint_clause_when_geometry_has_polygon(self):
        l_room = {
            "id": "RX",
            "size": {"width": 320, "height": 240},
            "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
        }
        geom = envsys._room_geometry(l_room)
        prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Ruins", "negative_direction": "none"},
            {
                "mood": "somber",
                "lighting": "low",
                "description": "test",
                "component_schemas": {"background": envsys._default_component_schema("background", "test")},
            },
            {
                "component_type": "background_far_plate",
                "schema_key": "background",
                "target_dimensions": {"width": 1600, "height": 1200},
                "orientation": "full",
                "tile_mode": "stretch",
                "border_treatment": "full_frame",
                "protected_zones": [],
            },
            {"variant_family": "background", "orientation": "full"},
            room_geometry=geom,
        )
        self.assertIn("room footprint conditioning", prompt.lower())
        self.assertIn("chamber bounds", prompt.lower())

    def test_build_bespoke_prompt_room_shell_includes_masonry_thickness_rules(self):
        l_room = {
            "id": "RX",
            "size": {"width": 320, "height": 240},
            "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
        }
        geom = envsys._room_geometry(l_room)
        prompt = envsys._build_bespoke_prompt(
            {"high_level_direction": "Ruins", "negative_direction": "none"},
            {
                "mood": "somber",
                "lighting": "low",
                "description": "test",
                "component_schemas": {"walls": envsys._default_component_schema("walls", "test")},
            },
            {
                "component_type": "room_shell_foreground",
                "schema_key": "walls",
                "target_dimensions": {"width": 1600, "height": 1200},
                "orientation": "full",
                "tile_mode": "stretch",
                "border_treatment": "full_frame",
                "protected_zones": [],
            },
            {"variant_family": "foreground", "orientation": "full"},
            room_geometry=geom,
        )
        low = prompt.lower()
        self.assertIn("heavy masonry", low)
        self.assertIn("hairline", low)
        self.assertIn("edge-fill contract", low)
        self.assertIn("spatial contract", low)
        self.assertIn("shell_band_axis_aligned_bbox_px_inclusive", prompt)
        self.assertIn("mask paint", low)
        self.assertNotIn("only adapt it to the requested fit", low)
        self.assertNotIn("compose fog, depth, and architecture", low)

    def test_room_shell_spatial_contract_json_matches_mask_geometry(self):
        geom = {
            "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]],
            "chamber_width": 320,
            "chamber_height": 240,
        }
        raw = envsys._room_shell_spatial_contract_json(geom, (320, 240))
        self.assertTrue(raw)
        data = json.loads(raw)
        self.assertEqual(data["output_size_px"], [320, 240])
        self.assertIn("shell_band_axis_aligned_bbox_px_inclusive", data)
        self.assertIn("edge_flush_rule", data)
        ref1 = data.get("reference_1_silhouette") or {}
        self.assertIn("neutral_clear_rgb_8_12_16", ref1)
        self.assertNotIn("white_rgb_255", str(data))

    def test_wall_reference_guides_use_full_size_geometry_guides(self):
        refs_root = self.root / "refs"
        template = self.root / "template-wide.png"
        preview = self.root / "preview-wide.png"
        envsys.Image.new("RGBA", (200, 100), (120, 140, 155, 255)).save(template)
        envsys.Image.new("RGBA", (200, 100), (90, 105, 118, 255)).save(preview)

        left_refs = envsys._bespoke_reference_images_for_component(
            "wall_module_left",
            template,
            preview,
            [],
            refs_root,
            (60, 100),
            False,
        )
        right_refs = envsys._bespoke_reference_images_for_component(
            "wall_module_right",
            template,
            preview,
            [],
            refs_root,
            (60, 100),
            False,
        )

        self.assertEqual(left_refs[0], template)
        self.assertEqual(right_refs[0], template)
        with envsys.Image.open(left_refs[1]) as left_image:
            self.assertEqual(left_image.size, (60, 100))
        with envsys.Image.open(right_refs[1]) as right_image:
            self.assertEqual(right_image.size, (60, 100))

    def test_background_retry_prompt_strengthens_outer_shell_definition(self):
        retry = envsys._retry_prompt_for_validation_errors("background_far_plate", "base prompt", ["background_shell_definition_low"], 0)
        self.assertIn("visible enclosing wall faces", retry)
        self.assertIn("Reduce the feeling of a giant open nave", retry)

    def test_background_retry_prompt_can_warn_against_lower_fog_bank(self):
        retry = envsys._retry_prompt_for_validation_errors("background_far_plate", "base prompt", ["some_other_background_issue"], 0)
        self.assertIn("avoid a broad bright lower fog bank", retry)
        self.assertIn("rear-floor depth", retry)

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

    def test_postprocess_background_handles_heat_and_shell_definition_together(self):
        background = self.root / "background-both.png"
        template = self.root / "background-template.png"
        envsys.Image.new("RGBA", (160, 120), (210, 216, 220, 255)).save(background)
        envsys.Image.new("RGBA", (160, 120), (36, 44, 52, 255)).save(template)

        changed = envsys._postprocess_component_for_validation(
            background,
            "background_far_plate",
            ["center_lane_too_hot", "background_shell_definition_low"],
            0,
            template,
        )

        self.assertTrue(changed)
        self.assertLess(envsys._region_luminance(background, (0.34, 0.22, 0.66, 0.78)), 190)

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

    def test_scenic_slots_validate_family_drift_against_sanitized_guide_reference(self):
        raw_template = self.root / "midground-template-raw.png"
        guide = self.root / "midground-guide.png"
        candidate = self.root / "midground-candidate-guide-match.png"

        raw = envsys.Image.new("RGBA", (160, 120), (90, 102, 116, 255))
        draw = envsys.ImageDraw.Draw(raw)
        draw.rectangle((0, 0, 48, 119), fill=(152, 168, 182, 255))
        draw.rectangle((112, 0, 159, 119), fill=(152, 168, 182, 255))
        draw.rectangle((46, 0, 114, 119), fill=(134, 148, 160, 255))
        raw.save(raw_template)

        guided = envsys.Image.new("RGBA", (160, 120), (0, 0, 0, 0))
        draw = envsys.ImageDraw.Draw(guided)
        draw.rectangle((0, 0, 36, 119), fill=(62, 72, 82, 255))
        draw.rectangle((124, 0, 159, 119), fill=(62, 72, 82, 255))
        guided.save(guide)
        guided.save(candidate)

        raw_valid, raw_errors = envsys._validate_bespoke_component(
            candidate,
            "midground_side_frame",
            (160, 120),
            "alpha",
            raw_template,
        )
        guide_valid, guide_errors = envsys._validate_bespoke_component(
            candidate,
            "midground_side_frame",
            (160, 120),
            "alpha",
            guide,
        )

        self.assertFalse(raw_valid)
        self.assertIn("template_family_drift", raw_errors)
        self.assertTrue(guide_valid)
        self.assertNotIn("template_family_drift", guide_errors)

    def test_runtime_review_capture_page_uses_wrapper_instead_of_hash_packing_layout(self):
        output = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review" / "runtime-review.png"
        url = envsys._write_runtime_review_capture_page(
            self.saved,
            "R1",
            "http://127.0.0.1:8766/tools/2d-sprite-and-animation/index.html",
            output,
        )
        capture_page = output.parent / "runtime-capture.html"
        layout_json = output.parent / "runtime-layout.json"
        html = capture_page.read_text(encoding="utf-8")

        self.assertEqual(
            url,
            f"http://127.0.0.1:8766/tools/2d-sprite-and-animation/projects-data/{self.project_id}/room_environment_assets/R1/review/runtime-capture.html",
        )
        self.assertTrue(layout_json.exists())
        self.assertIn("/index.html#preview=embed&capture=runtime-review&layout_url=", html)
        self.assertIn("&start=R1", html)
        self.assertNotIn("layout=", html)

    def test_runtime_review_capture_uses_browser_by_default_when_available(self):
        output = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review" / "runtime-review.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        capture_helper = self.root / "scripts" / "capture_runtime_review.js"
        capture_helper.parent.mkdir(parents=True, exist_ok=True)
        capture_helper.write_text("// test helper stub\n", encoding="utf-8")
        old_pref = envsys.os.environ.pop("ROOM_ENVIRONMENT_REVIEW_USE_BROWSER", None)
        try:
            with mock.patch.object(envsys, "_find_headless_browser", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), \
                 mock.patch.object(envsys, "_write_runtime_review_capture_page", return_value="http://127.0.0.1:8766/mock-runtime-capture.html"), \
                 mock.patch.object(envsys.shutil, "which", return_value="/usr/bin/node"), \
                 mock.patch.object(envsys.subprocess, "run") as run_mock, \
                 mock.patch.object(envsys, "_runtime_review_capture_is_usable", return_value=True):
                output.write_bytes(b"browser-shot")
                mode, issue = envsys._capture_runtime_review_screenshot(self.saved, "R1", {}, output)
        finally:
            if old_pref is None:
                envsys.os.environ.pop("ROOM_ENVIRONMENT_REVIEW_USE_BROWSER", None)
            else:
                envsys.os.environ["ROOM_ENVIRONMENT_REVIEW_USE_BROWSER"] = old_pref

        self.assertEqual(mode, "headless_browser")
        self.assertIsNone(issue)
        run_mock.assert_called_once()
        args, kwargs = run_mock.call_args
        self.assertEqual(args[0][0], "/usr/bin/node")
        self.assertIn("scripts/capture_runtime_review.js", args[0])
        self.assertIn("--browser", args[0])
        self.assertIn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", args[0])
        self.assertIn("--output", args[0])
        self.assertIn("tools/2d-sprite-and-animation/projects-data/project-alpha/room_environment_assets/R1/review/runtime-review.png", args[0])
        self.assertEqual(kwargs.get("cwd"), str(self.root))
        cmd = args[0]
        self.assertEqual(cmd[cmd.index("--width") + 1], "1280")
        self.assertEqual(cmd[cmd.index("--height") + 1], "880")

    def test_runtime_review_capture_can_be_explicitly_disabled(self):
        output = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review" / "runtime-review.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        old_pref = envsys.os.environ.get("ROOM_ENVIRONMENT_REVIEW_USE_BROWSER")
        envsys.os.environ["ROOM_ENVIRONMENT_REVIEW_USE_BROWSER"] = "false"
        try:
            mode, issue = envsys._capture_runtime_review_screenshot(self.saved, "R1", {}, output)
        finally:
            if old_pref is None:
                envsys.os.environ.pop("ROOM_ENVIRONMENT_REVIEW_USE_BROWSER", None)
            else:
                envsys.os.environ["ROOM_ENVIRONMENT_REVIEW_USE_BROWSER"] = old_pref

        self.assertEqual(mode, "composite_fallback")
        self.assertEqual(issue, "headless_browser_disabled_by_config")

    def test_primary_floor_band_bounds_expand_to_chamber_bounds_not_canvas(self):
        room = {
            "id": "RG-R2",
            "name": "Broken Hall Passage",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
            "platforms": [{"id": "RG-R2-P1", "x": 256, "y": 992, "len": 30}],
            "doors": [],
        }
        bounds = envsys._primary_floor_band_bounds(room)
        self.assertEqual(bounds, (160, 968, 1280, 220))

    def test_wall_shell_bounds_anchor_to_polygon_edges_not_canvas_edges(self):
        room = {
            "id": "RG-R2",
            "name": "Broken Hall Passage",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
            "platforms": [],
            "doors": [],
        }
        left = envsys._wall_shell_bounds("wall_module_left", {"x": 0, "y": 0, "display_width": 96, "display_height": 600}, room)
        right = envsys._wall_shell_bounds("wall_module_right", {"x": 0, "y": 0, "display_width": 96, "display_height": 600}, room)
        self.assertEqual(left, (160, 160, 205, 880))
        self.assertEqual(right, (1235, 160, 205, 880))

    def test_generate_bespoke_assets_uses_room_aware_generation_for_shell_slots(self):
        envsys.update_project_art_direction(self.project_id, {"template_id": "ruined-gothic", "locked": True})
        envsys.build_room_environment_spec(
            self.project_id,
            "R1",
            {"description": "A readable ruined hall with heavy stone and a strong central route."},
        )
        generated = envsys.generate_room_environment_previews(self.project_id, "R1", {})
        preview_id = generated["environment"]["preview"]["images"][0]["preview_id"]
        envsys.approve_room_environment_preview(self.project_id, "R1", {"preview_id": preview_id})

        with mock.patch.object(
            envsys,
            "_generate_bespoke_component_from_references",
            return_value=(True, None),
        ) as mocked_ai, \
             mock.patch.object(envsys, "_validate_bespoke_component", return_value=(True, [])), \
             mock.patch.object(envsys, "_run_runtime_review", return_value=self._passing_runtime_review()):
            result = envsys.generate_room_environment_asset_pack(self.project_id, "R1", {"preview_id": preview_id})

        bespoke = result["environment"]["runtime"]["bespoke_asset_manifest"]
        self.assertEqual(bespoke["status"], "ready")
        self.assertGreaterEqual(mocked_ai.call_count, 8)

    def test_gemini_last_error_recorded_on_http_error(self):
        import io

        def raise_http(*_a, **_k):
            fp = io.BytesIO(b'{"error":{"message":"API key not valid"}}')
            raise envsys.urllib.error.HTTPError("http://example", 400, "Bad", {}, fp)

        with mock.patch.dict(envsys.os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), \
             mock.patch.object(envsys.urllib.request, "urlopen", side_effect=raise_http):
            _, err = envsys._gemini_generate_content_rest(
                "gemini-2.5-flash-image", [{"text": "probe"}], response_modalities=["IMAGE"]
            )
        self.assertIsNotNone(err)
        snap = envsys.gemini_last_error_snapshot()
        self.assertTrue(snap.get("message"))
        self.assertTrue(snap.get("recorded_at"))

    def test_gemini_generate_content_rest_uses_timeout(self):
        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"candidates":[]}'

        with mock.patch.dict(envsys.os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_HTTP_TIMEOUT_SECONDS": "42"}, clear=False), \
             mock.patch.object(envsys.urllib.request, "urlopen", return_value=_FakeResponse()) as urlopen:
            response, err = envsys._gemini_generate_content_rest("gemini-2.5-flash", [{"text": "healthy"}], response_modalities=["TEXT"])

        self.assertIsNone(response)
        self.assertEqual(err, "empty_candidates")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 42)

    def test_runtime_review_capture_usability_rejects_black_frame(self):
        black = self.root / "runtime-black.png"
        almost_black = self.root / "runtime-almost-black.png"
        ok = self.root / "runtime-ok.png"
        envsys.Image.new("RGB", (40, 20), (0, 0, 0)).save(black)
        image = envsys.Image.new("RGB", (40, 20), (0, 0, 0))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 3, 3), fill=(150, 180, 220))
        image.save(almost_black)
        image = envsys.Image.new("RGB", (40, 20), (0, 0, 0))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((8, 4, 32, 16), fill=(96, 112, 128))
        image.save(ok)

        self.assertFalse(envsys._runtime_review_capture_is_usable(black))
        self.assertFalse(envsys._runtime_review_capture_is_usable(almost_black))
        self.assertTrue(envsys._runtime_review_capture_is_usable(ok))

    def test_runtime_review_headless_capture_uses_longer_budget(self):
        source = Path(envsys.__file__).read_text(encoding="utf-8")
        self.assertIn("--virtual-time-budget=20000", source)
        self.assertIn("timeout=60", source)

    def test_composite_runtime_review_skips_non_runtime_structural_overlays(self):
        room = {
            "id": "R1",
            "polygon": [[0, 0], [1600, 0], [1600, 1200], [0, 1200]],
            "global": {"x": 0, "y": 0},
        }
        review = self.root / "runtime-composite.png"
        background = self.root / "background.png"
        ceiling = self.root / "ceiling.png"
        panel = self.root / "panel.png"
        envsys.Image.new("RGBA", (1600, 1200), (20, 30, 40, 255)).save(background)
        envsys.Image.new("RGBA", (1600, 224), (220, 40, 40, 255)).save(ceiling)
        envsys.Image.new("RGBA", (760, 648), (40, 220, 40, 255)).save(panel)
        assets = {
            "R1-background": {
                "slot_id": "R1-background",
                "component_type": "background_far_plate",
                "slot_group": "background",
                "url": f"/{background.relative_to(envsys.ROOT).as_posix()}",
                "placement": {"x": 800, "y": 1200, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 1},
            },
            "R1-ceiling": {
                "slot_id": "R1-ceiling",
                "component_type": "ceiling_band",
                "slot_group": "misc",
                "url": f"/{ceiling.relative_to(envsys.ROOT).as_posix()}",
                "placement": {"x": 800, "y": 0, "display_width": 1600, "display_height": 224, "origin_x": 0.5, "origin_y": 0},
            },
            "R1-panel": {
                "slot_id": "R1-panel",
                "component_type": "backwall_panel",
                "slot_group": "misc",
                "url": f"/{panel.relative_to(envsys.ROOT).as_posix()}",
                "placement": {"x": 400, "y": 240, "display_width": 760, "display_height": 648, "origin_x": 0.5, "origin_y": 0},
            },
        }

        envsys._composite_runtime_review_image(room, assets, review)

        image = envsys.Image.open(review).convert("RGBA")
        self.assertEqual(image.getpixel((800, 20))[:3], (220, 40, 40))
        self.assertEqual(image.getpixel((400, 400))[:3], (20, 30, 40))

    def test_composite_runtime_review_matches_runtime_floor_top_scaling(self):
        asset = self.root / "floor-top.png"
        review = self.root / "runtime-floor-top.png"
        envsys.Image.new("RGBA", (1600, 96), (180, 190, 200, 255)).save(asset)
        item = {
            "slot_id": "R1-main-floor-top",
            "component_type": "main_floor_top",
            "slot_group": "floor",
            "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
            "placement": {"x": 800, "y": 960, "display_width": 1600, "display_height": 96, "origin_x": 0.5, "origin_y": 0.5},
        }
        composed = envsys._composite_runtime_asset_sprite(item, asset)
        self.assertIsNotNone(composed)
        sprite, (x, y) = composed
        self.assertEqual(sprite.size[0], 1600)
        self.assertLess(sprite.size[1], 96)
        self.assertEqual(x, 0)
        self.assertLess(y, 960)

    def test_render_bespoke_wall_module_uses_synthetic_structural_adaptation(self):
        template = self.root / "wall-template-source.png"
        output = self.root / "wall-template-output.png"
        envsys.Image.new("RGBA", (1600, 1200), (52, 64, 72, 255)).save(template)

        original = envsys._render_synthetic_structural_component

        def guard(size, component_type, template_source):
            if component_type == "wall_module_left":
                raise AssertionError("wall modules should use synthetic structural rendering")
            return original(size, component_type, template_source)

        envsys._render_synthetic_structural_component = guard
        try:
            ok = envsys._render_bespoke_component_from_template(
                template,
                output,
                (380, 1068),
                False,
                "wall_module_left",
            )
        finally:
            envsys._render_synthetic_structural_component = original
        self.assertFalse(ok)

    def test_room_component_plan_uses_component_specific_structural_slots(self):
        room = {
            "id": "R1",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[128, 128], [1472, 128], [1472, 1088], [128, 1088]],
            "platforms": [{"id": "P1", "x": 256, "y": 960, "len": 24}, {"id": "P2", "x": 512, "y": 672, "len": 8}],
            "doors": [{"id": "D1", "x": 256, "y": 960}],
        }
        plan = envsys._room_component_plan(room, "preview-1", self._mock_biome_pack())
        ceiling = next(item for item in plan if item["component_type"] == "ceiling_band")
        left_wall = next(item for item in plan if item["component_type"] == "wall_module_left")
        left_trim = next(item for item in plan if item["component_type"] == "wall_base_trim_left")
        floor_top = next(item for item in plan if item["component_type"] == "main_floor_top")
        platform_top = next(item for item in plan if item["component_type"] == "hero_platform_top")
        self.assertEqual(ceiling["source_template_id"], "tmpl-ceiling")
        self.assertEqual(left_wall["source_template_id"], "tmpl-wall")
        self.assertEqual(left_trim["source_template_id"], "tmpl-wall")
        self.assertEqual(floor_top["source_template_id"], "tmpl-floor")
        self.assertEqual(platform_top["source_template_id"], "tmpl-platform")

    def test_render_bespoke_midground_side_frame_clears_center_lane(self):
        template = self.root / "midground-template-source.png"
        output = self.root / "midground-template-output.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (255, 255, 255, 255))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 220, 1200), fill=(20, 28, 36, 255))
        draw.rectangle((1380, 0, 1600, 1200), fill=(20, 28, 36, 255))
        image.save(template)

        ok = envsys._render_bespoke_component_from_template(
            template,
            output,
            (1600, 1200),
            True,
            "midground_side_frame",
        )

        self.assertTrue(ok)
        rendered = envsys.Image.open(output).convert("RGBA")
        self.assertEqual(rendered.getpixel((800, 600))[3], 0)
        self.assertGreater(rendered.getpixel((100, 600))[3], 0)

    def test_render_bespoke_wall_module_generates_flat_wall_mass_from_wall_piece(self):
        template = self.root / "foreground-frame-wall-source.png"
        output = self.root / "foreground-frame-wall-output.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 260, 1200), fill=(180, 30, 30, 255))
        draw.rectangle((1340, 0, 1600, 1200), fill=(30, 180, 30, 255))
        image.save(template)

        ok = envsys._render_bespoke_component_from_template(
            template,
            output,
            (320, 960),
            False,
            "wall_module_left",
        )

        self.assertTrue(ok)
        rendered = envsys.Image.open(output).convert("RGBA")
        center = rendered.getpixel((rendered.width // 2, rendered.height // 2))[:3]
        outer = rendered.getpixel((24, rendered.height // 2))[:3]
        inner = rendered.getpixel((rendered.width - 12, rendered.height // 2))[:3]
        self.assertLess(sum(outer), sum(center))
        self.assertLess(sum(inner), sum(center))
        self.assertNotEqual(center, (0, 0, 0))

    def test_composite_runtime_review_scopes_scenic_layers_to_chamber_bounds(self):
        room = {
            "id": "R1",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
            "platforms": [{"id": "R1-P1", "x": 192, "y": 1024, "len": 38}],
        }
        asset = self.root / "background-chamber.png"
        review = self.root / "runtime-chamber-scope.png"
        envsys.Image.new("RGBA", (1600, 1200), (180, 40, 40, 255)).save(asset)
        assets = {
            "R1-background": {
                "slot_id": "R1-background",
                "component_type": "background_far_plate",
                "slot_group": "background",
                "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
                "placement": {"x": 800, "y": 1200, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 1},
            },
        }

        envsys._composite_runtime_review_image(room, assets, review)

        image = envsys.Image.open(review).convert("RGBA")
        self.assertEqual(image.getpixel((800, 500))[:3], (180, 40, 40))
        self.assertNotEqual(image.getpixel((80, 500))[:3], (180, 40, 40))
        self.assertNotEqual(image.getpixel((800, 1120))[:3], (180, 40, 40))

    def test_composite_runtime_asset_scopes_room_shell_to_chamber_bounds(self):
        room = {
            "id": "R1",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
            "platforms": [{"id": "R1-P1", "x": 192, "y": 1024, "len": 38}],
        }
        asset = self.root / "room-shell-chamber.png"
        envsys.Image.new("RGBA", (800, 600), (50, 120, 200, 255)).save(asset)
        item = {
            "slot_id": "R1-room-shell",
            "component_type": "room_shell_foreground",
            "slot_group": "foreground",
            "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
            "placement": {"x": 800, "y": 600, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 0.5},
        }
        composed = envsys._composite_runtime_asset_sprite(item, asset, room)
        self.assertIsNotNone(composed)
        sprite, (x, y) = composed
        self.assertEqual(sprite.size, (1280, 880))
        self.assertEqual((x, y), (160, 160))
        self.assertGreater(sprite.getpixel((sprite.size[0] // 2, sprite.size[1] // 2))[3], 240)

    def test_composite_runtime_review_matches_runtime_floor_face_band_height(self):
        asset = self.root / "floor-face.png"
        envsys.Image.new("RGBA", (1600, 97), (90, 100, 110, 255)).save(asset)
        room = {
            "id": "R1",
            "size": {"width": 1600, "height": 1200},
            "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
            "platforms": [{"id": "R1-P1", "x": 192, "y": 1024, "len": 38}],
        }
        item = {
            "slot_id": "R1-main-floor-face",
            "component_type": "main_floor_face",
            "slot_group": "floor",
            "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
            "placement": {"x": 192, "y": 1036, "display_width": 1216, "display_height": 97, "origin_x": 0, "origin_y": 0},
        }
        composed = envsys._composite_runtime_asset_sprite(item, asset, room)
        self.assertIsNotNone(composed)
        sprite, (x, y) = composed
        self.assertEqual(sprite.size[0], 1280)
        self.assertGreaterEqual(sprite.size[1], 97)
        self.assertEqual(x, 160)
        self.assertLess(y, 1024)

    def test_composite_runtime_review_uses_wall_module_asset_for_large_rooms(self):
        asset = self.root / "wall-shell.png"
        envsys.Image.new("RGBA", (380, 1068), (255, 0, 0, 255)).save(asset)
        room = {
            "id": "R2",
            "size": {"width": 2112, "height": 1248},
            "polygon": [[0, 0], [2112, 0], [2112, 1248], [0, 1248]],
        }
        item = {
            "slot_id": "R2-wall-module-left",
            "component_type": "wall_module_left",
            "slot_group": "walls",
            "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
            "placement": {"x": 0, "y": 0, "display_width": 380, "display_height": 1068, "origin_x": 0, "origin_y": 0},
        }
        composed = envsys._composite_runtime_asset_sprite(item, asset, room)
        self.assertIsNotNone(composed)
        sprite, (x, y) = composed
        self.assertGreaterEqual(sprite.size[0], 160)
        self.assertLess(sprite.size[0], 380)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)
        self.assertEqual(sprite.getpixel((sprite.size[0] // 2, sprite.size[1] // 2))[:3], (255, 0, 0))

    def test_composite_runtime_review_scopes_ceiling_band_to_chamber_top(self):
        asset = self.root / "ceiling-band.png"
        envsys.Image.new("RGBA", (1600, 224), (20, 24, 28, 255)).save(asset)
        room = {
            "id": "R2",
            "size": {"width": 2112, "height": 1248},
            "polygon": [[128, 160], [1984, 160], [1984, 1088], [128, 1088]],
        }
        item = {
            "slot_id": "R2-ceiling",
            "component_type": "ceiling_band",
            "slot_group": "ceiling",
            "url": f"/{asset.relative_to(envsys.ROOT).as_posix()}",
            "placement": {"x": 1056, "y": 0, "display_width": 2112, "display_height": 224, "origin_x": 0.5, "origin_y": 0},
        }
        composed = envsys._composite_runtime_asset_sprite(item, asset, room)
        self.assertIsNotNone(composed)
        sprite, (x, y) = composed
        self.assertEqual(sprite.size[0], 1856)
        self.assertEqual(x, 128)
        self.assertEqual(y, 160)
        self.assertGreater(sprite.getpixel((sprite.size[0] // 2, 0))[3], 240)
        self.assertEqual(sprite.getpixel((sprite.size[0] // 2, sprite.size[1] - 4))[:3], (20, 24, 28))

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

    def test_runtime_review_blocks_top_occlusion_slab_artifact(self):
        review_root = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review"
        review_root.mkdir(parents=True, exist_ok=True)
        screenshot = review_root / "runtime-review.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (70, 84, 96, 255))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1600, 160), fill=(18, 24, 28, 255))
        draw.rectangle((220, 200, 1380, 980), fill=(82, 98, 112, 255))
        image.save(screenshot)

        with mock.patch.object(envsys, "_capture_runtime_review_screenshot", return_value=("mocked", None)):
            review = envsys._run_runtime_review(self.saved, self.project_id, "R1", {})

        self.assertEqual(review["status"], "fail")
        self.assertIn("top_occlusion_slab_present", review["fail_reasons"])

    def test_runtime_review_blocks_noncanonical_scenic_layer_recovery(self):
        review_root = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review"
        review_root.mkdir(parents=True, exist_ok=True)
        screenshot = review_root / "runtime-review.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (70, 84, 96, 255))
        image.save(screenshot)
        assets = {
            "R1-background": {
                "slot_id": "R1-background",
                "component_type": "background_far_plate",
                "url": "/mock/background.png",
                "generation_source": "restored_from_calibration_20260402",
                "placement": {"x": 800, "y": 1200, "display_width": 1600, "display_height": 1200, "origin_x": 0.5, "origin_y": 1},
            }
        }

        with mock.patch.object(envsys, "_capture_runtime_review_screenshot", return_value=("mocked", None)):
            review = envsys._run_runtime_review(self.saved, self.project_id, "R1", assets)

        self.assertEqual(review["status"], "fail")
        self.assertIn("scenic_layers_noncanonical", review["fail_reasons"])

    def test_validate_foreground_frame_source_passes_correct_perimeter_frame(self):
        path = self.root / "fg-frame-pass.png"
        img = envsys.Image.new("RGBA", (1600, 1200), envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        # Top band: full-width ceiling cap
        draw.rectangle((0, 0, 1600, ft), fill=(70, 60, 50, 255))
        # Side walls: two tones so outer vs inner face luminance differs (validator scales with border width).
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, 0, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, ft, 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        # Bottom floor band
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(70, 60, 50, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertTrue(valid, f"Expected valid, got errors: {errors}")
        self.assertEqual(errors, [])

    def test_validate_foreground_frame_source_fails_missing_top_band(self):
        path = self.root / "fg-frame-no-top.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        # Top 20% must stay dark: do not paint side walls into y < 20% h (else top_band_lum reads wall mass).
        y_top_cut = int(1200 * 0.20)
        # Left and right walls present but top band left pitch black
        draw.rectangle((0, y_top_cut, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), max(ft, y_top_cut), fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, y_top_cut, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, max(ft, y_top_cut), 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("top_band_missing_or_too_dark", errors)

    def test_validate_foreground_frame_source_fails_fragmented_top_band(self):
        path = self.root / "fg-frame-fragmented-top.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        draw.rectangle((0, 0, 220, 1200), fill=(65, 55, 45, 255))
        draw.rectangle((1380, 0, 1600, 1200), fill=(65, 55, 45, 255))
        draw.rectangle((0, 0, 420, min(220, ft)), fill=(72, 62, 52, 255))
        draw.rectangle((1180, 0, 1600, min(220, ft)), fill=(72, 62, 52, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(72, 62, 52, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("top_band_not_continuous", errors)

    def test_validate_foreground_frame_source_fails_top_band_lower_edge_break(self):
        path = self.root / "fg-frame-top-lower-break.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (26, 34, 42, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        # Lower edge of the top 20% strip (validator samples 14%–20% h vs full 0%–20% h).
        y_top20 = int(1200 * 0.20)
        y_top14 = int(1200 * 0.14)
        y_top_cut = y_top20
        draw.rectangle((0, 0, 1600, ft), fill=(52, 64, 70, 255))
        draw.rectangle((0, y_top14, 1600, y_top20), fill=(22, 24, 28, 255))
        # Keep side-wall paint out of the top 20% strip so the lower-edge luminance break remains detectable.
        draw.rectangle((0, y_top_cut, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), max(ft, y_top_cut), fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, y_top_cut, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, max(ft, y_top_cut), 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(70, 60, 50, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("top_band_lower_edge_break", errors)

    def test_validate_foreground_frame_source_fails_collapsed_right_wall(self):
        path = self.root / "fg-frame-no-right.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        # Top band and left wall present; right side left pitch black
        draw.rectangle((0, 0, 1600, ft), fill=(70, 60, 50, 255))
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(70, 60, 50, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("right_wall_collapsed", errors)

    def test_validate_foreground_frame_source_fails_floating_interior_ledges(self):
        path = self.root / "fg-frame-floating.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        # Minimal perimeter so walls and top just pass their thresholds
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        draw.rectangle((0, 0, 1600, ft), fill=(40, 35, 30, 255))
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, 0, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, ft, 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        # Broad bright floating shelf covering most of the center mid-height zone —
        # represents the "partial scene/atlas with floating ledge bands" failure mode
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        draw.rectangle((350, 320, 1250, 840), fill=(150, 135, 118, 255))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("floating_interior_ledges", errors)

    def test_validate_foreground_frame_source_fails_weak_wall_to_center_transition(self):
        path = self.root / "fg-frame-flat-side-fields.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (36, 42, 48, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        draw.rectangle((0, 0, 1600, ft), fill=(50, 58, 66, 255))
        draw.rectangle((0, 0, fs + 40, 1200), fill=(40, 46, 54, 255))
        draw.rectangle((1600 - fs - 40, 0, 1600, 1200), fill=(40, 46, 54, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(54, 62, 70, 255))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("left_wall_center_transition_weak", errors)
        self.assertIn("right_wall_center_transition_weak", errors)

    def test_validate_foreground_frame_source_fails_bands_not_distinct_from_center(self):
        path = self.root / "fg-frame-undistinct-bands.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        draw.rectangle((0, 0, 1600, ft), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, 0, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, ft, 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il, itop, ir, ib), fill=envsys.FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("top_band_not_distinct_from_center", errors)
        self.assertIn("bottom_band_not_distinct_from_center", errors)

    def test_validate_foreground_frame_source_fails_missing_center_key(self):
        path = self.root / "fg-frame-no-center-key.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (34, 44, 52, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        draw.rectangle((0, 0, 1600, ft), fill=(70, 60, 50, 255))
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, 0, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, ft, 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(70, 60, 50, 255))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("center_key_missing_or_contaminated", errors)

    def test_validate_foreground_frame_source_fails_center_intrusion(self):
        path = self.root / "fg-frame-center-intrusion.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(img)
        ft = envsys.FOREGROUND_FRAME_BORDER_TOP_PX
        fb = envsys.FOREGROUND_FRAME_BORDER_BOTTOM_PX
        fs = envsys.FOREGROUND_FRAME_BORDER_SIDE_PX
        draw.rectangle((0, 0, 1600, ft), fill=(70, 60, 50, 255))
        draw.rectangle((0, 0, fs, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((fs - min(120, fs // 2), ft, fs, 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((1600 - fs, 0, 1600, 1200), fill=(88, 75, 62, 255))
        draw.rectangle((1600 - fs, ft, 1600 - fs + min(120, fs // 2), 1200 - fb), fill=(42, 38, 34, 255))
        draw.rectangle((0, 1200 - fb, 1600, 1200), fill=(70, 60, 50, 255))
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        draw.rectangle((il + 20, itop + 10, ir - 20, ib - 10), fill=(185, 170, 150, 255))
        img.save(path)
        valid, errors = envsys._validate_foreground_frame_source(path)
        self.assertFalse(valid)
        self.assertIn("center_intrusion_excessive", errors)

    def test_render_bespoke_ceiling_band_uses_synthetic_ceiling_render(self):
        template = self.root / "foreground-frame-ceiling-source.png"
        output = self.root / "foreground-frame-ceiling-output.png"
        image = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        draw = envsys.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1600, 140), fill=(24, 32, 40, 255))
        draw.rectangle((0, 140, 1600, 240), fill=(210, 180, 120, 255))
        image.save(template)

        ok = envsys._render_bespoke_component_from_template(
            template,
            output,
            (1600, 224),
            False,
            "ceiling_band",
        )

        self.assertTrue(ok)
        rendered = envsys.Image.open(output).convert("RGBA")
        top = rendered.getpixel((rendered.width // 2, 12))[:3]
        mid = rendered.getpixel((rendered.width // 2, rendered.height // 2))[:3]
        seam = rendered.getpixel((max(8, rendered.width // 9), rendered.height // 2))[:3]
        self.assertNotEqual(top, mid)
        self.assertNotEqual(mid, seam)

    def test_generate_biome_pack_visuals_rejects_invalid_foreground_frame_source(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        pack = envsys.load_project(self.project_id)["art_direction"]["biome_packs"][0]
        foreground_template = next(
            item for item in pack["template_library"] if item["component_type"] == "foreground_frame"
        )
        foreground_template["biome_visual_generated_at"] = "2026-03-28T12:00:00Z"
        self.saved["art_direction"]["biome_packs"][0]["template_library"] = pack["template_library"]
        existing_rel = foreground_template["image_path"]
        existing_path = self.projects_root / self.project_id / existing_rel
        original = envsys.Image.new("RGBA", (1600, 1200), (90, 80, 70, 255))
        original.save(existing_path)
        original_bytes = existing_path.read_bytes()
        # AI generates successfully but the image fails structural validation
        bad_frame = envsys.Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))

        def fake_generate_bad_frame(output_path, prompt, refs, size, transparent, component_type=None):
            bad_frame.save(output_path)
            return True, None

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate_bad_frame):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["foreground_frame"]},
            )
        self.assertTrue(out["ok"])
        self.assertTrue(out["used_ai"])
        result = next(r for r in out["results"] if r["component_type"] == "foreground_frame")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "foreground_frame_source_invalid")
        self.assertIn("validation_errors", result)
        debug_rel = result.get("debug_rejected_candidate_path")
        self.assertTrue(debug_rel)
        debug_path = self.projects_root / self.project_id / debug_rel
        self.assertTrue(debug_path.exists())
        self.assertIn(".tmp_biome_generation_rejections", debug_rel)
        self.assertEqual(existing_path.read_bytes(), original_bytes)
        pack = out["art_direction"]["biome_packs"][0]
        self.assertFalse(any(".tmp_biome_generation_rejections" in str(t.get("image_path") or "") for t in pack["template_library"]))

    def test_generate_biome_pack_visuals_preserves_existing_wall_piece_when_candidate_fails_validation(self):
        envsys.generate_project_art_direction_concepts(self.project_id, {"template_id": "ruined-gothic"})
        envsys.update_project_art_direction(
            self.project_id,
            {"template_id": "ruined-gothic", "locked": True, "frozen_concept_ids": ["art-direction-01"]},
        )
        pack = envsys.load_project(self.project_id)["art_direction"]["biome_packs"][0]
        wall_template = next(item for item in pack["template_library"] if item["component_type"] == "wall_piece")
        wall_template["biome_visual_generated_at"] = "2026-03-28T12:00:00Z"
        self.saved["art_direction"]["biome_packs"][0]["template_library"] = pack["template_library"]
        wall_path = self.projects_root / self.project_id / str(wall_template["image_path"])
        original = envsys.Image.new("RGBA", (512, 1200), (80, 90, 100, 255))
        original.save(wall_path)
        original_bytes = wall_path.read_bytes()

        def fake_generate_bad_wall(output_path, prompt, refs, size, transparent, component_type=None):
            bad = envsys.Image.new("RGBA", size, (68, 76, 84, 255))
            draw = envsys.ImageDraw.Draw(bad)
            draw.rectangle((int(size[0] * 0.3), int(size[1] * 0.2), int(size[0] * 0.7), int(size[1] * 0.8)), fill=(0, 0, 0, 0))
            bad.save(output_path)
            return True, None

        with mock.patch.object(envsys, "_generate_bespoke_component_from_references", side_effect=fake_generate_bad_wall):
            out = envsys.generate_biome_pack_visuals(
                self.project_id,
                {"confirm_overwrite": True, "component_types": ["wall_piece"]},
            )

        self.assertTrue(out["ok"])
        result = next(r for r in out["results"] if r["component_type"] == "wall_piece")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "wall_piece_source_invalid")
        self.assertEqual(wall_path.read_bytes(), original_bytes)

    def test_foreground_frame_prompt_explicitly_bans_side_ledge_drift(self):
        il, itop, ir, ib = envsys._foreground_frame_inner_rect_inclusive()
        prompt = envsys._build_biome_template_prompt(
            "foreground_frame",
            {"high_level_direction": "Broken gothic halls", "negative_direction": "", "lighting_rules": ["single focal glow", "fog depth near floor"]},
            "",
        )
        self.assertIn("no inward shelves", prompt)
        self.assertIn("flush, vertical, and perimeter-only", prompt)
        self.assertIn("clearly visible masonry ceiling band", prompt)
        self.assertIn("solid bright green screen color", prompt)
        self.assertIn("Do not solve the frame by making the whole image uniformly dark blue-gray", prompt)
        self.assertIn("top band must read as an obvious horizontal masonry strip by eye", prompt)
        self.assertIn(
            f"green center opening must not begin inside the top {envsys.FOREGROUND_FRAME_BORDER_TOP_PX} pixels",
            prompt,
        )
        self.assertIn("strengthen the top strip first rather than darkening the whole frame", prompt)
        self.assertIn("no black wedges", prompt)
        self.assertIn("bottom band must also read as an obvious horizontal masonry strip by eye", prompt)
        self.assertIn("strengthen the bottom strip second rather than turning the lower frame into a shadow mass", prompt)
        self.assertIn(f"green center opening must end above y={ib}", prompt)
        self.assertIn("no black corner cutouts", prompt)
        self.assertIn("retaining wall face or plinth course seen straight on", prompt)
        self.assertIn("do not draw paving stones, receding tile seams, trapezoid slab tops", prompt)
        self.assertIn("do not add a bright upper lip, rim light, or recessed shadow shelf", prompt)
        self.assertIn("ceiling band and floor band = readable horizontal strip zones", prompt)
        self.assertIn("outer wall strips = darkest and most detailed zone", prompt)
        self.assertIn("Do not make the wall strips and center field the same value family", prompt)
        self.assertIn("Center field should show no masonry cues at all", prompt)
        self.assertIn("Do not make the right wall softer, flatter, dimmer, or less distinct than the left wall", prompt)
        self.assertIn("Preserve the provided border silhouette and occupied-zone layout exactly", prompt)
        self.assertIn("no perspective floor plane", prompt)
        self.assertIn("no inward-lit bevels", prompt)
        self.assertIn("no cast shadows projecting into the center", prompt)
        self.assertIn("no dark inner shadow columns", prompt)
        self.assertIn("keyed holdout zone", prompt)
        self.assertIn("No circular hotspot", prompt)
        self.assertIn("no radial vignette", prompt)
        self.assertIn("flat orthographic front elevation", prompt)
        self.assertIn("straight-on front elevation with zero perspective convergence and zero reveal depth", prompt)
        self.assertIn("Do not depict an inset chamber opening, window reveal, portal mouth, inner jamb, receding corridor, or boxed recess", prompt)
        self.assertIn("front-facing surfaces only, not side faces or top faces", prompt)
        self.assertIn("No diagonal receding edges, no visible wall thickness returns, no interior corner perspective", prompt)
        self.assertIn("geometry-only occupancy guide", prompt)
        self.assertIn("solid bright green screen color", prompt)
        self.assertIn(f"The very first green row must begin at y={itop}", prompt)
        self.assertIn(
            f"Pixels on the center boundary such as ({il},{itop}), (800,{itop}), ({ir},{itop}), ({il},{ib}), and ({ir},{ib})",
            prompt,
        )
        self.assertIn("Do not enlarge the green field upward or downward beyond those exact vertical limits", prompt)
        self.assertIn("keyed holdout zone", prompt)
        self.assertIn("pillars, posts, columns, or freestanding vertical supports", prompt)
        self.assertIn("fused to the outer image border", prompt)
        self.assertIn("do not add bright inner edge highlights, bevel rims, side-face reveals", prompt)
        self.assertIn("must never be lighter than the main wall mass", prompt)
        self.assertIn("no inset panel border, and no light rim or outline around the center field", prompt)
        self.assertIn("must not be framed by a second lighter rectangle inside the border shell", prompt)
        self.assertIn("Do not copy its flat fills, gray values, outlines, or mask-like treatment literally", prompt)
        self.assertIn("If the geometry guide and the style swatch disagree", prompt)
        self.assertIn("preserve the occupied coordinates and border silhouette from the geometry guide exactly", prompt)
        self.assertIn("with no visible top surface", prompt)
        self.assertIn("do not draw a separate top-edge line, highlight seam, or light coping strip", prompt)
        self.assertIn("no global vignette", prompt)
        self.assertIn("no directional lighting sweep", prompt)
        self.assertIn("cool dark stone", prompt)
        self.assertIn("no pale gray-beige stone drift", prompt)

    def test_slot_family_specs_no_longer_use_foreground_frame_for_shell_slots(self):
        self.assertEqual(envsys.V2_SLOT_SPEC_BY_TYPE["ceiling_band"]["template_component_type"], "ceiling_piece")
        self.assertEqual(envsys.V2_SLOT_SPEC_BY_TYPE["wall_module_left"]["template_component_type"], "wall_piece")
        self.assertEqual(envsys.V2_SLOT_SPEC_BY_TYPE["main_floor_top"]["template_component_type"], "primary_floor_piece")
        self.assertEqual(envsys.V2_SLOT_SPEC_BY_TYPE["room_shell_foreground"]["template_component_type"], "foreground_frame")
        self.assertEqual(envv3.TEMPLATE_COMPONENT_BY_SLOT["ceiling_band"], "ceiling_piece")
        self.assertEqual(envv3.TEMPLATE_COMPONENT_BY_SLOT["wall_module_left"], "wall_piece")
        self.assertEqual(envv3.TEMPLATE_COMPONENT_BY_SLOT["main_floor_face"], "primary_floor_piece")
        self.assertEqual(envv3.TEMPLATE_COMPONENT_BY_SLOT["room_shell_foreground"], "foreground_frame")

    def test_validate_wall_piece_source_rejects_recess_read(self):
        path = self.root / "wall-piece-bad.png"
        img = envsys.Image.new("RGBA", (512, 1200), (68, 76, 84, 255))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((170, 260, 342, 1080), fill=(10, 12, 16, 255))
        img.save(path)
        valid, errors = envsys._validate_wall_piece_source(path)
        self.assertFalse(valid)
        self.assertIn("wall_piece_opening_or_recess_read", errors)

    def test_validate_primary_floor_piece_source_rejects_top_plane_perspective(self):
        path = self.root / "floor-piece-bad.png"
        img = envsys.Image.new("RGBA", (512, 96), (40, 46, 54, 255))
        draw = envsys.ImageDraw.Draw(img)
        draw.polygon([(0, 0), (512, 0), (420, 34), (92, 34)], fill=(200, 210, 220, 255))
        draw.rectangle((0, 34, 512, 96), fill=(28, 32, 38, 255))
        img.save(path)
        valid, errors = envsys._validate_primary_floor_piece_source(path)
        self.assertFalse(valid)
        self.assertIn("primary_floor_piece_top_plane_perspective", errors)

    def test_validate_ceiling_piece_source_rejects_placeholder_header_read(self):
        path = self.root / "ceiling-piece-bad.png"
        img = envsys.Image.new("RGBA", (1600, 224), (34, 40, 46, 255))
        draw = envsys.ImageDraw.Draw(img)
        draw.rectangle((0, 0, 1600, 48), fill=(26, 32, 38, 255))
        draw.rectangle((0, 48, 1600, 224), fill=(30, 36, 42, 255))
        img.save(path)
        valid, errors = envsys._validate_ceiling_piece_source(path)
        self.assertFalse(valid)
        self.assertIn("ceiling_piece_placeholder_header_read", errors)

    def test_validate_structural_family_rejects_palette_drift(self):
        biome_root = self.root / "art_direction_biomes" / "ruined-gothic-v1"
        biome_root.mkdir(parents=True, exist_ok=True)
        envsys.Image.new("RGBA", (512, 1200), (20, 26, 32, 255)).save(biome_root / "wall_piece.png")
        envsys.Image.new("RGBA", (1600, 224), (160, 150, 120, 255)).save(biome_root / "ceiling_piece.png")
        envsys.Image.new("RGBA", (512, 96), (18, 24, 30, 255)).save(biome_root / "primary_floor_piece.png")
        errors = envsys._validate_structural_family({
            "wall_piece": biome_root / "wall_piece.png",
            "ceiling_piece": biome_root / "ceiling_piece.png",
            "primary_floor_piece": biome_root / "primary_floor_piece.png",
        })
        self.assertIn("structural_family_palette_drift", errors)

    def test_runtime_review_requires_browser_capture(self):
        review_path = self.projects_root / self.project_id / "room_environment_assets" / "R1" / "review" / "runtime-review.png"
        review_path.parent.mkdir(parents=True, exist_ok=True)
        envsys.Image.new("RGBA", (1600, 1200), (32, 40, 48, 255)).save(review_path)
        with mock.patch.object(envsys, "_capture_runtime_review_screenshot", return_value=("composite_fallback", "headless_browser_disabled_by_default")):
            review = envsys._run_runtime_review(self.saved, self.project_id, "R1", {})
        self.assertEqual(review["status"], "fail")
        self.assertIn("browser_capture_required", review["fail_reasons"])

    def test_foreground_frame_retry_prompt_targets_band_distinction(self):
        retry = envsys._retry_prompt_for_validation_errors(
            "foreground_frame",
            "base prompt",
            ["top_band_not_distinct_from_center", "bottom_band_not_distinct_from_center"],
            0,
        )
        self.assertIsNotNone(retry)
        self.assertIn("unmistakable horizontal masonry strips", retry)
        self.assertIn("Do not let them dissolve into the same foggy blue-gray field as the center", retry)

    def test_border_first_biome_prompts_are_generic_templates_not_final_rooms(self):
        direction = {
            "high_level_direction": "Ruined gothic castle shell",
            "negative_direction": "",
            "lighting_rules": ["single focal glow", "fog depth near floor"],
        }
        border_prompt = envsys._build_biome_template_prompt("border_piece", direction, "")
        far_prompt = envsys._build_biome_template_prompt("background_far_piece", direction, "")
        platform_prompt = envsys._build_biome_template_prompt("platform_piece", direction, "")

        self.assertIn("not a room scene", border_prompt)
        self.assertIn("fills the full 1600x1200 canvas", border_prompt)
        self.assertIn("Use the full occupied area shown in the guide", border_prompt)
        self.assertIn("Anti-designs", border_prompt)
        self.assertIn("constant horizontal position", border_prompt)
        self.assertIn("square ninety-degree corners", border_prompt)
        self.assertIn("torn plaster breach", border_prompt)
        self.assertIn("not columns or posts", border_prompt)
        self.assertIn("not a lintel", border_prompt)
        self.assertIn("not a sill or threshold", border_prompt)
        self.assertIn("Material-language contract", border_prompt)
        self.assertIn("DOUBLE-thick enclosing read", border_prompt)
        self.assertIn("Do not paint cyan, teal, aqua, or electric-blue rim lines", border_prompt)
        self.assertIn("cyan, teal, or aqua accent rim", border_prompt)
        self.assertIn("not a final room scene", far_prompt)
        self.assertIn("Do not compose a hero shot", far_prompt)
        self.assertIn("white matte bars", far_prompt)
        self.assertIn("reusable side-view platform source", platform_prompt)
        self.assertIn("no glowing trim", platform_prompt)
        self.assertIn("no background, no ruins behind it", platform_prompt)
        self.assertIn("Keep the left and right wall bands perfectly straight", border_prompt)
        self.assertIn("simple heavy stone strip", border_prompt)

    def test_border_first_retry_prompts_tighten_geometry_and_genericity(self):
        border_retry = envsys._retry_prompt_for_validation_errors(
            "border_piece",
            "base prompt",
            ["border_piece_top_band_too_ornate"],
            0,
        )
        far_retry = envsys._retry_prompt_for_validation_errors(
            "background_far_piece",
            "base prompt",
            ["background_far_piece_center_too_composed"],
            0,
        )
        platform_retry = envsys._retry_prompt_for_validation_errors(
            "platform_piece",
            "base prompt",
            ["platform_piece_top_highlight_too_warm"],
            0,
        )

        self.assertIn("generic border template only", border_retry)
        self.assertIn("plain flat border is preferred", border_retry)
        self.assertIn("Do not depict columns, posts, lintels, sills, thresholds", border_retry)
        flare_retry = envsys._retry_prompt_for_validation_errors(
            "border_piece",
            "base prompt",
            ["border_piece_side_wall_flare"],
            0,
        )
        breach_retry = envsys._retry_prompt_for_validation_errors(
            "border_piece",
            "base prompt",
            ["border_piece_center_breach_read"],
            0,
        )
        self.assertIn("constant vertical line", flare_retry)
        self.assertIn("square top and bottom corners", flare_retry)
        self.assertIn("remove the torn-hole center", breach_retry)
        self.assertIn("jagged breach edges", breach_retry)
        thickness_retry = envsys._retry_prompt_for_validation_errors(
            "border_piece",
            "base prompt",
            ["border_piece_side_thickness_thin"],
            0,
        )
        texture_retry = envsys._retry_prompt_for_validation_errors(
            "border_piece",
            "base prompt",
            ["border_piece_texture_family_drift"],
            0,
        )
        self.assertIn("double the apparent frame mass", thickness_retry)
        self.assertIn("one consistent masonry language", texture_retry)
        self.assertIn("Remove bridges, statues, stairs", far_retry)
        self.assertIn("Remove glow lines, gold trim", platform_retry)
        self.assertIn("Do not show any background", platform_retry)

    def test_room_shell_retry_prompts_address_ceiling_and_corner_composite_read(self):
        ceiling_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_ceiling_composite_read"],
            0,
        )
        corner_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_corner_join_seam_read"],
            0,
        )
        shadow_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_corner_shadow_pool"],
            0,
        )
        detail_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_detail_scale_too_coarse"],
            0,
        )
        edge_gap_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_top_edge_gap_post"],
            0,
        )
        corner_gap_retry = envsys._retry_prompt_for_validation_errors(
            "room_shell_foreground",
            "base prompt",
            ["shell_corner_gap_pre"],
            0,
        )
        self.assertIn("continuous carved slab", ceiling_retry)
        self.assertIn("fused masonry corner", corner_retry)
        self.assertIn("remove heavy corner vignette shading", shadow_retry)
        self.assertIn("reduce block scale", detail_retry)
        self.assertIn("fill the top ledge continuously", edge_gap_retry)
        self.assertIn("fill all border corners", corner_gap_retry)

    def test_validate_border_piece_source_fails_side_wall_flare(self):
        path = self.root / "border-piece-side-flare.png"
        img = envsys.Image.new("RGBA", (1600, 1200), (32, 36, 44, 255))
        draw = envsys.ImageDraw.Draw(img)
        top = envsys.BORDER_PIECE_BORDER_TOP_PX
        bot = envsys.BORDER_PIECE_BORDER_BOTTOM_PX
        side = envsys.BORDER_PIECE_BORDER_SIDE_PX
        draw.rectangle((0, 0, 1600, top), fill=(48, 56, 64, 255))
        draw.rectangle((0, 1200 - bot, 1600, 1200), fill=(48, 56, 64, 255))
        draw.rectangle((0, top, side, 1200 - bot), fill=(52, 60, 70, 255))
        draw.rectangle((1600 - side, top, 1600, 1200 - bot), fill=(52, 60, 70, 255))
        draw.rectangle((0, top + 8, side + 40, top + 148), fill=(112, 124, 136, 255))
        draw.rectangle((0, 840, side + 40, 1010), fill=(112, 124, 136, 255))
        draw.rectangle((1340, top + 8, 1600, top + 148), fill=(112, 124, 136, 255))
        draw.rectangle((1340, 840, 1600, 1010), fill=(112, 124, 136, 255))
        img.save(path)
        valid, errors = envsys._validate_border_piece_source(path)
        self.assertFalse(valid)
        self.assertIn("border_piece_side_wall_flare", errors)


if __name__ == "__main__":
    unittest.main()
