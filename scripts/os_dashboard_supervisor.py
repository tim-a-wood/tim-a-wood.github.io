#!/usr/bin/env python3
"""
Local Agent OS dashboard: serves os-dashboard.html, GET /api/dashboard-data,
POST /api/workbench/{start|stop|restart}, POST /api/status-update, and
POST /api/issue-chat (OpenAI JSON chat for issue discussion in the UI).
Binds 127.0.0.1 only.

Issue chat: set OPENAI_API_KEY in the environment (optional ISSUE_CHAT_MODEL,
default gpt-4o-mini). Cursor IDE does not expose a browser-accessible chat API;
this server endpoint is the supported integration for Auto-style reasoning in
the dashboard.

Usage:
  python3 scripts/os_dashboard_supervisor.py
  OPENAI_API_KEY=... python3 scripts/os_dashboard_supervisor.py --port 8769 --workbench-port 8766

Open http://127.0.0.1:<port>/os-dashboard.html
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.workbench_local_control import (
    build_supervisor_dashboard_payload,
    restart_workbench,
    start_workbench,
    stop_workbench,
)

REPO_ROOT = _REPO_ROOT


def _issue_chat_call_openai(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    OpenAI Chat Completions with JSON output. Uses OPENAI_API_KEY (same key type many
    Cursor / local setups use for cloud models). Cursor IDE does not expose a public
    HTTP API from the browser; this server-side path is the supported integration.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "response_format": {"type": "json_object"},
        "temperature": 0.35,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {err_body[:800]}") from exc
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    outer = json.loads(raw)
    content = outer["choices"][0]["message"]["content"]
    return json.loads(content)


def _norm_path(handler: BaseHTTPRequestHandler) -> str:
    p = urlparse(handler.path).path
    p = unquote(p)
    p = p.rstrip("/")
    return p if p else "/"


def _normalize_workbench_post_path(path: str) -> str | None:
    if path.startswith("/api/os/workbench/"):
        path = "/api/workbench/" + path[len("/api/os/workbench/") :]
    if not path.startswith("/api/workbench/"):
        return None
    return path


def make_handler(
    *,
    repo_root: Path,
    workbench_host: str,
    workbench_port: int,
) -> type[BaseHTTPRequestHandler]:
    static_allow = frozenset(
        {
            "os-dashboard.html",
            "engineering-status.json",
            "design-status.json",
            "analytics-status.json",
            "marketing-status.json",
            "orchestration-status.json",
            "strategy-status.json",
            "qa-status.json",
            "game-director-status.json",
            "game-systems-status.json",
            "level-design-status.json",
            "workbench-po-status.json",
            "finance-status.json",
            "legal-status.json",
            "cybersecurity-status.json",
            "support-status.json",
            "animation-status.json",
            "narrative-status.json",
            "audio-status.json",
            "workbench-art-status.json",
            "ashen-hollow-art-status.json",
        }
    )
    # Files that can be written back via POST /api/status-update
    status_write_allow = frozenset(
        f for f in static_allow if f.endswith("-status.json")
    )

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

        def _send_json(self, status: int, obj: Any) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_GET(self) -> None:
            path = _norm_path(self)
            if path == "/api/workbench/status":
                pl = build_supervisor_dashboard_payload(workbench_host, workbench_port)
                return self._send_json(
                    HTTPStatus.OK,
                    {
                        "running": pl["workbench_server_running"],
                        "port": workbench_port,
                        "host": workbench_host,
                        "pid": pl.get("workbench_pid"),
                    },
                )
            if path == "/api/dashboard-data":
                return self._send_json(
                    HTTPStatus.OK,
                    build_supervisor_dashboard_payload(workbench_host, workbench_port),
                )

            rel = path.lstrip("/")
            if rel in static_allow:
                fpath = repo_root / rel
                try:
                    fpath.resolve().relative_to(repo_root.resolve())
                except ValueError:
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                if not fpath.is_file():
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                body = fpath.read_bytes()
                ctype = "application/json" if rel.endswith(".json") else "text/html; charset=utf-8"
                return self._send_bytes(HTTPStatus.OK, body, ctype)
            if path == "/" or path == "/os-dashboard.html":
                fpath = repo_root / "os-dashboard.html"
                if not fpath.is_file():
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "os-dashboard.html missing"})
                return self._send_bytes(
                    HTTPStatus.OK,
                    fpath.read_bytes(),
                    "text/html; charset=utf-8",
                )
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:
            raw_path = _norm_path(self)

            # ── Issue discussion chat (OpenAI-compatible JSON response) ─────
            if raw_path == "/api/issue-chat":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else b""
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
                messages = payload.get("messages")
                issue = payload.get("issue")
                agent_charter = payload.get("agentCharter") or ""
                agent_label = payload.get("agentLabel") or "Agent"
                if not isinstance(messages, list) or not messages:
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "messages required"})
                if not isinstance(issue, dict):
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "issue required"})

                api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
                if not api_key:
                    return self._send_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "error": "no_api_key",
                            "message": "Set OPENAI_API_KEY in the environment and restart the supervisor. "
                            "Cursor IDE does not expose a browser chat API; this endpoint uses the OpenAI API.",
                        },
                    )
                model = (os.environ.get("ISSUE_CHAT_MODEL") or "gpt-4o-mini").strip()

                allowed_files = ", ".join(sorted(status_write_allow))
                system_prompt = (
                    f"You are the {agent_label} specialist for the MV metroidvania toolchain (solo-founder OS).\n"
                    f"Charter reference path: {agent_charter or '(not provided)'}\n\n"
                    "The user is discussing ONE priority row from a dashboard status JSON file.\n"
                    "Current issue snapshot (JSON):\n"
                    f"{json.dumps(issue, ensure_ascii=False, indent=2)}\n\n"
                    "You may propose edits to this priority and, if the user explicitly agrees, to other priorities "
                    "in the same file or another allowed status file when logically necessary.\n\n"
                    "Respond with a single JSON object ONLY, keys:\n"
                    '- "thinking": string, your step-by-step reasoning (show your work).\n'
                    '- "assistant_message": string, concise reply to the user.\n'
                    '- "priority_updates": array of objects, each: '
                    '{"file": "<filename>", "id": <numeric priority id>, "fields": { ... partial fields ... }} '
                    "where fields may include title, status, risk, note, proposed_solution. "
                    "Use [] if no file changes are appropriate yet.\n\n"
                    f"Allowed file names for priority_updates: {allowed_files}\n"
                    "Do not invent file names. Status must be one of: "
                    "in-progress, needs-review, queued, paused, done. Risk: high, med, low."
                )

                try:
                    norm_messages: list[dict[str, Any]] = []
                    for m in messages:
                        if not isinstance(m, dict):
                            continue
                        role = m.get("role")
                        content = m.get("content")
                        if role in ("user", "assistant") and isinstance(content, str):
                            norm_messages.append({"role": role, "content": content})
                    if not norm_messages:
                        return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "no valid messages"})
                    result = _issue_chat_call_openai(
                        api_key=api_key,
                        model=model,
                        system_prompt=system_prompt,
                        messages=norm_messages,
                    )
                except (RuntimeError, KeyError, json.JSONDecodeError, TypeError) as exc:
                    return self._send_json(
                        HTTPStatus.BAD_GATEWAY,
                        {"error": "chat_failed", "message": str(exc)},
                    )
                return self._send_json(HTTPStatus.OK, {"ok": True, "result": result})

            # ── Status-file write-back ──────────────────────────────────────
            if raw_path == "/api/status-update":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else b""
                try:
                    payload = json.loads(body)
                    fname = payload.get("file", "")
                    data  = payload.get("data")
                except (json.JSONDecodeError, AttributeError):
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
                if not isinstance(fname, str) or fname not in status_write_allow:
                    return self._send_json(HTTPStatus.FORBIDDEN, {"error": "File not writable"})
                if not isinstance(data, dict):
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "data must be an object"})
                fpath = repo_root / fname
                try:
                    fpath.resolve().relative_to(repo_root.resolve())
                except ValueError:
                    return self._send_json(HTTPStatus.FORBIDDEN, {"error": "Path escape"})
                try:
                    fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                except OSError as exc:
                    return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return self._send_json(HTTPStatus.OK, {"ok": True, "file": fname})

            path = _normalize_workbench_post_path(raw_path)
            if path is None:
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            action = path[len("/api/workbench/") :].strip()
            if action == "start":
                ok, msg = start_workbench(workbench_host, workbench_port)
                return self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST, {"ok": ok, "message": msg})
            if action == "stop":
                ok, msg = stop_workbench(workbench_host, workbench_port)
                return self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST, {"ok": ok, "message": msg})
            if action == "restart":
                ok, msg = restart_workbench(workbench_host, workbench_port)
                return self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST, {"ok": ok, "message": msg})
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown action"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent OS dashboard + workbench supervisor")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8769, help="Supervisor HTTP port")
    parser.add_argument("--workbench-host", default="127.0.0.1", help="Workbench bind / health check host")
    parser.add_argument("--workbench-port", type=int, default=8766, help="Workbench port")
    args = parser.parse_args()

    handler = make_handler(
        repo_root=REPO_ROOT,
        workbench_host=args.workbench_host,
        workbench_port=args.workbench_port,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Agent OS at http://{args.host}:{args.port}/os-dashboard.html", file=sys.stderr)
    print(f"Workbench: http://{args.workbench_host}:{args.workbench_port}/ (Start/Stop from dashboard)", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
