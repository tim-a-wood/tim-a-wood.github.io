#!/usr/bin/env python3
"""Run side-by-side parity checks for in-repo vs scaffolded Agent OS."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
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

MARKDOWN_PROBES = (
    "STYLE_GUIDE.md",
    "agents/design/charter.md",
)


def _fetch(url: str, timeout: float = 3.0) -> tuple[int | None, bytes]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None, b""


def _fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    status, body = _fetch(url, timeout)
    if status is None or status < 200 or status >= 300:
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _wait_for_json(url: str, timeout_sec: float) -> dict[str, Any] | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        data = _fetch_json(url)
        if data is not None:
            return data
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


def _normalize_dashboard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in REQUIRED_DASHBOARD_KEYS:
        out[key] = payload.get(key)
    if isinstance(out.get("home_internal"), dict):
        out["home_internal"] = {
            "blocking_issue_count": out["home_internal"].get("blocking_issue_count"),
            "serious_issue_count": out["home_internal"].get("serious_issue_count"),
            "founder_decisions_open": out["home_internal"].get("founder_decisions_open"),
            "priorities_in_progress": out["home_internal"].get("priorities_in_progress"),
            "tests_passing": out["home_internal"].get("tests_passing"),
            "tests_failing": out["home_internal"].get("tests_failing"),
            "broken_test_collections": out["home_internal"].get("broken_test_collections"),
            "release_gate_label": out["home_internal"].get("release_gate_label"),
        }
    return out


def _ma_hash32(text: str) -> int:
    h = 2166136261
    for ch in str(text or ""):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def _ma_norm_title(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _ma_founder_id(agent: str, fd: dict[str, Any]) -> str:
    explicit = str(fd.get("my_actions_id") or "").strip()
    if explicit:
        return f"{agent}:founder:{explicit}"
    t = f"{fd.get('title', '')}\0{fd.get('source', '')}\0{fd.get('note', '')}"
    return f"{agent}:founder:{_ma_hash32(t):x}"


def _item_visible_in_context(item: dict[str, Any], ctx: str) -> bool:
    if ctx == "all":
        return True
    raw = item.get("os_contexts", item.get("os_context"))
    if raw is None:
        return True
    arr = raw if isinstance(raw, list) else [raw]
    cleaned = [str(x).strip() for x in arr if str(x).strip()]
    if not cleaned:
        return True
    return ctx in cleaned


def _aggregate_my_actions(status_payloads: dict[str, dict[str, Any]], ctx: str = "all") -> dict[str, int]:
    blocking = 0
    decision = 0
    review = 0
    seen_founder: set[str] = set()
    for filename, data in status_payloads.items():
        agent = filename[: -len("-status.json")]
        if agent == "orchestration":
            agent = "orchestrator"
        for fd in data.get("founder_decisions", []):
            if not isinstance(fd, dict):
                continue
            if not _item_visible_in_context(fd, ctx):
                continue
            title = str(fd.get("title") or "").strip()
            if not title:
                continue
            is_block = fd.get("blocking") is True
            dedupe = f"{'b' if is_block else 'd'}:{_ma_norm_title(title)}"
            if dedupe in seen_founder:
                continue
            seen_founder.add(dedupe)
            _ma_founder_id(agent, fd)
            if is_block:
                blocking += 1
            else:
                decision += 1
        for p in data.get("priorities", []):
            if not isinstance(p, dict):
                continue
            if str(p.get("status") or "") != "needs-review":
                continue
            if not _item_visible_in_context(p, ctx):
                continue
            title = str(p.get("title") or "").strip()
            if not title:
                continue
            review += 1
    return {"blocking": blocking, "decision": decision, "review": review}


def _start_supervisor(app_root: Path, workspace_root: Path, supervisor_port: int, workbench_port: int, log_path: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["AGENT_OS_APP_ROOT"] = str(app_root)
    env["MV_WORKSPACE_ROOT"] = str(workspace_root)
    with log_path.open("ab") as logf:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(app_root / "scripts" / "os_dashboard_supervisor.py"),
                "--port",
                str(supervisor_port),
                "--workbench-port",
                str(workbench_port),
            ],
            cwd=str(app_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=logf,
            stderr=logf,
            start_new_session=True,
            close_fds=True,
        )
    return proc


def _status_files(workspace_root: Path) -> list[str]:
    return sorted(p.name for p in workspace_root.glob("*-status.json"))


def _read_statuses(base_url: str, status_files: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in status_files:
        payload = _fetch_json(f"{base_url}/{name}")
        if payload is None:
            raise RuntimeError(f"failed to fetch {name} from {base_url}")
        out[name] = payload
    return out


def _markdown_probe(base_url: str, rel: str) -> tuple[int | None, int]:
    url = f"{base_url}/view/markdown?path={urllib.parse.quote(rel, safe='')}"
    status, body = _fetch(url, timeout=5.0)
    return status, len(body)


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare in-repo and scaffolded Agent OS behavior.")
    ap.add_argument("--workspace-root", type=Path, default=APP_ROOT, help="MV workspace root")
    ap.add_argument("--internal-port", type=int, default=8770, help="Port for in-repo supervisor")
    ap.add_argument("--external-port", type=int, default=8779, help="Port for scaffolded supervisor")
    ap.add_argument("--workbench-port", type=int, default=8766, help="Expected MV workbench port")
    ap.add_argument("--timeout", type=float, default=20.0, help="Startup timeout in seconds")
    args = ap.parse_args()

    workspace_root = args.workspace_root.expanduser().resolve()
    if not workspace_root.is_dir():
        raise SystemExit(f"Workspace root missing: {workspace_root}")

    with tempfile.TemporaryDirectory(prefix="agent-os-parity-") as td:
        tmp_root = Path(td)
        external_root = tmp_root / "agent-os"
        _run_bootstrap(external_root)

        internal_log = tmp_root / "internal.log"
        external_log = tmp_root / "external.log"
        internal = _start_supervisor(APP_ROOT, workspace_root, args.internal_port, args.workbench_port, internal_log)
        external = _start_supervisor(external_root, workspace_root, args.external_port, args.workbench_port, external_log)
        try:
            internal_url = f"http://127.0.0.1:{args.internal_port}"
            external_url = f"http://127.0.0.1:{args.external_port}"
            internal_payload = _wait_for_json(f"{internal_url}/api/dashboard-data", args.timeout)
            external_payload = _wait_for_json(f"{external_url}/api/dashboard-data", args.timeout)
            if internal_payload is None:
                raise RuntimeError(f"in-repo supervisor failed to start\n{internal_log.read_text(encoding='utf-8', errors='replace')[-4000:]}")
            if external_payload is None:
                raise RuntimeError(f"external supervisor failed to start\n{external_log.read_text(encoding='utf-8', errors='replace')[-4000:]}")

            status_files = _status_files(workspace_root)
            internal_statuses = _read_statuses(internal_url, status_files)
            external_statuses = _read_statuses(external_url, status_files)
            if internal_statuses != external_statuses:
                raise RuntimeError("status JSON responses differ between in-repo and external supervisors")

            internal_actions = _aggregate_my_actions(internal_statuses)
            external_actions = _aggregate_my_actions(external_statuses)
            if internal_actions != external_actions:
                raise RuntimeError(f"My Actions counts differ: {internal_actions!r} vs {external_actions!r}")

            markdown_results: dict[str, dict[str, Any]] = {}
            for rel in MARKDOWN_PROBES:
                i_status, i_len = _markdown_probe(internal_url, rel)
                e_status, e_len = _markdown_probe(external_url, rel)
                markdown_results[rel] = {
                    "internal_status": i_status,
                    "external_status": e_status,
                    "internal_len": i_len,
                    "external_len": e_len,
                }
                if i_status != 200 or e_status != 200:
                    raise RuntimeError(f"markdown preview failed for {rel}: {markdown_results[rel]!r}")

            manifest_internal = _read_json_file(APP_ROOT / "docs" / "os-documentLibrary.manifest.json")
            manifest_external = _read_json_file(external_root / "docs" / "os-documentLibrary.manifest.json")
            if manifest_internal is None or manifest_external is None:
                raise RuntimeError("document-library manifest did not load from one or both runtimes")
            if manifest_internal != manifest_external:
                raise RuntimeError("document-library manifest differs between runtimes")
            categories = manifest_internal.get("categories")
            if not isinstance(categories, list) or len(categories) == 0:
                raise RuntimeError("document-library manifest loaded but categories were empty")

            result = {
                "ok": True,
                "internal_url": internal_url,
                "external_url": external_url,
                "dashboard_data": {
                    "internal": _normalize_dashboard_payload(internal_payload),
                    "external": _normalize_dashboard_payload(external_payload),
                },
                "my_actions": internal_actions,
                "status_file_count": len(status_files),
                "markdown": markdown_results,
                "document_library_categories": len(categories),
            }
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        finally:
            for proc in (internal, external):
                try:
                    proc.terminate()
                except OSError:
                    pass
            for proc in (internal, external):
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
