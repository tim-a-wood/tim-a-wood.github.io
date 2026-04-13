"""
Cursor Cloud Agents API — launch repo agents and fetch PNG artifacts.

Docs: https://cursor.com/docs/cloud-agent/api/endpoints
Auth: Basic with API key as username and empty password (see Cursor API overview).

This path is experimental: each image request launches a cloud agent, polls until
FINISHED, then downloads the largest PNG from agent artifacts. It is much slower
and costlier than Gemini image generation.
"""
from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CURSOR_API_ORIGIN = "https://api.cursor.com"


def _basic_auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key.strip()}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _read_json_response(resp: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw = resp.read()
    except OSError as exc:
        return None, str(exc)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, raw[:500].decode("utf-8", errors="replace")
    if not isinstance(data, dict):
        return None, "non_object_json"
    return data, None


def _cursor_request(
    method: str,
    path: str,
    *,
    api_key: str,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 120.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    url = f"{CURSOR_API_ORIGIN}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": _basic_auth_header(api_key),
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 200) or 200
            payload, err = _read_json_response(resp)
            if err and payload is None:
                return None, err, code
            return payload, None, code
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        try:
            parsed = json.loads(detail)
            err_obj = parsed.get("error")
            if isinstance(err_obj, dict):
                msg = err_obj.get("message") or str(err_obj.get("code") or detail)
            else:
                msg = parsed.get("message") or err_obj or detail
        except json.JSONDecodeError:
            msg = detail
        return None, f"HTTP {exc.code}: {msg}", exc.code
    except urllib.error.URLError as exc:
        return None, str(exc.reason or exc), 0


def _poll_timeout_sec() -> int:
    raw = __import__("os").environ.get("CURSOR_CLOUD_AGENT_POLL_TIMEOUT_SEC", "1800").strip()
    try:
        return max(120, min(7200, int(raw)))
    except ValueError:
        return 1800


def _poll_interval_sec() -> float:
    raw = __import__("os").environ.get("CURSOR_CLOUD_AGENT_POLL_INTERVAL_SEC", "5").strip()
    try:
        return max(2.0, min(60.0, float(raw)))
    except ValueError:
        return 5.0


def run_cloud_agent_png_task(
    *,
    api_key: str,
    repository: str,
    repository_ref: str,
    model: str,
    prompt_text: str,
    reference_pngs: List[Tuple[bytes, int, int]],
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Launch an agent with prompt + up to 5 reference images (raw PNG bytes + dimensions).
    Poll until FINISHED, then return bytes of the largest PNG artifact.
    """
    if not api_key.strip():
        return None, "missing_cursor_api_key"
    if not repository.strip():
        return None, "missing_cursor_cloud_repository"

    image_attachments: List[Dict[str, Any]] = []
    for blob, w, h in reference_pngs[:5]:
        if not blob:
            continue
        image_attachments.append({
            "data": base64.b64encode(blob).decode("ascii"),
            "dimension": {"width": int(w), "height": int(h)},
        })

    prompt_obj: Dict[str, Any] = {"text": prompt_text}
    if image_attachments:
        prompt_obj["images"] = image_attachments

    create_body: Dict[str, Any] = {
        "prompt": prompt_obj,
        "model": model.strip() or "composer-2",
        "source": {
            "repository": repository.strip(),
            "ref": (repository_ref.strip() or "main"),
        },
        "target": {"autoCreatePr": False},
    }

    created, err, code = _cursor_request("POST", "/v0/agents", api_key=api_key, body=create_body, timeout=120.0)
    if err or not created:
        return None, err or f"cursor_agent_create_failed:{code}"
    agent_id = str(created.get("id") or "").strip()
    if not agent_id:
        return None, "cursor_agent_missing_id"

    deadline = time.monotonic() + float(_poll_timeout_sec())
    interval = _poll_interval_sec()
    last_status = ""
    while time.monotonic() < deadline:
        status_payload, s_err, _ = _cursor_request("GET", f"/v0/agents/{agent_id}", api_key=api_key, timeout=60.0)
        if s_err or not status_payload:
            return None, s_err or "cursor_agent_status_failed"
        status = str(status_payload.get("status") or "").upper()
        last_status = status
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            summary = str(status_payload.get("summary") or "").strip()
            return None, f"cursor_agent_{status.lower()}:{summary or 'no_summary'}"
        time.sleep(interval)
    else:
        return None, f"cursor_agent_timeout:last_status={last_status or 'unknown'}"

    arts_payload, a_err, _ = _cursor_request("GET", f"/v0/agents/{agent_id}/artifacts", api_key=api_key, timeout=60.0)
    if a_err or not arts_payload:
        return None, a_err or "cursor_agent_artifacts_failed"

    artifacts = arts_payload.get("artifacts") or []
    if not isinstance(artifacts, list) or not artifacts:
        return None, "cursor_agent_no_artifacts"

    png_candidates: List[Tuple[int, str]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        path = str(item.get("absolutePath") or "")
        size_b = int(item.get("sizeBytes") or 0)
        if path.lower().endswith(".png") and size_b > 0:
            png_candidates.append((size_b, path))

    if not png_candidates:
        return None, "cursor_agent_no_png_artifact"

    png_candidates.sort(key=lambda t: t[0], reverse=True)
    chosen_path = png_candidates[0][1]

    dl_path = (
        "/v0/agents/"
        + urllib.parse.quote(agent_id, safe="")
        + "/artifacts/download?path="
        + urllib.parse.quote(chosen_path, safe="")
    )
    dl_payload, d_err, _ = _cursor_request("GET", dl_path, api_key=api_key, timeout=60.0)
    if d_err or not dl_payload:
        return None, d_err or "cursor_agent_download_url_failed"
    presigned = str(dl_payload.get("url") or "").strip()
    if not presigned:
        return None, "cursor_agent_presigned_url_missing"

    try:
        with urllib.request.urlopen(presigned, timeout=120.0) as img_resp:
            data = img_resp.read()
    except urllib.error.URLError as exc:
        return None, f"cursor_agent_fetch_png:{exc.reason or exc}"

    if not data or len(data) < 32:
        return None, "cursor_agent_empty_png"
    logger.info("cursor cloud agent %s returned PNG %s bytes from %s", agent_id, len(data), chosen_path)
    return data, None
