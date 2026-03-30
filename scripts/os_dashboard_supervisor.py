#!/usr/bin/env python3
"""
Local Agent OS dashboard server: serves os-dashboard.html and optional JSON,
implements GET /api/dashboard-data, and authenticated workbench lifecycle APIs.

Bind 127.0.0.1 only by default. Set OS_DASHBOARD_SUPERVISOR_TOKEN in .env.local
for POST /api/os/workbench/* (start | stop | restart).

Usage:
  python3 scripts/os_dashboard_supervisor.py
  python3 scripts/os_dashboard_supervisor.py --port 8769 --workbench-port 8766

Open http://127.0.0.1:<port>/os-dashboard.html
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"
PID_FILE = Path("/tmp/sprite_workbench_server.pid")
LOG_FILE = Path("/tmp/sprite_workbench_server.log")
SERVER_SCRIPT = REPO_ROOT / "scripts" / "sprite_workbench_server.py"

TOKEN_HEADER = "X-OS-Dashboard-Token"


def _parse_env_local(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        out[key] = val
    return out


def _merge_env_for_workbench() -> dict[str, str]:
    env = os.environ.copy()
    env.update({k: v for k, v in _parse_env_local(ENV_FILE).items() if v})
    return env


def _port_listening(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _workbench_health_ok(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _read_pid() -> int | None:
    try:
        if PID_FILE.is_file():
            return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pass
    return None


def _keys_from_env(env: dict[str, str]) -> dict[str, bool]:
    def set_(k: str) -> bool:
        v = env.get(k, "").strip()
        return bool(v)

    return {
        "pixellab_key_set": set_("PIXELLAB_API_KEY"),
        "gemini_key_set": set_("GEMINI_API_KEY"),
        "resend_key_set": set_("RESEND_API_KEY"),
    }


def _latest_daily_report_name() -> str | None:
    art = REPO_ROOT / "artifacts"
    if not art.is_dir():
        return None
    candidates = sorted(art.glob("daily-report-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name if candidates else None


def build_dashboard_payload(host: str, wb_port: int) -> dict[str, Any]:
    env = _merge_env_for_workbench()
    keys = _keys_from_env(env)
    running = _workbench_health_ok(host, wb_port)
    pid = _read_pid() if running else None
    return {
        "supervisor": True,
        "workbench_server_running": running,
        "workbench_port": wb_port,
        "workbench_host": host,
        "workbench_pid": pid,
        "last_daily_report": _latest_daily_report_name(),
        **keys,
    }


def _start_workbench(host: str, wb_port: int) -> tuple[bool, str]:
    if _workbench_health_ok(host, wb_port):
        return True, "Already running"
    if _port_listening(host, wb_port):
        return False, f"Port {wb_port} is in use but /api/health did not respond"
    env = _merge_env_for_workbench()
    if not env.get("GEMINI_API_KEY", "").strip():
        return False, "GEMINI_API_KEY missing in environment (.env.local)"
    if not SERVER_SCRIPT.is_file():
        return False, f"Missing {SERVER_SCRIPT}"
    python = sys.executable
    cmd = [python, str(SERVER_SCRIPT), "--host", host, "--port", str(wb_port)]
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_f = open(LOG_FILE, "ab")
    except OSError as e:
        return False, f"Cannot open log file: {e}"
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=log_f,
            env=env,
            cwd=str(REPO_ROOT),
            start_new_session=True,
            close_fds=True,
        )
    except OSError as e:
        log_f.close()
        return False, str(e)
    log_f.close()
    try:
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except OSError:
        pass
    for _ in range(30):
        if _workbench_health_ok(host, wb_port):
            return True, f"Started (PID {proc.pid})"
        if proc.poll() is not None:
            return False, "Server exited before health check; see /tmp/sprite_workbench_server.log"
        time.sleep(1)
    return False, "Timeout waiting for /api/health"


def _stop_workbench(host: str, wb_port: int) -> tuple[bool, str]:
    pid = _read_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as e:
            return False, str(e)
    for _ in range(30):
        if not _port_listening(host, wb_port) and not _workbench_health_ok(host, wb_port):
            break
        time.sleep(0.2)
    else:
        return False, "Workbench port still listening after SIGTERM"
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return True, "Stopped"


def make_handler(
    *,
    repo_root: Path,
    workbench_host: str,
    workbench_port: int,
    supervisor_token: str | None,
) -> type[BaseHTTPRequestHandler]:
    static_allow = frozenset(
        {
            "os-dashboard.html",
            "engineering-status.json",
            "design-status.json",
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
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Any:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None

        def _check_token(self) -> bool:
            if not supervisor_token:
                return False
            got = self.headers.get(TOKEN_HEADER, "").strip()
            return bool(got) and got == supervisor_token

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", f"Content-Type, {TOKEN_HEADER}")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path == "/api/os/supervisor-config":
                return self._send_json(
                    HTTPStatus.OK,
                    {
                        "supervisor": True,
                        "workbench_port": workbench_port,
                        "workbench_host": workbench_host,
                        "token_configured": bool(supervisor_token),
                    },
                )
            if path == "/api/os/workbench/status":
                pl = build_dashboard_payload(workbench_host, workbench_port)
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
                return self._send_json(HTTPStatus.OK, build_dashboard_payload(workbench_host, workbench_port))

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
            path = self.path.split("?", 1)[0].rstrip("/")
            if not path.startswith("/api/os/workbench/"):
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            if not self._check_token():
                return self._send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": f"Missing or invalid {TOKEN_HEADER} (set OS_DASHBOARD_SUPERVISOR_TOKEN in .env.local)"},
                )
            action = path.removeprefix("/api/os/workbench/").strip()
            if action == "start":
                ok, msg = _start_workbench(workbench_host, workbench_port)
                return self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST, {"ok": ok, "message": msg})
            if action == "stop":
                ok, msg = _stop_workbench(workbench_host, workbench_port)
                return self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST, {"ok": ok, "message": msg})
            if action == "restart":
                _stop_workbench(workbench_host, workbench_port)
                time.sleep(0.5)
                ok, msg = _start_workbench(workbench_host, workbench_port)
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

    env_local = _parse_env_local(ENV_FILE)
    token = (os.environ.get("OS_DASHBOARD_SUPERVISOR_TOKEN") or env_local.get("OS_DASHBOARD_SUPERVISOR_TOKEN") or "").strip() or None

    handler = make_handler(
        repo_root=REPO_ROOT,
        workbench_host=args.workbench_host,
        workbench_port=args.workbench_port,
        supervisor_token=token,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Agent OS supervisor at http://{args.host}:{args.port}/os-dashboard.html", file=sys.stderr)
    print(f"Workbench expected at http://{args.workbench_host}:{args.workbench_port}/", file=sys.stderr)
    if token:
        print("POST controls require X-OS-Dashboard-Token (set in dashboard session).", file=sys.stderr)
    else:
        print("Warning: OS_DASHBOARD_SUPERVISOR_TOKEN not set — start/stop/restart disabled.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
