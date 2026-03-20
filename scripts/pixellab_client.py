#!/usr/bin/env python3
"""
Minimal Pixel Lab API client used by the sprite workbench server.

This module intentionally keeps response handling permissive because Pixel Lab
can return different shapes depending on whether an endpoint runs in the
foreground or as an async background job.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image


logger = logging.getLogger(__name__)

SizeLike = Union[Tuple[int, int], Dict[str, int]]


def _pixel_lab_serial_animate_fallback_enabled() -> bool:
    """If true (default), retry failed directions with one POST per direction after parallel poll settles."""
    v = os.environ.get("PIXELLAB_ANIMATE_SERIAL_FALLBACK", "1")
    return str(v).strip().lower() not in ("0", "false", "no", "off")


def _direction_labels_aligned(accepted_labels: Any, kwargs_directions: Any, n: int) -> List[str]:
    """Best-effort direction names aligned 1:1 with ``background_job_ids`` order."""
    if isinstance(accepted_labels, list) and len(accepted_labels) == n:
        return [str(x) for x in accepted_labels]
    if isinstance(kwargs_directions, list) and len(kwargs_directions) == n:
        return [str(x) for x in kwargs_directions]
    return ["dir_%d" % (i + 1) for i in range(n)]


def _log_pixellab_post_accepted(context: str, accepted: Any) -> None:
    """INFO log for async POST acceptance (job ids / status) so long polls are not silent."""
    if not isinstance(accepted, dict):
        logger.info("Pixel Lab %s POST response type=%s", context, type(accepted).__name__)
        return
    keys = list(accepted.keys())
    st = accepted.get("status")
    bj = accepted.get("background_job_ids") or accepted.get("backgroundJobIds")
    if isinstance(bj, list) and bj:
        first = bj[0]
        sid = (first[:32] + "…") if isinstance(first, str) and len(first) > 32 else first
        logger.info(
            "Pixel Lab %s POST returned status=%r background_job_ids=%d (e.g. %s); polling…",
            context,
            st,
            len(bj),
            sid,
        )
        return
    for k in ("job_id", "jobId", "background_job_id", "backgroundJobId", "id"):
        v = accepted.get(k)
        if isinstance(v, str) and v.strip():
            logger.info(
                "Pixel Lab %s POST returned status=%r %s=%s; polling…",
                context,
                st,
                k,
                (v[:40] + "…") if len(v) > 40 else v,
            )
            return
    logger.info(
        "Pixel Lab %s POST returned keys=%s status=%r (no job id — treating as synchronous body)",
        context,
        keys,
        st,
    )


def _normalize_size(image_size: SizeLike) -> Dict[str, int]:
    if isinstance(image_size, dict):
        return {"width": int(image_size["width"]), "height": int(image_size["height"])}
    width, height = image_size
    return {"width": int(width), "height": int(height)}


def base64_image_payload(image_b64: str, image_format: str = "png") -> Dict[str, Any]:
    """
    Build a Pixel Lab v2 ``Base64Image`` object.

    Several endpoints (e.g. ``/v2/create-character-with-8-directions``) expect
    ``color_image`` as this object, not a raw base64 string.
    """
    return {"type": "base64", "base64": image_b64, "format": image_format}


def _json_dumps(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class PixelLabError(RuntimeError):
    pass


@dataclass
class PixelLabHTTPError(PixelLabError):
    status_code: int
    payload: Any
    url: str

    def __str__(self) -> str:
        detail = None
        if isinstance(self.payload, dict):
            detail = self.payload.get("detail") or self.payload.get("message")
        return f"Pixel Lab HTTP {self.status_code} for {self.url}: {detail or self.payload!r}"


def format_background_job_failure(payload: Any) -> str:
    """
    Extract a short message from a failed ``GET /v2/background-jobs/{id}`` JSON body
    (no full ``repr`` of usage / nested dicts). Callers add outer context (e.g. direction 3/4).
    """
    if not isinstance(payload, dict):
        return "Background job failed (unexpected response shape)."
    lr = payload.get("last_response")
    primary = ""
    if isinstance(lr, dict):
        chunks: List[str] = []
        for key in ("error", "message", "title", "detail"):
            v = lr.get(key)
            if isinstance(v, str) and v.strip() and v.strip() not in chunks:
                chunks.append(v.strip())
        if chunks:
            primary = " — ".join(chunks)
        if not primary and lr:
            try:
                primary = json.dumps(lr, ensure_ascii=False)[:600]
            except Exception:
                primary = repr(lr)[:600]
    jid = payload.get("id") or payload.get("job_id")
    job_note = ""
    if isinstance(jid, str) and jid.strip():
        job_note = " [job %s…]" % jid.strip()[:8]
    if primary:
        if len(primary) > 900:
            primary = primary[:897] + "…"
        return "%s%s" % (primary, job_note)
    return "Job failed with no error message from Pixel Lab.%s" % job_note


def _unwrap_completed_job_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a completed GET /v2/background-jobs/{id} body to the inner result dict."""
    lr = payload.get("last_response")
    if isinstance(lr, dict) and lr:
        return lr
    inner = payload.get("result") or payload.get("output")
    if isinstance(inner, dict):
        return inner
    return payload


class PixelLabClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.pixellab.ai",
        *,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

        # Best-effort storage for UI.
        self.last_usage: Optional[Dict[str, Any]] = None
        self.last_balance: Optional[Dict[str, Any]] = None

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _extract_usage_from_payload(self, payload: Any) -> None:
        if isinstance(payload, dict):
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self.last_usage = usage

    def _extract_balance_from_payload(self, payload: Any) -> None:
        if isinstance(payload, dict) and ("usd" in payload or "balance" in payload):
            self.last_balance = payload

    def _extract_job_id(self, payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        for key in ("job_id", "jobId", "background_job_id", "backgroundJobId", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        # Some APIs nest metadata.
        job = payload.get("job") if isinstance(payload, dict) else None
        if isinstance(job, dict):
            for key in ("job_id", "jobId", "id"):
                value = job.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

    def _extract_background_job_ids(self, payload: Any) -> List[str]:
        """
        v2 character animation POST may return multiple async jobs as ``background_job_ids``
        (parallel to ``directions``) instead of a single ``job_id``.
        """
        if not isinstance(payload, dict):
            return []
        for key in ("background_job_ids", "backgroundJobIds"):
            value = payload.get(key)
            if not isinstance(value, list):
                continue
            out: List[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                elif isinstance(item, dict):
                    jid = (
                        item.get("job_id")
                        or item.get("jobId")
                        or item.get("background_job_id")
                        or item.get("backgroundJobId")
                        or item.get("id")
                    )
                    if isinstance(jid, str) and jid.strip():
                        out.append(jid.strip())
            if out:
                return out
        return []

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = _json_dumps(payload) if payload is not None else None

        headers = dict(self._auth_headers())
        if payload is not None:
            headers["Content-Type"] = "application/json"

        req = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                if not raw:
                    parsed: Dict[str, Any] = {}
                else:
                    parsed = json.loads(raw.decode("utf-8"))
                self._extract_usage_from_payload(parsed)
                self._extract_balance_from_payload(parsed)
                return parsed
        except HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                parsed = raw.decode("utf-8", "replace") if raw else {}
            self._extract_usage_from_payload(parsed)
            raise PixelLabHTTPError(exc.code, parsed, url)
        except (URLError, OSError, TimeoutError) as exc:
            raise PixelLabError(f"Pixel Lab request failed for {url}: {exc}") from exc

    def _request_bytes(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> bytes:
        url = f"{self.base_url}{path}"
        body = _json_dumps(payload) if payload is not None else None

        headers = dict(self._auth_headers())
        # For binary downloads, allow content-type negotiation to be lax.
        headers.pop("Accept", None)
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            raw = exc.read()
            raise PixelLabHTTPError(exc.code, raw.decode("utf-8", "replace") if raw else {}, url)
        except (URLError, OSError, TimeoutError) as exc:
            raise PixelLabError(f"Pixel Lab request failed for {url}: {exc}") from exc

    def _poll_job(self, job_id: str, *, timeout_seconds: int = 120, interval_seconds: int = 3) -> Dict[str, Any]:
        start = time.monotonic()
        last_payload: Optional[Dict[str, Any]] = None
        poll_idx = 0
        last_heartbeat = start
        short_id = (job_id[:36] + "…") if len(job_id) > 36 else job_id

        while True:
            now = time.monotonic()
            elapsed = now - start
            if elapsed > timeout_seconds:
                raise PixelLabError(f"Pixel Lab job polling timeout after {timeout_seconds}s (job_id={job_id})")

            payload = self._request_json("GET", f"/v2/background-jobs/{job_id}")
            last_payload = payload
            poll_idx += 1

            # Best-effort status handling.
            status = None
            if isinstance(payload, dict):
                status = payload.get("status") or payload.get("job_status") or payload.get("state")

            # Heartbeat so multi-minute polls are visible in the server terminal.
            if poll_idx == 1 or (now - last_heartbeat) >= 15.0:
                logger.info(
                    "Pixel Lab poll job_id=%s status=%r elapsed=%.0fs poll#=%d",
                    short_id,
                    status,
                    elapsed,
                    poll_idx,
                )
                last_heartbeat = now

            if status in {"completed", "succeeded", "done", "success"}:
                if isinstance(payload, dict):
                    return _unwrap_completed_job_payload(payload)
                return {"result": payload}
            if status in {"failed", "error"}:
                raise PixelLabError(format_background_job_failure(payload))

            time.sleep(interval_seconds)

    def _poll_jobs_parallel(
        self,
        job_ids: List[str],
        *,
        direction_labels: Optional[List[str]] = None,
        timeout_seconds: int = 120,
        interval_seconds: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Poll multiple background jobs in round-robin each cycle.

        Unlike sequential ``_poll_job`` calls, a failed or slow job is still polled every
        cycle, so failures surface without waiting for earlier jobs to complete.
        Budget: ``timeout_seconds * len(job_ids)`` wall-clock (same worst case as sequential).
        """
        if not job_ids:
            return []
        n = len(job_ids)
        total_budget = max(int(timeout_seconds), 1) * n
        parallel_start = time.monotonic()
        deadline = parallel_start + float(total_budget)
        results: Dict[str, Dict[str, Any]] = {}
        pending = set(job_ids)
        poll_counts: Dict[str, int] = {j: 0 for j in job_ids}
        last_hb: Dict[str, float] = {j: parallel_start for j in job_ids}

        def hint_for(jid: str) -> str:
            try:
                idx = job_ids.index(jid)
            except ValueError:
                return ""
            if direction_labels and isinstance(direction_labels, list) and idx < len(direction_labels):
                return " (%s)" % direction_labels[idx]
            return ""

        def one_based_index(jid: str) -> int:
            try:
                return job_ids.index(jid) + 1
            except ValueError:
                return -1

        logger.info(
            "Pixel Lab parallel poll: %d jobs, budget=%ds (%.0fs wall-clock max)",
            n,
            timeout_seconds,
            total_budget,
        )

        while pending:
            now = time.monotonic()
            if now > deadline:
                pend = ", ".join((p[:8] + "…") for p in sorted(pending)[:8])
                raise PixelLabError(
                    "Pixel Lab jobs still pending after %ds (budget=%ds): %s"
                    % (int(now - parallel_start), total_budget, pend or "(none)")
                )

            for jid in list(job_ids):
                if jid not in pending:
                    continue
                payload = self._request_json("GET", f"/v2/background-jobs/{jid}")
                poll_counts[jid] += 1
                status = None
                if isinstance(payload, dict):
                    status = payload.get("status") or payload.get("job_status") or payload.get("state")

                short_id = (jid[:36] + "…") if len(jid) > 36 else jid
                elapsed = now - parallel_start
                if poll_counts[jid] == 1 or (now - last_hb[jid]) >= 15.0:
                    logger.info(
                        "Pixel Lab parallel poll job=%s status=%r elapsed=%.0fs poll#=%d finished=%d/%d",
                        short_id,
                        status,
                        elapsed,
                        poll_counts[jid],
                        n - len(pending),
                        n,
                    )
                    last_hb[jid] = now

                if status in {"completed", "succeeded", "done", "success"}:
                    if isinstance(payload, dict):
                        results[jid] = _unwrap_completed_job_payload(payload)
                    pending.discard(jid)
                elif status in {"failed", "error"}:
                    raise PixelLabError(
                        "Pixel Lab direction job %d of %d%s failed: %s"
                        % (
                            one_based_index(jid),
                            n,
                            hint_for(jid),
                            format_background_job_failure(payload),
                        )
                    )

            if pending:
                time.sleep(interval_seconds)

        return [results[jid] for jid in job_ids]

    def _poll_jobs_parallel_until_settled(
        self,
        job_ids: List[str],
        *,
        direction_labels: Optional[List[str]] = None,
        timeout_seconds: int = 120,
        interval_seconds: int = 3,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        """
        Poll every job until each completes, fails, or the parallel budget is exhausted.

        Unlike :meth:`_poll_jobs_parallel`, a single direction failing does **not** abort polling
        for the others—so successful jobs can finish while flaky directions are retried separately.
        """
        if not job_ids:
            return {}, {}
        n = len(job_ids)
        total_budget = max(int(timeout_seconds), 1) * n
        parallel_start = time.monotonic()
        deadline = parallel_start + float(total_budget)
        completed: Dict[str, Dict[str, Any]] = {}
        failed: Dict[str, str] = {}
        pending = set(job_ids)
        poll_counts: Dict[str, int] = {j: 0 for j in job_ids}
        last_hb: Dict[str, float] = {j: parallel_start for j in job_ids}

        def hint_for(jid: str) -> str:
            try:
                idx = job_ids.index(jid)
            except ValueError:
                return ""
            if direction_labels and isinstance(direction_labels, list) and idx < len(direction_labels):
                return " (%s)" % direction_labels[idx]
            return ""

        def one_based_index(jid: str) -> int:
            try:
                return job_ids.index(jid) + 1
            except ValueError:
                return -1

        logger.info(
            "Pixel Lab parallel poll (settle-all): %d jobs, budget=%ds (%.0fs wall-clock max)",
            n,
            timeout_seconds,
            total_budget,
        )

        while pending:
            now = time.monotonic()
            if now > deadline:
                for jid in list(pending):
                    failed[jid] = (
                        "Pixel Lab direction job %d of %d%s still pending after %ds (budget exhausted)"
                        % (
                            one_based_index(jid),
                            n,
                            hint_for(jid),
                            int(now - parallel_start),
                        )
                    )
                    logger.warning("Pixel Lab parallel poll: %s", failed[jid])
                    pending.discard(jid)
                break

            for jid in list(job_ids):
                if jid not in pending:
                    continue
                payload = self._request_json("GET", f"/v2/background-jobs/{jid}")
                poll_counts[jid] += 1
                status = None
                if isinstance(payload, dict):
                    status = payload.get("status") or payload.get("job_status") or payload.get("state")

                short_id = (jid[:36] + "…") if len(jid) > 36 else jid
                elapsed = now - parallel_start
                if poll_counts[jid] == 1 or (now - last_hb[jid]) >= 15.0:
                    logger.info(
                        "Pixel Lab parallel poll job=%s status=%r elapsed=%.0fs poll#=%d finished=%d/%d",
                        short_id,
                        status,
                        elapsed,
                        poll_counts[jid],
                        n - len(pending),
                        n,
                    )
                    last_hb[jid] = now

                if status in {"completed", "succeeded", "done", "success"}:
                    if isinstance(payload, dict):
                        completed[jid] = _unwrap_completed_job_payload(payload)
                    pending.discard(jid)
                elif status in {"failed", "error"}:
                    msg = (
                        "Pixel Lab direction job %d of %d%s failed: %s"
                        % (
                            one_based_index(jid),
                            n,
                            hint_for(jid),
                            format_background_job_failure(payload),
                        )
                    )
                    failed[jid] = msg
                    logger.warning("Pixel Lab parallel poll: %s", msg)
                    pending.discard(jid)

            if pending:
                time.sleep(interval_seconds)

        return completed, failed

    def get_balance(self) -> Dict[str, Any]:
        payload = self._request_json("GET", "/v1/balance")
        self._extract_balance_from_payload(payload)
        return payload

    # -----------------------------
    # Helpers
    # -----------------------------
    def encode_image(self, path_or_pil: Union[str, Path, Image.Image]) -> str:
        # PIL Image must be checked before Path: pathlib.Path is not str but is also not Image.
        if isinstance(path_or_pil, Image.Image):
            buf = io.BytesIO()
            # PNG keeps alpha if present.
            path_or_pil.save(buf, format="PNG")
            raw = buf.getvalue()
        else:
            with open(os.fspath(path_or_pil), "rb") as f:
                raw = f.read()
        return base64.b64encode(raw).decode("ascii")

    def decode_image(self, image_b64: str) -> Image.Image:
        raw = base64.b64decode(image_b64)
        return Image.open(io.BytesIO(raw)).convert("RGBA")

    # -----------------------------
    # Concepts / images
    # -----------------------------
    def create_image_pixflux(self, description: str, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "description": description,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        # Endpoint described as v1 in the workbench plan.
        return self._request_json("POST", "/v1/generate-image-pixflux", payload)

    def create_image_v2(self, description: str, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "description": description,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)

        # Pro endpoint is async (background processing).
        accepted = self._request_json("POST", "/v2/generate-image-v2", payload)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id)
        return accepted

    def image_to_pixelart(
        self,
        image_b64: str,
        *,
        input_size: SizeLike,
        output_size: SizeLike,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "image": {"type": "base64", "base64": image_b64, "format": "png"},
            "image_size": _normalize_size(input_size),
            "output_size": _normalize_size(output_size),
        }
        payload.update(kwargs)
        return self._request_json("POST", "/v2/image-to-pixelart", payload)

    # -----------------------------
    # Character creation & retrieval
    # -----------------------------
    def create_character_4dir(self, description: str, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 300))
        payload: Dict[str, Any] = {
            "description": description,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        # v2 character endpoints return a background job (202) — poll if job_id present.
        result = self._request_json("POST", "/v2/create-character-with-4-directions", payload)
        job_id = self._extract_job_id(result)
        if job_id:
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return result

    def create_character_8dir(self, description: str, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 420))
        payload: Dict[str, Any] = {
            "description": description,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        # v2 character endpoints return a background job (202) — poll if job_id present.
        result = self._request_json("POST", "/v2/create-character-with-8-directions", payload)
        job_id = self._extract_job_id(result)
        if job_id:
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return result

    def get_character(self, character_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"/v2/characters/{character_id}")

    def list_characters(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        # urllib doesn't do query building for us here; keep it simple.
        return self._request_json("GET", f"/v2/characters?limit={int(limit)}&offset={int(offset)}")

    def download_character_zip(self, character_id: str) -> bytes:
        return self._request_bytes("GET", f"/v2/characters/{character_id}/zip")

    # -----------------------------
    # Skeleton and animation
    # -----------------------------
    def estimate_skeleton(self, image_b64: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "image": {"type": "base64", "base64": image_b64, "format": "png"},
        }
        return self._request_json("POST", "/v1/estimate-skeleton", payload)

    def _animate_character_post_poll_one_direction(
        self,
        character_id: str,
        template_animation_id: str,
        direction: str,
        poll_timeout: int,
        extra: Dict[str, Any],
        *,
        seed_delta: int = 0,
        log_label: str = "animate_character_serial",
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Single-direction ``POST /v2/characters/animations`` then poll (strict fail on that job).
        ``seed_delta`` perturbs ``extra["seed"]`` when present.
        """
        branch = dict(extra)
        branch["directions"] = [direction]
        if "seed" in branch and branch["seed"] is not None:
            try:
                base = int(branch["seed"])  # type: ignore[arg-type]
                branch["seed"] = (base + int(seed_delta)) % (2**31 - 1)
            except (TypeError, ValueError):
                pass
        payload: Dict[str, Any] = {
            "character_id": character_id,
            "template_animation_id": template_animation_id,
        }
        payload.update(branch)
        logger.info("Pixel Lab %s: POST direction %s", log_label, direction)
        accepted = self._request_json("POST", "/v2/characters/animations", payload)
        _log_pixellab_post_accepted(log_label, accepted)
        job_ids: List[str] = []
        mids = self._extract_background_job_ids(accepted)
        if mids:
            job_ids.extend(mids)
            part = self._poll_jobs_parallel(
                mids,
                direction_labels=[direction],
                timeout_seconds=poll_timeout,
            )
            if part:
                return part[0], job_ids
            return accepted, job_ids
        jid = self._extract_job_id(accepted)
        if jid:
            job_ids.append(jid)
            return self._poll_job(jid, timeout_seconds=poll_timeout), job_ids
        return accepted, job_ids

    def _animate_character_serial_by_direction(
        self,
        character_id: str,
        template_animation_id: str,
        direction_list: List[str],
        poll_timeout: int,
        extra: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        One ``POST /v2/characters/animations`` per direction (avoids flaky multi-job "splitting" on Pixel Lab's side).
        ``extra`` is the same optional fields as the multi-direction call (e.g. ``seed``), without ``directions``.
        """
        merged: List[Dict[str, Any]] = []
        all_job_ids: List[str] = []
        n = len(direction_list)
        for i, d in enumerate(direction_list):
            pl_res, jids = self._animate_character_post_poll_one_direction(
                character_id,
                template_animation_id,
                d,
                poll_timeout,
                extra,
                seed_delta=i * 7919,
                log_label="animate_character serial fallback",
            )
            merged.append(pl_res)
            all_job_ids.extend(jids)
        return merged, all_job_ids

    def animate_character(self, character_id: str, template_animation_id: str, **kwargs: Any) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 420))
        payload: Dict[str, Any] = {
            "character_id": character_id,
            "template_animation_id": template_animation_id,
        }
        payload.update(kwargs)
        logger.info(
            "Pixel Lab animate_character: POST /v2/characters/animations (http timeout=%ds, poll timeout=%ds) — "
            "waiting for API to return job id(s)…",
            self.timeout_seconds,
            poll_timeout,
        )
        accepted = self._request_json("POST", "/v2/characters/animations", payload)
        _log_pixellab_post_accepted("animate_character", accepted)
        multi_ids = self._extract_background_job_ids(accepted)
        if multi_ids:
            dir_labels = accepted.get("directions") or accepted.get("Directions")
            if not isinstance(dir_labels, list):
                dir_labels = None
            direction_list = kwargs.get("directions")
            labels = _direction_labels_aligned(dir_labels, direction_list, len(multi_ids))
            completed, failed_jobs = self._poll_jobs_parallel_until_settled(
                multi_ids,
                direction_labels=labels,
                timeout_seconds=poll_timeout,
            )
            slots: List[Optional[Dict[str, Any]]] = []
            job_ids_out: List[str] = list(multi_ids)
            for jid in multi_ids:
                if jid in completed:
                    slots.append(completed[jid])
                else:
                    slots.append(None)
            retry_pairs = [(i, labels[i]) for i in range(len(multi_ids)) if slots[i] is None]
            if retry_pairs and _pixel_lab_serial_animate_fallback_enabled():
                logger.warning(
                    "Pixel Lab %d/%d direction job(s) failed or timed out (%s); retrying those directions with separate requests.",
                    len(retry_pairs),
                    len(multi_ids),
                    ", ".join(d for (_, d) in retry_pairs),
                )
                extra_base = {k: v for k, v in kwargs.items() if k != "directions"}
                for seq, (slot_idx, direc) in enumerate(retry_pairs):
                    seed_delta = (slot_idx + 1) * 17_000 + (seq + 1) * 99_073
                    pl_res, new_jids = self._animate_character_post_poll_one_direction(
                        character_id,
                        template_animation_id,
                        str(direc),
                        poll_timeout,
                        extra_base,
                        seed_delta=seed_delta,
                        log_label="animate_character serial refill",
                    )
                    slots[slot_idx] = pl_res
                    if new_jids:
                        job_ids_out[slot_idx] = new_jids[0]
            if any(s is None for s in slots):
                miss = [labels[i] for i, s in enumerate(slots) if s is None]
                raise PixelLabError(
                    "Pixel Lab animation incomplete after parallel poll"
                    + (
                        " and serial retries"
                        if retry_pairs and _pixel_lab_serial_animate_fallback_enabled()
                        else ""
                    )
                    + ": missing directions %s. First failures: %s"
                    % (
                        miss,
                        list(failed_jobs.values())[:4] if failed_jobs else "(none)",
                    )
                )
            merged = [s for s in slots if s is not None]
            return {
                "per_job_last_response": merged,
                "directions": accepted.get("directions") or accepted.get("Directions") or direction_list,
                "status": "completed",
                "background_job_ids": job_ids_out,
            }
        job_id = self._extract_job_id(accepted)
        if job_id:
            logger.info("Pixel Lab animate_character single job poll timeout=%ds", poll_timeout)
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return accepted

    def animate_with_text_v2(self, reference_image_b64: str, action: str, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 420))
        payload: Dict[str, Any] = {
            "reference_image": {"type": "base64", "base64": reference_image_b64, "format": "png"},
            "reference_image_size": _normalize_size(image_size),
            "action": action,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        logger.info(
            "Pixel Lab animate_with_text_v2: POST starting (http timeout=%ds, poll timeout=%ds)…",
            self.timeout_seconds,
            poll_timeout,
        )
        accepted = self._request_json("POST", "/v2/animate-with-text-v2", payload)
        _log_pixellab_post_accepted("animate_with_text_v2", accepted)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return accepted

    def animate_with_skeleton(
        self,
        reference_image_b64: str,
        image_size: SizeLike,
        skeleton_keypoints: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 420))
        payload: Dict[str, Any] = {
            "image_size": _normalize_size(image_size),
            "reference_image": {"type": "base64", "base64": reference_image_b64, "format": "png"},
            "skeleton_keypoints": skeleton_keypoints,
        }
        payload.update(kwargs)
        logger.info(
            "Pixel Lab animate_with_skeleton: POST starting (http timeout=%ds, poll timeout=%ds)…",
            self.timeout_seconds,
            poll_timeout,
        )
        accepted = self._request_json("POST", "/v1/animate-with-skeleton", payload)
        _log_pixellab_post_accepted("animate_with_skeleton", accepted)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return accepted

    def interpolation_v2(
        self,
        start_image_b64: str,
        end_image_b64: str,
        action: str,
        image_size: SizeLike,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "start_image": {
                "image": {"type": "base64", "base64": start_image_b64, "format": "png"},
                "size": _normalize_size(image_size),
            },
            "end_image": {
                "image": {"type": "base64", "base64": end_image_b64, "format": "png"},
                "size": _normalize_size(image_size),
            },
            "action": action,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        accepted = self._request_json("POST", "/v2/interpolation-v2", payload)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id)
        return accepted

    # -----------------------------
    # Editing
    # -----------------------------
    def edit_animation_v2(self, description: str, frames: Any, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        poll_timeout = int(kwargs.pop("poll_timeout_seconds", 420))
        payload: Dict[str, Any] = {
            "description": description,
            "frames": frames,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        logger.info(
            "Pixel Lab edit_animation_v2: POST starting (http timeout=%ds, poll timeout=%ds)…",
            self.timeout_seconds,
            poll_timeout,
        )
        accepted = self._request_json("POST", "/v2/edit-animation-v2", payload)
        _log_pixellab_post_accepted("edit_animation_v2", accepted)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id, timeout_seconds=poll_timeout)
        return accepted

    def inpaint_v3(
        self,
        description: str,
        inpainting_image_b64: str,
        mask_image_b64: str,
        image_size: SizeLike,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "description": description,
            "inpainting_image": {
                "image": {"type": "base64", "base64": inpainting_image_b64, "format": "png"},
                "size": _normalize_size(image_size),
            },
            "mask_image": {
                "image": {"type": "base64", "base64": mask_image_b64, "format": "png"},
                "size": _normalize_size(image_size),
            },
        }
        payload.update(kwargs)
        accepted = self._request_json("POST", "/v2/inpaint-v3", payload)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id)
        return accepted

    def transfer_outfit_v2(self, reference_image_b64: str, frames: Any, image_size: SizeLike, **kwargs: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "reference_image": {"type": "base64", "base64": reference_image_b64, "format": "png"},
            "frames": frames,
            "image_size": _normalize_size(image_size),
        }
        payload.update(kwargs)
        accepted = self._request_json("POST", "/v2/transfer-outfit-v2", payload)
        job_id = self._extract_job_id(accepted)
        if job_id:
            return self._poll_job(job_id)
        return accepted

