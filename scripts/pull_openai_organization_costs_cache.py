#!/usr/bin/env python3
"""
Pull OpenAI organization **costs** and/or **completions usage** into the Agent OS personal cache.

Writes ``tools/2d-sprite-and-animation/projects-data/_personal_api_usage_cache.json``
(ledger-compatible ``entries``) so the API Usage dashboard can show numbers even when
Cursor / CLI usage never hits the Sprite Workbench ``_usage_ledger.json``.

Strategy:
  1. ``GET /v1/organization/costs`` — daily USD (needs billing/cost scope on the key).
  2. If that yields no rows or fails, ``GET /v1/organization/usage/completions`` —
     daily ``num_model_requests`` + tokens (OpenAI cookbook; often the same admin key).

Auth (try in order):
  OPENAI_ADMIN_API_KEY — create at https://platform.openai.com/settings/organization/admin-keys
  OPENAI_API_KEY — project keys often lack organization usage scopes

Env files (optional, non-destructive: does not override existing shell vars):
  Repo root ``agent_os.env`` then ``.env.local`` (same pattern as the supervisor).

Run:

  python3 scripts/pull_openai_organization_costs_cache.py --days 31

When only completions usage is available, USD is a **token estimate** (tune with
``OPENAI_USAGE_ESTIMATE_USD_PER_M_INPUT`` and ``OPENAI_USAGE_ESTIMATE_USD_PER_M_OUTPUT``).

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
OPENAI_USAGE_COMPLETIONS_URL = "https://api.openai.com/v1/organization/usage/completions"


def _token_estimate_usd(input_tokens: int, output_tokens: int) -> float:
    """
    Rough USD when the Costs API is unavailable: blend using env-tunable $/1M token rates.
    Defaults approximate a small-model tier; override for your actual mix.
    """
    try:
        pin = float((os.environ.get("OPENAI_USAGE_ESTIMATE_USD_PER_M_INPUT") or "0.15").strip() or "0.15")
        pout = float((os.environ.get("OPENAI_USAGE_ESTIMATE_USD_PER_M_OUTPUT") or "0.60").strip() or "0.60")
    except ValueError:
        pin, pout = 0.15, 0.60
    it = max(0, int(input_tokens))
    ot = max(0, int(output_tokens))
    return (it / 1_000_000.0) * pin + (ot / 1_000_000.0) * pout


def _load_repo_env_files() -> None:
    """Populate os.environ from agent_os.env and .env.local when keys are unset."""
    for name in ("agent_os.env", ".env.local"):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("export "):
                s = s[7:].strip()
            if "=" not in s:
                continue
            key, _, val = s.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key or not val or key in os.environ:
                continue
            os.environ[key] = val


def _pick_api_key() -> str:
    for k in ("OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return ""


def _http_get_json(url: str, api_key: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="GET",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


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


def fetch_usage_completions_buckets(api_key: str, start_time: int, end_time: int | None) -> list[dict[str, Any]]:
    """Paginate through /v1/organization/usage/completions (daily buckets)."""
    out: list[dict[str, Any]] = []
    page: str | None = None
    for _ in range(100):
        q: list[tuple[str, str]] = [
            ("start_time", str(start_time)),
            ("bucket_width", "1d"),
            ("limit", "31"),
        ]
        if end_time is not None:
            q.append(("end_time", str(end_time)))
        if page:
            q.append(("page", page))
        url = OPENAI_USAGE_COMPLETIONS_URL + "?" + urllib.parse.urlencode(q)
        body = _http_get_json(url, api_key)
        data = body.get("data")
        if not isinstance(data, list):
            break
        out.extend(b for b in data if isinstance(b, dict))
        nxt = body.get("next_page")
        if isinstance(nxt, str) and nxt.strip():
            page = nxt.strip()
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


def usage_buckets_to_ledger_entries(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One synthetic row per UTC day with rollup_call_count = sum(num_model_requests)."""
    by_day: dict[str, dict[str, int]] = {}
    for bucket in buckets:
        st = bucket.get("start_time")
        if not isinstance(st, (int, float)):
            continue
        day = datetime.fromtimestamp(int(st), tz=timezone.utc).date().isoformat()
        ag = by_day.setdefault(day, {"n": 0, "it": 0, "ot": 0})
        for row in _bucket_results(bucket):
            if str(row.get("object") or "") != "organization.usage.completions.result":
                continue
            try:
                ag["n"] += int(row.get("num_model_requests") or 0)
            except (TypeError, ValueError):
                pass
            try:
                ag["it"] += int(row.get("input_tokens") or 0)
            except (TypeError, ValueError):
                pass
            try:
                ag["ot"] += int(row.get("output_tokens") or 0)
            except (TypeError, ValueError):
                pass

    entries: list[dict[str, Any]] = []
    for day in sorted(by_day.keys()):
        ag = by_day[day]
        nreq = ag["n"]
        if nreq <= 0 and (ag["it"] + ag["ot"]) > 0:
            nreq = 1
        if nreq <= 0:
            continue
        est = _token_estimate_usd(ag["it"], ag["ot"])
        row: dict[str, Any] = {
            "created_at": f"{day}T12:00:00.000Z",
            "provider": "openai",
            "endpoint": "organization/usage/completions",
            "status": "success",
            "usage": {
                "rollup_call_count": nreq,
                "input_tokens": ag["it"],
                "output_tokens": ag["ot"],
                "cost_estimate_source": "token_rates_env",
            },
            "source": "openai_organization_usage_completions_cache",
        }
        if est > 0:
            row["usage_cost_usd"] = round(est, 6)
        entries.append(row)
    return entries


def write_cache(entries: list[dict[str, Any]], dest: Path, *, source: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source,
        "entries": entries,
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    _load_repo_env_files()
    ap = argparse.ArgumentParser(description="Pull OpenAI org costs/usage into Agent OS personal usage cache.")
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
        print("Set OPENAI_ADMIN_API_KEY or OPENAI_API_KEY (or add to agent_os.env / .env.local).", file=sys.stderr)
        return 2
    days = max(1, min(int(args.days), 366))
    end_ts = int(time.time())
    start_ts = end_ts - days * 86400

    entries_cost: list[dict[str, Any]] = []
    try:
        buckets = fetch_cost_buckets(key, start_ts, end_ts)
        entries_cost = buckets_to_ledger_entries(buckets)
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:800]
        print(f"OpenAI costs HTTP {exc.code}: {err}", file=sys.stderr)
        if exc.code == 403:
            print(
                "Your key cannot read organization costs. Fix one of:",
                file=sys.stderr,
            )
            print(
                "  • Organization Admin API key: https://platform.openai.com/settings/organization/admin-keys",
                file=sys.stderr,
            )
            print(
                "  • Or edit your restricted key and enable Usage (scope api.usage.read).",
                file=sys.stderr,
            )
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if entries_cost:
        write_cache(entries_cost, args.output, source="openai_organization_costs")
        print(f"Wrote {len(entries_cost)} priced day row(s) from organization/costs to {args.output}")
        return 0

    print("No priced days from costs API — fetching organization/usage/completions …", file=sys.stderr)
    try:
        ub = fetch_usage_completions_buckets(key, start_ts, end_ts)
        entries_u = usage_buckets_to_ledger_entries(ub)
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:800]
        print(f"OpenAI usage HTTP {exc.code}: {err}", file=sys.stderr)
        if exc.code == 403:
            print(
                "Same scope issue: completions usage also requires api.usage.read on the key.",
                file=sys.stderr,
            )
            print(
                "Create an Organization Admin key or add the Usage permission to your API key.",
                file=sys.stderr,
            )
        return 1
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if entries_u:
        write_cache(entries_u, args.output, source="openai_organization_usage_completions")
        print(
            f"Wrote {len(entries_u)} day row(s) from organization/usage/completions "
            f"(call counts + tokens + token-based USD estimate; set "
            f"OPENAI_USAGE_ESTIMATE_USD_PER_M_INPUT/OUTPUT to tune) to {args.output}"
        )
        return 0

    print(
        "No rows from organization/costs or organization/usage/completions in this window. "
        "Cache file not updated (existing cache left in place).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
