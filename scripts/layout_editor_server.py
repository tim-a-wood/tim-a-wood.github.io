#!/usr/bin/env python3
"""
Optional lightweight HTTP server: repo static files + canonical room layout + Copilot APIs.

For day-to-day use, prefer `sprite_workbench_server.py` (same routes + workbench + projects).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.room_layout_canonical import CANONICAL_LAYOUT_PATH, read_canonical_layout, save_canonical_layout
from scripts.room_layout_copilot import copilot_handle_post, copilot_ping_payload, gemini_configured


class LayoutEditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/ping":
            self._send_json(copilot_ping_payload())
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
            self._send_json(read_canonical_layout())
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
            if not isinstance(payload, dict):
                self.send_error(HTTPStatus.BAD_REQUEST, "Body must be a JSON object")
                return
            self._send_json(save_canonical_layout(payload))
        except json.JSONDecodeError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except OSError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Write failed: {exc}")

    def _handle_copilot(self):
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
        out, status = copilot_handle_post(payload)
        self._send_json(out, status=status)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Local room layout editor server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LayoutEditorHandler)
    print(f"Layout editor server running at http://{args.host}:{args.port}/room-layout-editor.html")
    print(f"Canonical layout file: {CANONICAL_LAYOUT_PATH}")
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
