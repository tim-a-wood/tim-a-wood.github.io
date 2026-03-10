#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAYOUT_PATH = ROOT / "room-layout-data.json"


class LayoutEditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/ping":
            self._send_json({"ok": True, "root": str(ROOT)})
            return
        if self.path == "/api/layout":
            self._handle_get_layout()
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/layout":
            self._handle_save_layout()
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

    def _send_json(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
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
    print(f"Canonical layout file: {LAYOUT_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
