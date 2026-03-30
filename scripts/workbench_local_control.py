"""
Shared helpers for Agent OS dashboard data and workbench process start/stop.
Used by os_dashboard_supervisor.py and sprite_workbench_server.py (GET /api/dashboard-data only).
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"
USAGE_LEDGER_REL = Path("projects-data") / "_usage_ledger.json"
PID_FILE = Path("/tmp/sprite_workbench_server.pid")
LOG_FILE = Path("/tmp/sprite_workbench_server.log")
SERVER_SCRIPT = REPO_ROOT / "scripts" / "sprite_workbench_server.py"


def parse_env_local(path: Path) -> dict[str, str]:
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


def merge_env_for_workbench() -> dict[str, str]:
    env = os.environ.copy()
    env.update({k: v for k, v in parse_env_local(ENV_FILE).items() if v})
    return env


def port_listening(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def workbench_health_ok(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def read_workbench_pid() -> int | None:
    try:
        if PID_FILE.is_file():
            return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pass
    return None


def keys_from_env(env: dict[str, str]) -> dict[str, bool]:
    def set_(k: str) -> bool:
        v = env.get(k, "").strip()
        return bool(v)

    return {
        "pixellab_key_set": set_("PIXELLAB_API_KEY"),
        "gemini_key_set": set_("GEMINI_API_KEY"),
        "resend_key_set": set_("RESEND_API_KEY"),
    }


def latest_daily_report_name() -> str | None:
    art = REPO_ROOT / "artifacts"
    if not art.is_dir():
        return None
    candidates = sorted(art.glob("daily-report-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name if candidates else None


def default_agent_os_control_base() -> str:
    return os.environ.get("AGENT_OS_CONTROL_BASE", "http://127.0.0.1:8769").strip().rstrip("/")


def read_repo_json_object(filename: str) -> dict[str, Any] | None:
    """Best-effort load of a JSON object from repo root (Agent OS status files)."""
    path = REPO_ROOT / filename
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _ledger_entries_from_repo_disk() -> list[dict[str, Any]]:
    path = REPO_ROOT / USAGE_LEDGER_REL
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return [e for e in raw.get("entries", []) if isinstance(e, dict)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _usage_charts_from_repo_disk() -> dict[str, Any]:
    """Read projects-data/_usage_ledger.json when workbench persistence is not configured (supervisor)."""
    from scripts.workbench_persistence import build_usage_ledger_charts_from_entries

    return build_usage_ledger_charts_from_entries(_ledger_entries_from_repo_disk())


def _usage_summary_from_repo_disk() -> dict[str, Any]:
    from scripts.workbench_persistence import summarize_usage_ledger_entries

    return summarize_usage_ledger_entries(_ledger_entries_from_repo_disk())


def build_workbench_server_dashboard_payload(bind_host: str, bind_port: int) -> dict[str, Any]:
    """When the JSON is served from sprite_workbench_server (this process is the workbench)."""
    env = merge_env_for_workbench()
    keys = keys_from_env(env)
    display_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::", "") else bind_host
    if display_host.startswith("::ffff:"):
        display_host = display_host.split("::ffff:", 1)[-1]
    ctrl = default_agent_os_control_base()
    from scripts.workbench_persistence import summarize_usage_ledger, summarize_usage_ledger_charts

    try:
        usage_charts = summarize_usage_ledger_charts()
        usage_summary = summarize_usage_ledger()
    except Exception:
        usage_charts = _usage_charts_from_repo_disk()
        usage_summary = _usage_summary_from_repo_disk()
    analytics_status = read_repo_json_object("analytics-status.json")
    return {
        "supervisor": False,
        "agent_os_control_base": ctrl,
        "workbench_server_running": True,
        "workbench_port": bind_port,
        "workbench_host": display_host,
        "workbench_pid": os.getpid(),
        "last_daily_report": latest_daily_report_name(),
        "usage_charts": usage_charts,
        "usage_summary": usage_summary,
        "analytics_status": analytics_status,
        **keys,
    }


def build_supervisor_dashboard_payload(host: str, wb_port: int) -> dict[str, Any]:
    env = merge_env_for_workbench()
    keys = keys_from_env(env)
    running = workbench_health_ok(host, wb_port)
    pid = read_workbench_pid() if running else None
    usage_charts = _usage_charts_from_repo_disk()
    usage_summary = _usage_summary_from_repo_disk()
    analytics_status = read_repo_json_object("analytics-status.json")
    return {
        "supervisor": True,
        "workbench_server_running": running,
        "workbench_port": wb_port,
        "workbench_host": host,
        "workbench_pid": pid,
        "last_daily_report": latest_daily_report_name(),
        "usage_charts": usage_charts,
        "usage_summary": usage_summary,
        "analytics_status": analytics_status,
        **keys,
    }


def start_workbench(host: str, wb_port: int) -> tuple[bool, str]:
    if workbench_health_ok(host, wb_port):
        return True, "Already running"
    if port_listening(host, wb_port):
        return False, f"Port {wb_port} is in use but /api/health did not respond"
    env = merge_env_for_workbench()
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
        if workbench_health_ok(host, wb_port):
            return True, f"Started (PID {proc.pid})"
        if proc.poll() is not None:
            return False, "Server exited before health check; see /tmp/sprite_workbench_server.log"
        time.sleep(1)
    return False, "Timeout waiting for /api/health"


def stop_workbench(host: str, wb_port: int) -> tuple[bool, str]:
    pid = read_workbench_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as e:
            return False, str(e)
    for _ in range(30):
        if not port_listening(host, wb_port) and not workbench_health_ok(host, wb_port):
            break
        time.sleep(0.2)
    else:
        return False, "Workbench port still listening after SIGTERM"
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return True, "Stopped"


def restart_workbench(host: str, wb_port: int) -> tuple[bool, str]:
    stop_workbench(host, wb_port)
    time.sleep(0.5)
    return start_workbench(host, wb_port)
