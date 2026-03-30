#!/usr/bin/env python3
"""
Local Agent OS dashboard: serves os-dashboard.html, GET /api/dashboard-data,
and POST /api/workbench/{start|stop|restart} (binds 127.0.0.1 only).

Usage:
  python3 scripts/os_dashboard_supervisor.py
  python3 scripts/os_dashboard_supervisor.py --port 8769 --workbench-port 8766

Open http://127.0.0.1:<port>/os-dashboard.html
"""
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
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
        }
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
            path = _normalize_workbench_post_path(_norm_path(self))
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
