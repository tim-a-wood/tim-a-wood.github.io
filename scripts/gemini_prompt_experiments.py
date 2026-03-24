import io
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path("/Users/timwood/Desktop/projects/PWA/MV")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from google import genai
from google.genai import types

from scripts import sprite_workbench_server as sw

OUTPUT_ROOT = ROOT / "tmp" / "gemini_prompt_experiments"
MODEL = sw.GEMINI_IMAGE_MODEL
SEND_SIZE = sw._GEMINI_SEND_SIZE


@dataclass
class Scenario:
    scenario_id: str
    source_path: Path
    brief: Dict[str, str]
    element: str
    change_text: str


def variant_current_requirements(brief: Dict[str, str], element: str, change_text: str) -> str:
    return sw._build_gemini_requirements_prompt(brief, element, change_text)


def variant_concise_outcome(brief: Dict[str, str], element: str, change_text: str) -> str:
    contract = sw._iteration_element_contract_with_request(element, change_text)
    description = str(brief.get("raw_prompt") or "pixel art character").strip()
    return "\n".join([
        "Edit this existing pixel-art sprite.",
        f"Keep the same character: {description}.",
        f"Requested result: {change_text}.",
        f"Only change: {contract['label']}.",
        "Keep the same identity, costume, gear, pixel-art style, and transparent background.",
        "Preserve all other pixels whenever possible.",
        "Return the full sprite as a strict side view.",
    ])


def variant_acceptance_criteria(brief: Dict[str, str], element: str, change_text: str) -> str:
    contract = sw._iteration_element_contract_with_request(element, change_text)
    return "\n".join([
        "Edit this sprite so it passes these acceptance criteria:",
        f"1. Requested change is applied: {change_text}.",
        f"2. Only this aspect changes: {contract['label']}.",
        f"3. Locked attributes stay the same: {', '.join(contract['locked'])}.",
        "4. The result stays pixel art and keeps a transparent background.",
        "5. The full image is returned and still reads as a strict side view.",
        "Fail by changing too little rather than by redesigning the sprite.",
    ])


def variant_identity_locked(brief: Dict[str, str], element: str, change_text: str) -> str:
    correcting_view = sw._is_side_view_correction_request(element, change_text)
    return "\n".join([
        "Use the input image as the source of truth for character identity.",
        f"Apply this single change: {change_text}.",
        "Do not redesign the character.",
        "Do not add new objects, shadows, halos, or background elements.",
        "Keep the same armor, prop family, palette intent, and pixel-art rendering style.",
        "Return a transparent full sprite.",
        "The final image must read as a strict side view." if correcting_view else "Do not change the viewing angle away from strict side view.",
    ])


PROMPT_VARIANTS: Dict[str, Callable[[Dict[str, str], str, str], str]] = {
    "current_requirements": variant_current_requirements,
    "concise_outcome": variant_concise_outcome,
    "acceptance_criteria": variant_acceptance_criteria,
    "identity_locked": variant_identity_locked,
}


def default_scenarios() -> List[Scenario]:
    hero = ROOT / "tools/2d-sprite-and-animation/projects-data/hero-knight-91c47779/concepts/concept-0006.png"
    ranger = ROOT / "tools/2d-sprite-and-animation/projects-data/test-player-0db89e30/concepts/concept-0002-processed.png"
    hero_brief = {
        "raw_prompt": "hero knight side-view armored fighter with sword and shield",
        "role_archetype": "ashen hollow knight",
        "silhouette_intent": "broad guarded profile",
        "outfit_materials": "weathered plate armor over dark cloth",
        "prop": "sword and shield",
        "palette_mood": "storm steel",
        "shape_language": "angular disciplined silhouettes",
        "mood_tone": "grim and vigilant",
    }
    ranger_brief = {
        "raw_prompt": "side-view ranger with lantern and layered travel gear",
        "role_archetype": "ashen hollow ranger",
        "silhouette_intent": "lean alert profile",
        "outfit_materials": "layered cloth and leather travel gear",
        "prop": "lantern",
        "palette_mood": "storm steel",
        "shape_language": "balanced angular to rounded mix",
        "mood_tone": "watchful and haunted",
    }
    return [
        Scenario("hero_expression", hero, hero_brief, "expression", "make the eye slit slightly brighter and clearer"),
        Scenario("hero_pose_guarded", hero, hero_brief, "pose", "raise the front arm a little into a more guarded stance"),
        Scenario("hero_side_correction", hero, hero_brief, "pose", "change the pose to a strict side view"),
        Scenario("ranger_outfit", ranger, ranger_brief, "outfit", "add a slightly longer tattered cloth tabard"),
    ]


def prepare_source_subject(image: Image.Image) -> Dict[str, Image.Image]:
    source_mask = sw.largest_component_mask(sw.detect_mask(image))
    source_subject = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_subject.alpha_composite(image)
    source_subject.putalpha(source_mask)
    return {"source_mask": source_mask, "source_subject": source_subject}


def run_variant(
    client: genai.Client,
    scenario: Scenario,
    variant_name: str,
    prompt_builder: Callable[[Dict[str, str], str, str], str],
    run_dir: Path,
) -> Dict[str, object]:
    source = Image.open(scenario.source_path).convert("RGBA")
    prepared = prepare_source_subject(source)
    source_subject = prepared["source_subject"]
    source_mask = prepared["source_mask"]

    prompt = prompt_builder(scenario.brief, scenario.element, scenario.change_text)
    send_img = source_subject.resize((SEND_SIZE, SEND_SIZE), resample=Image.Resampling.NEAREST)
    send_buf = io.BytesIO()
    send_img.save(send_buf, format="PNG")

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=send_buf.getvalue(), mime_type="image/png"),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    result_img: Optional[Image.Image] = None
    response_text = ""
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            result_img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")
        elif getattr(part, "text", None):
            response_text += str(part.text)
    if result_img is None:
        return {
            "scenario_id": scenario.scenario_id,
            "variant": variant_name,
            "status": "error",
            "error": "no image returned",
            "response_text": response_text,
        }

    result_img = result_img.resize(source.size, resample=Image.Resampling.NEAREST)
    edit_mask = sw._element_edit_mask_for_size(scenario.element, result_img.size)
    result_img = Image.composite(result_img, source_subject, edit_mask)
    protected_mask = sw._protected_source_mask_for_element(scenario.element, result_img.size, scenario.change_text)
    result_img = Image.composite(source_subject, result_img, protected_mask)
    result_mask = sw.largest_component_mask(sw.detect_mask(result_img))
    if sw._is_side_view_correction_request(scenario.element, scenario.change_text):
        final_mask = Image.composite(result_mask, source_mask, edit_mask)
    else:
        final_mask = source_mask
    result_img.putalpha(final_mask)

    evaluation = sw.evaluate_gemini_iteration_result(
        source_subject,
        result_img,
        scenario.element,
        scenario.change_text,
    )

    image_name = f"{scenario.scenario_id}__{variant_name}.png"
    result_path = run_dir / image_name
    result_img.save(result_path)

    return {
        "scenario_id": scenario.scenario_id,
        "variant": variant_name,
        "status": evaluation["status"],
        "reason": evaluation.get("reason"),
        "metrics": evaluation,
        "output_path": str(result_path),
        "prompt": prompt,
        "response_text": response_text,
    }


def summarize(results: List[Dict[str, object]]) -> Dict[str, object]:
    by_variant: Dict[str, Dict[str, object]] = {}
    for row in results:
        variant = str(row["variant"])
        summary = by_variant.setdefault(variant, {"passes": 0, "fails": 0, "errors": 0, "scenarios": []})
        status = row["status"]
        if status == "pass":
            summary["passes"] += 1
        elif status == "fail":
            summary["fails"] += 1
        else:
            summary["errors"] += 1
        summary["scenarios"].append({
            "scenario_id": row["scenario_id"],
            "status": status,
            "reason": row.get("reason"),
            "output_path": row.get("output_path"),
        })
    ranked = sorted(
        by_variant.items(),
        key=lambda item: (-int(item[1]["passes"]), int(item[1]["fails"]), int(item[1]["errors"])),
    )
    return {"variants": by_variant, "ranking": [name for name, _ in ranked]}


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required.")

    client = genai.Client(api_key=api_key)
    scenarios = default_scenarios()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = OUTPUT_ROOT / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, object]] = []
    for scenario in scenarios:
        for variant_name, prompt_builder in PROMPT_VARIANTS.items():
            print(f"running {scenario.scenario_id} :: {variant_name}", flush=True)
            row = run_variant(client, scenario, variant_name, prompt_builder, run_dir)
            results.append(row)

    summary = summarize(results)
    payload = {
        "model": MODEL,
        "scenarios": [scenario.__dict__ | {"source_path": str(scenario.source_path)} for scenario in scenarios],
        "results": results,
        "summary": summary,
    }
    out_path = run_dir / "results.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"results_path": str(out_path), "ranking": summary["ranking"]}, indent=2))


if __name__ == "__main__":
    main()
