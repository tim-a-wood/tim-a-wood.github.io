"""
Shared Environment Copilot (Gemini) for room-layout-editor.html.

Served by `sprite_workbench_server.py` (`GET /api/ping`, `POST /api/copilot`) on the same origin as `room-layout-editor.html`.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENV_LOCAL_PATH = ROOT / ".env.local"

COPILOT_THEME_IDS = frozenset(
    {"cave", "ruins", "forest", "shrine", "sewer", "void", "custom"}
)

COPILOT_SYSTEM_PROMPT = """You are an assistant for a dark fantasy metroidvania level authoring tool.
The user describes a room's atmosphere in plain language.
Respond with ONLY valid JSON (no markdown fences, no commentary), exactly this shape:
{"themeId":"<one of: cave, ruins, forest, shrine, sewer, void, custom>","tags":["tag1","tag2"],"rationale":"<one short sentence>"}
Rules:
- themeId must be exactly one of the listed strings.
- tags: 3 to 8 short lowercase tokens (hyphens allowed), mood and atmosphere keywords.
- If no preset theme fits well, use "custom" and put detail in tags.
- rationale: one sentence explaining the choice."""


def load_env_local() -> None:
    """Populate os.environ from .env.local if present (does not override existing vars)."""
    if not ENV_LOCAL_PATH.is_file():
        return
    try:
        for line in ENV_LOCAL_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        pass


def gemini_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def normalize_copilot_payload(obj: dict) -> dict:
    raw_theme = str(obj.get("themeId", "")).strip().lower()
    theme_id = raw_theme if raw_theme in COPILOT_THEME_IDS else "custom"
    tags_raw = obj.get("tags")
    tags: list[str] = []
    if isinstance(tags_raw, list):
        tags = [str(t).strip().lower() for t in tags_raw if str(t).strip()][:16]
    rationale = str(obj.get("rationale", "")).strip()
    return {"themeId": theme_id, "tags": tags, "rationale": rationale}


def extract_gemini_json_text(data: dict) -> str:
    cands = data.get("candidates") or []
    if not cands:
        raise ValueError("Gemini returned no candidates")
    parts = (cands[0].get("content") or {}).get("parts") or []
    if not parts:
        raise ValueError("Gemini returned empty content")
    text = parts[0].get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned no text")
    return text.strip()


def strip_json_fences(raw: str) -> str:
    s = raw.strip()
    if not s.startswith("```"):
        return s
    lines = s.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def call_gemini_copilot(user_prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": COPILOT_SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.35,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:800]}") from exc

    text = extract_gemini_json_text(raw)
    try:
        parsed = json.loads(strip_json_fences(text))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini JSON parse error: {e}; snippet: {text[:400]}") from e
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini returned a non-object JSON root")
    return normalize_copilot_payload(parsed)


def copilot_ping_payload() -> dict:
    return {
        "ok": True,
        "root": str(ROOT),
        "copilot": {"geminiConfigured": gemini_configured()},
    }


def copilot_handle_post(body: dict) -> tuple[dict, int]:
    """
    Handle POST /api/copilot JSON body.
    Returns (response_object, http_status_code).
    """
    if not gemini_configured():
        return (
            {
                "ok": False,
                "error": "GEMINI_API_KEY is not set. Add it to .env.local in the project root.",
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return {"ok": False, "error": "Missing prompt"}, HTTPStatus.BAD_REQUEST
    room_name = str(body.get("roomName", "") or "").strip()
    room_id = str(body.get("roomId", "") or "").strip()
    lines: list[str] = []
    if room_name:
        lines.append(f"Room name: {room_name}")
    if room_id:
        lines.append(f"Room id: {room_id}")
    lines.append(f"Author description:\n{prompt}")
    user_block = "\n".join(lines)
    try:
        data = call_gemini_copilot(user_block)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY
    return {"ok": True, "data": data}, HTTPStatus.OK


load_env_local()
