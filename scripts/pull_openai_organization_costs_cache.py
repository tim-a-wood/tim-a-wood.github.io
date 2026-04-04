#!/usr/bin/env python3
"""
Pull OpenAI **organization** costs into the Agent OS personal usage cache.

Writes ``tools/2d-sprite-and-animation/projects-data/_personal_api_usage_cache.json``
(ledger-compatible ``entries``) so the API Usage dashboard can show USD even when
Cursor / CLI usage never hits the Sprite Workbench ``_usage_ledger.json``.

Auth (try in order):
  OPENAI_ADMIN_API_KEY — recommended (Organization admin key from platform settings)
  OPENAI_API_KEY — may work for some orgs; often returns 403 for organization/costs

Run manually after you add a key, or from cron:

  OPENAI_ADMIN_API_KEY=sk-... python3 scripts/pull_openai_organization_costs_cache.py --days 31

Billing portal remains source of truth; this is a local cache for the dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.workbench_local_control import PERSONAL_USAGE_CACHE_REL, REPO_ROOT as WBC_ROOT  # noqa: E402

OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"


def _pick_api_key() -> str:
    for k in ("OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return ""


def _http_get_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="GET",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_cost_buckets(api_key: str, start_time: int, end_time: int | None) -> list[dict[str, Any]]:
    """Paginate through /v1/organization/costs daily buckets."""
    out: list[dict[str, Any]] = []
    page: str | None = None
    for _ in range(50):
        q: list[tuple[str, str]] = [
            ("start_time", str(start_time)),
            ("bucket_width", "1d"),
            ("limit", "31"),
        ]
        if end_time is not None:
            q.append(("end_time", str(end_time)))
        if page:
            q.append(("page", page))
        url = OPENAI_COSTS_URL + "?" + urllib.parse.urlencode(q)
        body = _http_get_json(url, api_key)
        if not isinstance(body, dict):
            break
        data = body.get("data")
        if not isinstance(data, list):
            break
        out.extend(b for b in data if isinstance(b, dict))
        nxt = body.get("next_page")
        if isinstance(nxt, str) and nxt.strip():
            page = nxt.strip()
            continue
        if body.get("has_more") is True and isinstance(nxt, str) and nxt:
            page = nxt
            continue
        break
    return out


def _bucket_results(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    r = bucket.get("results")
    if isinstance(r, list):
        return [x for x in r if isinstance(x, dict)]
    r2 = bucket.get("result")
    if isinstance(r2, list):
        return [x for x in r2 if isinstance(x, dict)]
    return []


def buckets_to_ledger_entries(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bucket in buckets:
        st = bucket.get("start_time")
        if not isinstance(st, (int, float)):
            continue
        day = datetime.fromtimestamp(int(st), tz=timezone.utc).date().isoformat()
        total_usd = 0.0
        for row in _bucket_results(bucket):
            if str(row.get("object") or "") != "organization.costs.result":
                continue
            amt = row.get("amount")
            if not isinstance(amt, dict):
                continue
            cur = str(amt.get("currency") or "").lower()
            if cur and cur != "usd":
                continue
            try:
                total_usd += float(amt.get("value") or 0)
            except (TypeError, ValueError):
                pass
        if total_usd <= 0:
            continue
        entries.append(
            {
                "created_at": f"{day}T12:00:00.000Z",
                "provider": "openai",
                "endpoint": "organization/costs",
                "status": "success",
                "usage_cost_usd": round(total_usd, 6),
                "source": "openai_organization_costs_cache",
            }
        )
    entries.sort(key=lambda e: str(e.get("created_at") or ""))
    return entries


def write_cache(entries: list[dict[str, Any]], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "openai_organization_costs",
        "entries": entries,
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull OpenAI org costs into Agent OS personal usage cache.")
    ap.add_argument("--days", type=int, default=31, help="Days of history to request (default 31)")
    ap.add_argument(
        "--output",
        type=Path,
        default=WBC_ROOT / PERSONAL_USAGE_CACHE_REL,
        help="Output JSON path",
    )
    args = ap.parse_args()
    key = _pick_api_key()
    if not key:
        print("Set OPENAI_ADMIN_API_KEY or OPENAI_API_KEY.", file=sys.stderr)
        return 2
    days = max(1, min(int(args.days), 366))
    end_ts = int(time.time())
    start_ts = end_ts - days * 86400
    try:
        buckets = fetch_cost_buckets(key, start_ts, end_ts)
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:800]
        print(f"OpenAI HTTP {exc.code}: {err}", file=sys.stderr)
        if exc.code == 403:
            print(
                "Hint: organization costs usually need an admin API key (OPENAI_ADMIN_API_KEY).",
                file=sys.stderr,
            )
        return 1
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    entries = buckets_to_ledger_entries(buckets)
    write_cache(entries, args.output)
    print(f"Wrote {len(entries)} day row(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
