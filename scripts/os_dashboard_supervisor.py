#!/usr/bin/env python3
"""
Local Agent OS dashboard: serves os-dashboard.html, read-only policy docs under
allowed path prefixes (for the Guides & policies iframe and in-page links), GET /api/dashboard-data,
POST /api/workbench/{start|stop|restart}, POST /api/status-update (full JSON replace per file, including row deletes from the dashboard),
POST /api/archive-document (move a policy/guide to docs/archived-policies/ and write a reference report),
and POST /api/issue-chat (issue and opportunity discussion in the UI; JSON body may set rowKind to "opportunity").
Binds 127.0.0.1 only.

Issue chat backends (see selection logic in Handler):
  • OpenAI Chat Completions — fast (seconds). Set OPENAI_API_KEY; optional ISSUE_CHAT_MODEL.
    Recommended for dashboard "Discuss issue" latency. Set ISSUE_CHAT_PREFER_OPENAI=1 to use
    this even when CURSOR_API_KEY is also set.
  • Cursor Cloud Agents API — slow (polls a repo-backed agent on GitHub). Set CURSOR_API_KEY
     (Cursor Dashboard → Cloud Agents). Optional: CURSOR_ISSUE_CHAT_REPOSITORY,
     CURSOR_ISSUE_CHAT_REF. If the repository is unset, tries `git remote get-url origin`.

Cursor does not offer a generic HTTP "chat completions" API; Cloud Agents are the
supported programmatic path. Each dashboard message launches a short-lived agent,
polls until it finishes, reads the conversation, then deletes the agent by default
(set CURSOR_ISSUE_CHAT_KEEP_AGENT=1 to skip deletion).

Usage:
  CURSOR_API_KEY=key_... python3 scripts/os_dashboard_supervisor.py
  # or: OPENAI_API_KEY=... python3 scripts/os_dashboard_supervisor.py

Open http://127.0.0.1:<port>/os-dashboard.html
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.workbench_local_control import (
    build_supervisor_dashboard_payload,
    parse_env_local,
    restart_workbench,
    start_workbench,
    stop_workbench,
)

REPO_ROOT = _REPO_ROOT


def load_agent_os_env_file(repo_root: Path) -> None:
    """
    Load optional repo-root agent_os.env into os.environ (does not override existing vars).
    Lines: KEY=value, # comments, blank lines. Values may use optional single/double quotes.
    """
    path = repo_root / "agent_os.env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key in os.environ and (os.environ.get(key) or "").strip():
            continue
        os.environ[key] = val


def load_dotenv_local_for_supervisor(repo_root: Path) -> None:
    """
    Load optional repo-root .env.local (Sprite Workbench format; `export KEY=value` allowed).
    Does not override existing os.environ entries that are already non-empty.
    """
    path = repo_root / ".env.local"
    try:
        pairs = parse_env_local(path)
    except OSError:
        return
    for key, val in pairs.items():
        if not key or not (val or "").strip():
            continue
        if key in os.environ and (os.environ.get(key) or "").strip():
            continue
        os.environ[key] = val


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


CURSOR_API_BASE = "https://api.cursor.com"


def _cursor_auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _http_request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    if not raw.strip():
        return code, {}
    try:
        return code, json.loads(raw)
    except json.JSONDecodeError:
        return code, {"_raw": raw}


def _github_https_from_git_origin(repo_root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except OSError:
        return None
    if r.returncode != 0:
        return None
    url = (r.stdout or "").strip()
    if url.startswith("git@github.com:"):
        path = url.split(":", 1)[1].removesuffix(".git")
        return f"https://github.com/{path}"
    if "github.com" in url and url.startswith("http"):
        return url.removesuffix(".git")
    return None


def _issue_chat_parse_json_from_text(text: str) -> dict[str, Any]:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    return json.loads(t)


def _issue_chat_result_from_cursor_conversation(messages: list[dict[str, Any]]) -> dict[str, Any]:
    texts: list[str] = []
    for msg in messages:
        if msg.get("type") == "assistant_message" and isinstance(msg.get("text"), str):
            texts.append(msg["text"].strip())
    if not texts:
        return {
            "thinking": "",
            "assistant_message": "No assistant messages in the Cursor agent conversation.",
            "priority_updates": [],
        }
    last = texts[-1]
    try:
        parsed = _issue_chat_parse_json_from_text(last)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"thinking": "", "assistant_message": last, "priority_updates": []}


def _issue_chat_call_cursor_cloud_agent(
    *,
    api_key: str,
    repository: str,
    ref: str,
    model: str,
    instruction_text: str,
    poll_interval_sec: float = 2.5,
    max_wait_sec: float = 180.0,
) -> dict[str, Any]:
    """
    Launch a Cursor Cloud Agent with one prompt, wait for a terminal status,
    read conversation JSON, optionally delete the agent.
    """
    auth = _cursor_auth_header(api_key)
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json",
    }
    launch_body: dict[str, Any] = {
        "prompt": {"text": instruction_text},
        "model": model,
        "source": {"repository": repository, "ref": ref},
        "target": {"autoCreatePr": False},
    }
    code, data = _http_request_json(
        "POST",
        f"{CURSOR_API_BASE}/v0/agents",
        headers=headers,
        body=launch_body,
        timeout=120,
    )
    if code >= 400:
        raise RuntimeError(f"Cursor launch HTTP {code}: {json.dumps(data, ensure_ascii=False)[:1200]}")
    agent_id = data.get("id")
    if not isinstance(agent_id, str) or not agent_id:
        raise RuntimeError(f"Cursor launch missing agent id: {data!r}")

    terminal = frozenset(
        {"FINISHED", "FAILED", "ERROR", "CANCELLED", "STOPPED", "REJECTED"}
    )
    deadline = time.monotonic() + max_wait_sec
    status_payload: dict[str, Any] = {}
    while time.monotonic() < deadline:
        sc, status_payload = _http_request_json(
            "GET",
            f"{CURSOR_API_BASE}/v0/agents/{agent_id}",
            headers=headers,
            body=None,
            timeout=60,
        )
        if sc >= 400:
            raise RuntimeError(f"Cursor status HTTP {sc}: {json.dumps(status_payload, ensure_ascii=False)[:800]}")
        st = status_payload.get("status")
        st_u = str(st).upper() if st is not None else ""
        if st_u in terminal:
            break
        time.sleep(poll_interval_sec)
    else:
        raise RuntimeError("Cursor agent timed out before reaching a terminal status.")

    st_final_u = str(status_payload.get("status") or "").upper()
    if st_final_u != "FINISHED":
        summ = status_payload.get("summary") or status_payload.get("message")
        if summ is None:
            summ = json.dumps(status_payload, ensure_ascii=False)[:1200]
        elif not isinstance(summ, str):
            summ = str(summ)
        raise RuntimeError(f"Cursor agent ended with status {st_final_u!r}: {summ[:1200]}")

    cc, conv = _http_request_json(
        "GET",
        f"{CURSOR_API_BASE}/v0/agents/{agent_id}/conversation",
        headers=headers,
        body=None,
        timeout=60,
    )
    if cc >= 400:
        raise RuntimeError(f"Cursor conversation HTTP {cc}: {json.dumps(conv, ensure_ascii=False)[:800]}")
    raw_messages = conv.get("messages")
    messages = raw_messages if isinstance(raw_messages, list) else []
    result = _issue_chat_result_from_cursor_conversation(messages)

    if os.environ.get("CURSOR_ISSUE_CHAT_KEEP_AGENT", "").strip() not in ("1", "true", "yes"):
        _http_request_json(
            "DELETE",
            f"{CURSOR_API_BASE}/v0/agents/{agent_id}",
            headers=headers,
            body=None,
            timeout=60,
        )

    return result


def _norm_path(handler: BaseHTTPRequestHandler) -> str:
    p = urlparse(handler.path).path
    p = unquote(p)
    p = p.rstrip("/")
    return p if p else "/"


READONLY_DOC_PREFIXES = (
    "docs/",
    "agents/",
    "prompts/",
    "decisions/",
    "research/",
    "knowledge/",
    "playbooks/",
    "templates/",
    "tests/",
    "artifacts/",
    "tools/2d-sprite-and-animation/docs/",
    ".cursor/rules/",
)
READONLY_ROOT_FILES = frozenset({
    "AGENTS.md",
    "CLAUDE.md",
    "STYLE_GUIDE.md",
    "README.md",
})


def _readonly_doc_path_allowed(rel: str) -> bool:
    r = rel.replace("\\", "/").lstrip("/")
    if not r or r.startswith("..") or "/../" in r:
        return False
    low = r.lower()
    if low in {x.lower() for x in READONLY_ROOT_FILES}:
        return True
    for prefix in READONLY_DOC_PREFIXES:
        if r.startswith(prefix):
            return True
    return False


def _content_type_for_path(fpath: Path) -> str:
    suf = fpath.suffix.lower()
    if suf == ".html":
        return "text/html; charset=utf-8"
    if suf == ".md":
        return "text/markdown; charset=utf-8"
    if suf == ".mdc":
        return "text/markdown; charset=utf-8"
    return "application/octet-stream"


def _resolve_readonly_repo_file(repo_root: Path, rel: str) -> tuple[bytes, str] | None:
    """Return (body, content_type) for an allowed read-only file, or None."""
    rel = rel.replace("\\", "/").lstrip("/")
    if not _readonly_doc_path_allowed(rel):
        return None
    fpath = (repo_root / rel).resolve()
    try:
        fpath.relative_to(repo_root.resolve())
    except ValueError:
        return None
    if not fpath.is_file():
        return None
    suf = fpath.suffix.lower()
    if suf not in {".md", ".html", ".mdc"}:
        return None
    return (fpath.read_bytes(), _content_type_for_path(fpath))


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
            "finance-status.json",
            "legal-status.json",
            "cybersecurity-status.json",
            "support-status.json",
            "animation-status.json",
            "narrative-status.json",
            "audio-status.json",
            "creative-status.json",
            "research-status.json",
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
            full = urlparse(self.path)
            path_only = (full.path or "/").rstrip("/") or "/"
            if path_only == "/view/markdown":
                qs = parse_qs(full.query, keep_blank_values=False)
                paths = qs.get("path", [])
                if not paths or not str(paths[0]).strip():
                    return self._send_json(
                        HTTPStatus.BAD_REQUEST, {"error": "path query parameter required"}
                    )
                rel = unquote(str(paths[0]).strip()).replace("\\", "/").lstrip("/")
                if not _readonly_doc_path_allowed(rel):
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                suf = Path(rel).suffix.lower()
                if suf not in {".md", ".mdc"}:
                    return self._send_json(
                        HTTPStatus.BAD_REQUEST, {"error": "Only .md and .mdc can be previewed"}
                    )
                fpath = (repo_root / rel).resolve()
                try:
                    fpath.relative_to(repo_root.resolve())
                except ValueError:
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                if not fpath.is_file():
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                try:
                    text = fpath.read_text(encoding="utf-8")
                except OSError:
                    return self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Failed to read file"}
                    )
                from scripts.render_markdown_view import build_markdown_view_page

                page = build_markdown_view_page(
                    title=fpath.stem.replace("-", " ").replace("_", " "),
                    repo_path=rel,
                    source=text,
                    repo_root=repo_root,
                )
                return self._send_bytes(
                    HTTPStatus.OK,
                    page.encode("utf-8"),
                    "text/html; charset=utf-8",
                )

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
            doc_payload = _resolve_readonly_repo_file(repo_root, path.lstrip("/"))
            if doc_payload is not None:
                body, ctype = doc_payload
                return self._send_bytes(HTTPStatus.OK, body, ctype)
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:
            raw_path = _norm_path(self)

            if raw_path == "/api/archive-document":
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length) if length > 0 else b""
                try:
                    payload = json.loads(raw_body or b"{}")
                except json.JSONDecodeError:
                    return self._send_json(
                        HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid JSON"}
                    )
                path = (payload.get("path") or "").strip()
                if not path:
                    return self._send_json(
                        HTTPStatus.BAD_REQUEST, {"ok": False, "error": "path required"}
                    )
                reason = payload.get("reason") or ""
                if not isinstance(reason, str):
                    reason = ""
                reason = reason.strip()
                confirm_gov = bool(payload.get("confirmGovernanceRoot"))
                from scripts.archive_policy_document import archive_policy_document

                result = archive_policy_document(
                    repo_root,
                    path,
                    reason=reason,
                    confirm_governance_root=confirm_gov,
                )
                if result.get("ok"):
                    return self._send_json(HTTPStatus.OK, result)
                return self._send_json(HTTPStatus.BAD_REQUEST, result)

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

                row_kind = (payload.get("rowKind") or payload.get("row_kind") or "priority").strip().lower()
                if row_kind not in ("priority", "opportunity"):
                    row_kind = "priority"

                cursor_key = (os.environ.get("CURSOR_API_KEY") or "").strip()
                openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
                prefer_openai = (os.environ.get("ISSUE_CHAT_PREFER_OPENAI") or "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )

                allowed_files = ", ".join(sorted(status_write_allow))

                # Strip internal dashboard meta-fields (_file, _agent, _idx, etc.)
                # before presenting the issue snapshot to the LLM. These fields are
                # injected by the dashboard JS and cause ID confusion (the LLM may
                # use _idx as the id instead of the actual id field).
                clean_issue = {k: v for k, v in issue.items() if not k.startswith("_")}
                item_file = issue.get("_file", "")
                item_id = issue.get("_priorityId", clean_issue.get("id", ""))

                if row_kind == "opportunity":
                    system_prompt = (
                        f"You are the {agent_label} specialist for the MV metroidvania toolchain (solo-founder OS).\n"
                        f"Charter reference path: {agent_charter or '(not provided)'}\n\n"
                        "The user is discussing ONE opportunity row from a dashboard status JSON file "
                        "(the `opportunities` array, not `priorities`).\n"
                        f"Source file: {item_file}\n"
                        f"Item id (use this exact value in priority_updates): {json.dumps(item_id)}\n"
                        "Current opportunity data (JSON):\n"
                        f"{json.dumps(clean_issue, ensure_ascii=False, indent=2)}\n\n"
                        "You may propose edits to this opportunity and, if the user explicitly agrees, to other "
                        "opportunities in the same file or another allowed status file when logically necessary.\n\n"
                        "Respond with a single JSON object ONLY, keys:\n"
                        '- "thinking": string, your step-by-step reasoning (show your work).\n'
                        '- "assistant_message": string, concise reply to the user.\n'
                        '- "priority_updates": array of objects, each: '
                        '{"file": "<filename>", "id": <use the exact item id shown above, string or number>, '
                        '"fields": { ... partial fields ... }} '
                        "where fields may include title, status, risk, note, solution, owner, stakeholders, summary. "
                        'Use the field name "solution" for proposed mitigation text (not "proposed_solution"). '
                        "stakeholders may be a string, comma-separated string, or array of strings. "
                        "Use [] if no file changes are appropriate yet.\n\n"
                        f"Allowed file names for priority_updates: {allowed_files}\n"
                        "Each update targets an object inside the `opportunities` array with a matching `id`.\n"
                        "Do not invent file names. Status must be one of: "
                        "in-progress, needs-review, queued, paused, done. Risk: high, med, low.\n\n"
                        "Do not open a pull request or push commits for this task unless the user explicitly asked you to "
                        "change the repository; prefer analysis and the JSON reply only."
                    )
                else:
                    system_prompt = (
                        f"You are the {agent_label} specialist for the MV metroidvania toolchain (solo-founder OS).\n"
                        f"Charter reference path: {agent_charter or '(not provided)'}\n\n"
                        "The user is discussing ONE priority row from a dashboard status JSON file.\n"
                        f"Source file: {item_file}\n"
                        f"Item id (use this exact value in priority_updates): {json.dumps(item_id)}\n"
                        "Current priority data (JSON):\n"
                        f"{json.dumps(clean_issue, ensure_ascii=False, indent=2)}\n\n"
                        "You may propose edits to this priority and, if the user explicitly agrees, to other priorities "
                        "in the same file or another allowed status file when logically necessary.\n\n"
                        "Respond with a single JSON object ONLY, keys:\n"
                        '- "thinking": string, your step-by-step reasoning (show your work).\n'
                        '- "assistant_message": string, concise reply to the user.\n'
                        '- "priority_updates": array of objects, each: '
                        '{"file": "<filename>", "id": <use the exact item id shown above, string or number>, "fields": { ... partial fields ... }} '
                        "where fields may include title, status, risk, note, proposed_solution, owner, stakeholders, summary. "
                        "Use [] if no file changes are appropriate yet.\n\n"
                        f"Allowed file names for priority_updates: {allowed_files}\n"
                        "Each update targets an object inside the `priorities` array with a matching `id`.\n"
                        "Do not invent file names. Status must be one of: "
                        "in-progress, needs-review, queued, paused, done. Risk: high, med, low.\n\n"
                        "Do not open a pull request or push commits for this task unless the user explicitly asked you to "
                        "change the repository; prefer analysis and the JSON reply only."
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

                    transcript = "\n\n".join(
                        f"{m['role'].upper()}: {m['content']}" for m in norm_messages
                    )
                    instruction_text = (
                        system_prompt
                        + "\n\n## Conversation\n\n"
                        + transcript
                        + "\n\nOutput: reply with one JSON object only (valid JSON, no markdown fences), "
                        "using the keys thinking, assistant_message, priority_updates exactly as specified."
                    )

                    if prefer_openai and openai_key:
                        model = (os.environ.get("ISSUE_CHAT_MODEL") or "gpt-4o-mini").strip()
                        result = _issue_chat_call_openai(
                            api_key=openai_key,
                            model=model,
                            system_prompt=system_prompt,
                            messages=norm_messages,
                        )
                    elif cursor_key:
                        repo = (os.environ.get("CURSOR_ISSUE_CHAT_REPOSITORY") or "").strip()
                        if not repo:
                            repo = _github_https_from_git_origin(repo_root) or ""
                        if not repo:
                            if openai_key:
                                model = (os.environ.get("ISSUE_CHAT_MODEL") or "gpt-4o-mini").strip()
                                result = _issue_chat_call_openai(
                                    api_key=openai_key,
                                    model=model,
                                    system_prompt=system_prompt,
                                    messages=norm_messages,
                                )
                            else:
                                return self._send_json(
                                    HTTPStatus.SERVICE_UNAVAILABLE,
                                    {
                                        "error": "no_cursor_repo",
                                        "message": "Set CURSOR_ISSUE_CHAT_REPOSITORY to your GitHub repo HTTPS URL "
                                        "(example: https://github.com/org/repo), or add a github.com git remote named "
                                        "origin. Cursor Cloud Agents require a GitHub source. Or set OPENAI_API_KEY "
                                        "for fast issue chat without GitHub.",
                                    },
                                )
                        else:
                            ref = (os.environ.get("CURSOR_ISSUE_CHAT_REF") or "main").strip() or "main"
                            cursor_model = (os.environ.get("CURSOR_ISSUE_CHAT_MODEL") or "default").strip() or "default"
                            result = _issue_chat_call_cursor_cloud_agent(
                                api_key=cursor_key,
                                repository=repo,
                                ref=ref,
                                model=cursor_model,
                                instruction_text=instruction_text,
                            )
                    elif openai_key:
                        model = (os.environ.get("ISSUE_CHAT_MODEL") or "gpt-4o-mini").strip()
                        result = _issue_chat_call_openai(
                            api_key=openai_key,
                            model=model,
                            system_prompt=system_prompt,
                            messages=norm_messages,
                        )
                    else:
                        return self._send_json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {
                                "error": "no_api_key",
                                "message": "Set OPENAI_API_KEY (fast chat) and/or CURSOR_API_KEY (slow Cloud Agents on "
                                "GitHub). Use ISSUE_CHAT_PREFER_OPENAI=1 with both keys to force OpenAI. Restart the "
                                "supervisor after changing environment variables.",
                            },
                        )
                except (RuntimeError, KeyError, json.JSONDecodeError, TypeError) as exc:
                    return self._send_json(
                        HTTPStatus.BAD_GATEWAY,
                        {"error": "chat_failed", "message": str(exc)},
                    )
                if not isinstance(result, dict):
                    result = {
                        "thinking": "",
                        "assistant_message": str(result),
                        "priority_updates": [],
                    }
                else:
                    result.setdefault("thinking", "")
                    result.setdefault("assistant_message", "")
                    pu = result.get("priority_updates")
                    if not isinstance(pu, list):
                        result["priority_updates"] = []
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
    load_agent_os_env_file(REPO_ROOT)
    load_dotenv_local_for_supervisor(REPO_ROOT)
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
    _ck = (os.environ.get("CURSOR_API_KEY") or "").strip()
    _ok = (os.environ.get("OPENAI_API_KEY") or "").strip()
    _prefer_oai = (os.environ.get("ISSUE_CHAT_PREFER_OPENAI") or "").strip().lower() in ("1", "true", "yes")
    if _prefer_oai and _ok:
        print("Issue chat: OPENAI_API_KEY (ISSUE_CHAT_PREFER_OPENAI=1 — fast Chat Completions).", file=sys.stderr)
    elif _ok and not _ck:
        print("Issue chat: OPENAI_API_KEY (fast Chat Completions).", file=sys.stderr)
    elif _ck:
        print(
            "Issue chat: CURSOR_API_KEY (Cloud Agents on GitHub — slow). "
            "Set OPENAI_API_KEY and ISSUE_CHAT_PREFER_OPENAI=1 to use fast OpenAI for Discuss issue.",
            file=sys.stderr,
        )
    elif (REPO_ROOT / "agent_os.env").is_file() or (REPO_ROOT / ".env.local").is_file():
        print(
            "Issue chat: agent_os.env or .env.local present but no CURSOR_API_KEY/OPENAI_API_KEY "
            "(or keys are empty). Set a key and restart the supervisor.",
            file=sys.stderr,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
