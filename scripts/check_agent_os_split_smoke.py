#!/usr/bin/env python3
"""Bootstrap and smoke-test a standalone Agent OS checkout against an MV workspace."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from scripts.bootstrap_agent_os_repo import main as bootstrap_main


REQUIRED_DASHBOARD_KEYS = (
    "supervisor",
    "workbench_server_running",
    "workbench_port",
    "workbench_host",
    "usage_charts",
    "usage_summary",
    "home_internal",
)


def _fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _wait_for_dashboard(url: str, timeout_sec: float) -> dict[str, Any] | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        payload = _fetch_json(url)
        if payload is not None:
            return payload
        time.sleep(0.25)
    return None


def _run_bootstrap(destination: Path) -> None:
    old_argv = sys.argv[:]
    try:
        sys.argv = ["bootstrap_agent_os_repo.py", str(destination)]
        rc = bootstrap_main()
    finally:
        sys.argv = old_argv
    if rc != 0:
        raise RuntimeError(f"bootstrap_agent_os_repo.py exited {rc}")


def _validate_payload(payload: dict[str, Any], expected_workbench_port: int) -> None:
    missing = [key for key in REQUIRED_DASHBOARD_KEYS if key not in payload]
    if missing:
        raise RuntimeError(f"dashboard payload missing keys: {missing}")
    if payload.get("supervisor") is not True:
        raise RuntimeError("dashboard payload did not come from supervisor mode")
    if payload.get("workbench_port") != expected_workbench_port:
        raise RuntimeError(
            f"unexpected workbench_port {payload.get('workbench_port')!r}; expected {expected_workbench_port!r}"
        )
    home = payload.get("home_internal")
    if not isinstance(home, dict) or "release_gate_label" not in home:
        raise RuntimeError("home_internal payload shape invalid")


def main() -> int:
    ap = argparse.ArgumentParser(description="Bootstrap and smoke-test a standalone Agent OS checkout.")
    ap.add_argument("--workspace-root", type=Path, default=APP_ROOT, help="MV workspace root to target")
    ap.add_argument("--supervisor-port", type=int, default=8779, help="Alternate Agent OS supervisor port")
    ap.add_argument("--workbench-port", type=int, default=8766, help="Expected MV workbench port")
    ap.add_argument("--timeout", type=float, default=20.0, help="Seconds to wait for supervisor startup")
    args = ap.parse_args()

    workspace_root = args.workspace_root.expanduser().resolve()
    if not workspace_root.is_dir():
        raise SystemExit(f"Workspace root missing: {workspace_root}")

    with tempfile.TemporaryDirectory(prefix="agent-os-split-smoke-") as td:
        external_root = Path(td) / "agent-os"
        _run_bootstrap(external_root)

        log_path = Path(td) / "agent-os-smoke.log"
        env = os.environ.copy()
        env["AGENT_OS_APP_ROOT"] = str(external_root)
        env["MV_WORKSPACE_ROOT"] = str(workspace_root)
        env["OS_AGENT_OS_PORT"] = str(args.supervisor_port)
        env["OS_DASHBOARD_WORKBENCH_PORT"] = str(args.workbench_port)

        with log_path.open("ab") as logf:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(external_root / "scripts" / "os_dashboard_supervisor.py"),
                    "--port",
                    str(args.supervisor_port),
                    "--workbench-port",
                    str(args.workbench_port),
                ],
                cwd=str(external_root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=logf,
                stderr=logf,
                start_new_session=True,
                close_fds=True,
            )

        url = f"http://127.0.0.1:{args.supervisor_port}/api/dashboard-data"
        try:
            payload = _wait_for_dashboard(url, args.timeout)
            if payload is None:
                log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
                raise RuntimeError(
                    f"dashboard did not become ready at {url} within {args.timeout}s\n"
                    f"--- supervisor log ---\n{log_text[-4000:]}"
                )
            _validate_payload(payload, args.workbench_port)
            print(json.dumps({"ok": True, "external_root": str(external_root), "url": url}, indent=2))
            return 0
        finally:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
