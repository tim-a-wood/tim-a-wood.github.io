#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAYOUT_PATH = ROOT / "room-layout-data.json"
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

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
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


class LayoutEditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/ping":
            self._send_json(
                {
                    "ok": True,
                    "root": str(ROOT),
                    "copilot": {"geminiConfigured": gemini_configured()},
                }
            )
            return
        if self.path == "/api/layout":
            self._handle_get_layout()
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/layout":
            self._handle_save_layout()
            return
        if self.path == "/api/copilot":
            self._handle_copilot()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")

    def _handle_get_layout(self):
        try:
            data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
            self._send_json(data)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "room-layout-data.json not found")
        except json.JSONDecodeError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Invalid JSON: {exc}")

    def _handle_save_layout(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid content length")
            return

        try:
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("rooms"), list):
                self.send_error(HTTPStatus.BAD_REQUEST, "Payload must contain a rooms array")
                return
            LAYOUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            self._send_json({"ok": True, "path": str(LAYOUT_PATH)})
        except json.JSONDecodeError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
        except OSError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Write failed: {exc}")

    def _handle_copilot(self):
        if not gemini_configured():
            self._send_json(
                {
                    "ok": False,
                    "error": "GEMINI_API_KEY is not set. Add it to .env.local in the project root.",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"ok": False, "error": "Invalid content length"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json({"ok": False, "error": f"Invalid JSON: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._send_json({"ok": False, "error": "Body must be a JSON object"}, status=HTTPStatus.BAD_REQUEST)
            return
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self._send_json({"ok": False, "error": "Missing prompt"}, status=HTTPStatus.BAD_REQUEST)
            return
        room_name = str(payload.get("roomName", "") or "").strip()
        room_id = str(payload.get("roomId", "") or "").strip()
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
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"ok": True, "data": data})

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


load_env_local()


def main():
    parser = argparse.ArgumentParser(description="Local room layout editor server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LayoutEditorHandler)
    print(f"Layout editor server running at http://{args.host}:{args.port}/room-layout-editor.html")
    print(f"Canonical layout file: {LAYOUT_PATH}")
    if gemini_configured():
        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        print(f"Environment Copilot: Gemini enabled (model={model})")
    else:
        print("Environment Copilot: Gemini disabled (set GEMINI_API_KEY in .env.local)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
