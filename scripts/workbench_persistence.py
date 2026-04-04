from __future__ import annotations

import copy
import io
import json
import math
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


PROJECTS_ROOT: Path
PROJECT_SCHEMA_VERSION: int
PROJECT_BUNDLE_MANIFEST_VERSION: int
PROJECT_HEALTH_REPORT_VERSION: int
PROJECT_BUNDLE_MANIFEST_FILENAME: str
PROJECT_HEALTH_REPORT_FILENAME: str
WORKBENCH_SETTINGS_FILENAME: str
USAGE_LEDGER_FILENAME: str
ROOM_LAYOUT_FILENAME: str
ROOM_LAYOUT_HISTORY_FILENAME: str
LEVEL_VALIDATION_REPORT_FILENAME: str
TOOL_VERSION: str
WORKBENCH_SETTINGS_DEFAULTS: Dict[str, Any]
USAGE_LEDGER_LIMIT: int

now_iso: Callable[[], str]
slugify: Callable[[str], str]


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def project_bundle_manifest_path(project_dir: Path) -> Path:
    return project_dir / PROJECT_BUNDLE_MANIFEST_FILENAME


def project_health_report_path(project_dir: Path) -> Path:
    return project_dir / PROJECT_HEALTH_REPORT_FILENAME


def workbench_settings_path() -> Path:
    return PROJECTS_ROOT / WORKBENCH_SETTINGS_FILENAME


def usage_ledger_path() -> Path:
    return PROJECTS_ROOT / USAGE_LEDGER_FILENAME


def room_layout_path(project_dir: Path) -> Path:
    return project_dir / ROOM_LAYOUT_FILENAME


def room_layout_history_path(project_dir: Path) -> Path:
    return project_dir / ROOM_LAYOUT_HISTORY_FILENAME


def level_validation_report_path(project_dir: Path) -> Path:
    return project_dir / LEVEL_VALIDATION_REPORT_FILENAME


def _artifact_kind_for_path(rel_path: Path) -> str:
    head = rel_path.parts[0] if rel_path.parts else ""
    if rel_path.name == "project.json":
        return "project_core"
    if rel_path.suffix.lower() == ".json":
        if head == "concepts":
            return "concept_metadata"
        if head == "animations":
            return "animation_metadata"
        return "metadata"
    if head == "concepts":
        return "concept_asset"
    if head == "character":
        return "character_asset"
    if head == "animations":
        return "animation_asset"
    if head == "references":
        return "reference_asset"
    if head == "exports":
        return "export_asset"
    return head or "asset"


def iter_project_artifact_paths(project_dir: Path) -> List[Path]:
    manifest_path = project_bundle_manifest_path(project_dir)
    artifacts: List[Path] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        if path == manifest_path or path.name == ".DS_Store":
            continue
        artifacts.append(path)
    return artifacts


def build_project_bundle_manifest(project_dir: Path, project: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = []
    for path in iter_project_artifact_paths(project_dir):
        stat = path.stat()
        rel_path = path.relative_to(project_dir)
        artifacts.append({
            "path": rel_path.as_posix(),
            "kind": _artifact_kind_for_path(rel_path),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return {
        "manifest_version": PROJECT_BUNDLE_MANIFEST_VERSION,
        "project_id": project.get("project_id") or project_dir.name,
        "project_schema_version": int(project.get("project_schema_version") or PROJECT_SCHEMA_VERSION),
        "tool_version": TOOL_VERSION,
        "generated_at": now_iso(),
        "project_name": project.get("project_name") or project_dir.name,
        "selected_concept_id": project.get("selected_concept_id"),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def _health_issue(
    issue_type: str,
    path_value: str,
    *,
    detail: Optional[str] = None,
    concept_id: Optional[str] = None,
    animation_name: Optional[str] = None,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    issue = {"type": issue_type, "path": path_value}
    if detail:
        issue["detail"] = detail
    if concept_id:
        issue["concept_id"] = concept_id
    if animation_name:
        issue["animation_name"] = animation_name
    if direction:
        issue["direction"] = direction
    return issue


def build_project_health_report(project: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    missing_files: List[Dict[str, Any]] = []
    warnings: List[str] = []
    seen_missing: Set[Tuple[str, str]] = set()

    def record_missing(issue_type: str, raw_path: Any, **extra: Any) -> None:
        if not raw_path:
            return
        path_text = str(raw_path)
        candidate = Path(path_text)
        resolved = candidate if candidate.is_absolute() else (project_dir / candidate)
        if resolved.exists():
            return
        key = (issue_type, path_text)
        if key in seen_missing:
            return
        seen_missing.add(key)
        missing_files.append(_health_issue(issue_type, path_text, **extra))

    concepts = project.get("concepts") or []
    selected_id = project.get("selected_concept_id")
    selected = next((item for item in concepts if item.get("concept_id") == selected_id), None) if selected_id else None
    if selected_id and selected is None:
        warnings.append("selected_concept_record_missing")
    for concept in concepts:
        concept_id = concept.get("concept_id")
        for field in ("preview_image", "original_preview_image", "processed_preview_image", "approved_source_image"):
            record_missing(
                "concept_asset_missing",
                concept.get(field),
                detail=field,
                concept_id=concept_id,
            )

    char_data = project.get("pixellab_character")
    if isinstance(char_data, dict):
        images = char_data.get("images") or {}
        if isinstance(images, dict):
            for direction, rel_path in images.items():
                record_missing(
                    "character_direction_image_missing",
                    rel_path,
                    detail="pixellab_character.images",
                    direction=str(direction),
                )

    pix_store = project.get("pixellab_animations")
    if isinstance(pix_store, dict):
        animations = pix_store.get("animations") or {}
        if isinstance(animations, dict):
            for animation_name, meta in animations.items():
                directions = (meta or {}).get("directions") or {}
                if not isinstance(directions, dict):
                    continue
                for direction, direction_meta in directions.items():
                    frames = (direction_meta or {}).get("frames") or []
                    if not isinstance(frames, list):
                        continue
                    for rel_path in frames:
                        record_missing(
                            "animation_frame_missing",
                            rel_path,
                            animation_name=str(animation_name),
                            direction=str(direction),
                        )

    last_export = project.get("last_export") or {}
    if isinstance(last_export, dict):
        export_dir = last_export.get("export_dir")
        if export_dir and not (project_dir / str(export_dir)).exists():
            warnings.append("last_export_directory_missing")
            record_missing("last_export_missing", export_dir, detail="last_export.export_dir")

    recommended_actions: List[str] = []
    if any(item["type"] == "concept_asset_missing" for item in missing_files):
        recommended_actions.append("relink_or_regenerate_concept_assets")
    if any(item["type"] == "character_direction_image_missing" for item in missing_files):
        recommended_actions.append("rebuild_or_reimport_character_assets")
    if any(item["type"] == "animation_frame_missing" for item in missing_files):
        recommended_actions.append("regenerate_or_repair_animation_frames")
    if any(item["type"] == "last_export_missing" for item in missing_files):
        recommended_actions.append("rerun_export_to_refresh_output_bundle")
    if "selected_concept_record_missing" in warnings:
        recommended_actions.append("reselect_or_reapprove_a_concept")

    room_validation = project.get("level_validation_report") or {}
    if isinstance(room_validation, dict):
        room_status = str(room_validation.get("status") or "").lower()
        if room_status == "fail":
            warnings.append("room_layout_validation_failed")
            recommended_actions.append("repair_room_layout")
        elif room_status == "warning":
            warnings.append("room_layout_validation_warning")

    status = "pass" if not missing_files and not warnings else "warning"
    return {
        "report_version": PROJECT_HEALTH_REPORT_VERSION,
        "project_id": project.get("project_id") or project_dir.name,
        "project_schema_version": int(project.get("project_schema_version") or PROJECT_SCHEMA_VERSION),
        "tool_version": TOOL_VERSION,
        "checked_at": now_iso(),
        "status": status,
        "missing_files": missing_files,
        "warnings": warnings,
        "recommended_actions": recommended_actions,
        "repair_actions_taken": [],
        "summary": {
            "concept_count": len(concepts),
            "missing_file_count": len(missing_files),
            "warning_count": len(warnings),
        },
    }


def persist_project_integrity_metadata(project: Dict[str, Any], project_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    health = build_project_health_report(project, project_dir)
    write_json(project_health_report_path(project_dir), health)
    manifest = build_project_bundle_manifest(project_dir, project)
    write_json(project_bundle_manifest_path(project_dir), manifest)
    return health, manifest


def load_project_health_summary(project_dir: Path) -> Dict[str, Any]:
    report = load_json(project_health_report_path(project_dir), None)
    if not isinstance(report, dict):
        return {"status": "unknown", "warning_count": 0, "missing_file_count": 0}
    summary = report.get("summary") or {}
    return {
        "status": report.get("status", "unknown"),
        "warning_count": int(summary.get("warning_count") or 0),
        "missing_file_count": int(summary.get("missing_file_count") or 0),
    }


def project_backup_filename(project: Dict[str, Any]) -> str:
    base = slugify(project.get("project_name") or project.get("project_id") or "sprite-workbench-project")
    return "%s.spriteworkbench.zip" % (base or "sprite-workbench-project")


def load_workbench_settings() -> Dict[str, Any]:
    payload = load_json(workbench_settings_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    normalized = dict(WORKBENCH_SETTINGS_DEFAULTS)
    normalized["safe_mode"] = bool(payload.get("safe_mode", normalized["safe_mode"]))
    normalized["confirm_paid_actions"] = bool(payload.get("confirm_paid_actions", normalized["confirm_paid_actions"]))
    normalized["updated_at"] = payload.get("updated_at")
    return normalized


def save_workbench_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = load_workbench_settings()
    current.update({
        "safe_mode": bool(payload.get("safe_mode", current["safe_mode"])),
        "confirm_paid_actions": bool(payload.get("confirm_paid_actions", current["confirm_paid_actions"])),
        "updated_at": now_iso(),
    })
    write_json(workbench_settings_path(), current)
    return current


def load_usage_ledger() -> Dict[str, Any]:
    payload = load_json(usage_ledger_path(), None)
    if not isinstance(payload, dict):
        payload = {"entries": []}
    payload.setdefault("entries", [])
    if not isinstance(payload["entries"], list):
        payload["entries"] = []
    return payload


def _coerce_usage_cost_usd(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def append_usage_ledger_entry(
    *,
    provider: str,
    endpoint: str,
    project_id: Optional[str] = None,
    status: str = "success",
    usage: Optional[Dict[str, Any]] = None,
    usage_cost_usd: Any = None,
    job_id: Optional[str] = None,
    generation_id: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ledger = load_usage_ledger()
    usage_obj = dict(usage) if isinstance(usage, dict) else None
    inferred_cost = _coerce_usage_cost_usd(usage_cost_usd)
    if inferred_cost is None and usage_obj:
        inferred_cost = (
            _coerce_usage_cost_usd(usage_obj.get("usage_cost_usd"))
            or _coerce_usage_cost_usd(usage_obj.get("cost_usd"))
            or _coerce_usage_cost_usd(usage_obj.get("usd"))
        )
    entry = {
        "entry_id": uuid.uuid4().hex[:12],
        "created_at": now_iso(),
        "provider": provider,
        "endpoint": endpoint,
        "project_id": project_id,
        "status": status,
        "usage_cost_usd": inferred_cost,
        "job_id": job_id,
        "generation_id": generation_id,
        "error": error,
        "usage": usage_obj,
        "metadata": metadata or {},
    }
    ledger["entries"].append(entry)
    if len(ledger["entries"]) > USAGE_LEDGER_LIMIT:
        ledger["entries"] = ledger["entries"][-USAGE_LEDGER_LIMIT:]
    write_json(usage_ledger_path(), ledger)
    return entry


def summarize_usage_ledger_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    today_prefix = datetime.now(timezone.utc).date().isoformat()
    recent = entries[-10:]
    today_entries = [item for item in entries if str(item.get("created_at") or "").startswith(today_prefix)]

    def _total(items: List[Dict[str, Any]]) -> float:
        return round(sum(_coerce_usage_cost_usd(item.get("usage_cost_usd")) or 0.0 for item in items), 4)

    return {
        "entry_count": len(entries),
        "today_entry_count": len(today_entries),
        "today_usage_cost_usd": _total(today_entries),
        "total_usage_cost_usd": _total(entries),
        "recent_entries": recent,
    }


def summarize_usage_ledger() -> Dict[str, Any]:
    ledger = load_usage_ledger()
    entries = [item for item in ledger.get("entries", []) if isinstance(item, dict)]
    return summarize_usage_ledger_entries(entries)


def _parse_iso_datetime_utc(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _monday_start_utc(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    d = dt.date()
    monday = d - timedelta(days=d.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)


def _iso_week_label(monday_utc: datetime) -> str:
    d = monday_utc.astimezone(timezone.utc).date()
    iw = d.isocalendar()
    return f"{iw[0]}-W{iw[1]:02d}"


def _normalize_usage_provider_key(provider: Any) -> str:
    raw = str(provider or "").strip().lower().replace(" ", "_").replace("-", "_")
    return raw if raw else "unlabeled"


def _usage_provider_display_label(key: str) -> str:
    labels = {
        "pixellab": "Pixel Lab",
        "gemini": "Google Gemini",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "unlabeled": "Unlabeled provider",
    }
    if key in labels:
        return labels[key]
    if not key:
        return "Unlabeled provider"
    return key.replace("_", " ").title()


def build_usage_cost_rollups_from_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Per-day counts by provider for every ledger row with a valid ``created_at``.
    USD totals are added only when ``usage_cost_usd`` (or nested ``usage`` cost hints) is > 0.

    Many vendors omit USD in API responses; the Agent OS table still shows call counts so the
    dashboard is not blank when prices are unknown.
    """
    daily_cost: Dict[str, Dict[str, float]] = {}
    daily_n: Dict[str, Dict[str, int]] = {}
    all_time_cost: Dict[str, float] = {}
    all_time_calls: Dict[str, int] = {}

    for item in entries:
        if not isinstance(item, dict):
            continue
        created = _parse_iso_datetime_utc(item.get("created_at"))
        if created is None:
            continue
        raw_prov = item.get("provider")
        pk = _normalize_usage_provider_key(raw_prov) if raw_prov is not None and str(raw_prov).strip() != "" else "unlabeled"

        usage_obj = item.get("usage") if isinstance(item.get("usage"), dict) else None
        cost = _coerce_usage_cost_usd(item.get("usage_cost_usd"))
        if cost is None and usage_obj:
            cost = (
                _coerce_usage_cost_usd(usage_obj.get("usage_cost_usd"))
                or _coerce_usage_cost_usd(usage_obj.get("cost_usd"))
                or _coerce_usage_cost_usd(usage_obj.get("usd"))
            )

        d_str = created.astimezone(timezone.utc).date().isoformat()
        daily_n.setdefault(d_str, {})
        daily_n[d_str][pk] = daily_n[d_str].get(pk, 0) + 1
        all_time_calls[pk] = all_time_calls.get(pk, 0) + 1

        if cost is not None and cost > 0:
            daily_cost.setdefault(d_str, {})
            daily_cost[d_str][pk] = daily_cost[d_str].get(pk, 0.0) + float(cost)
            all_time_cost[pk] = all_time_cost.get(pk, 0.0) + float(cost)

    all_dates = sorted(set(daily_n.keys()) | set(daily_cost.keys()))
    daily_list: List[Dict[str, Any]] = []
    for d_str in all_dates:
        c_src = daily_cost.get(d_str, {})
        n_src = daily_n.get(d_str, {})
        pks = sorted(set(c_src.keys()) | set(n_src.keys()))
        c_map = {k: round(c_src[k], 4) for k in pks if c_src.get(k, 0.0) > 0}
        n_map = {k: int(n_src.get(k, 0)) for k in pks}
        daily_list.append({"d": d_str, "c": c_map, "n": n_map})

    prov_rows: List[Dict[str, Any]] = []
    for pk in sorted(all_time_calls.keys(), key=lambda k: (-all_time_cost.get(k, 0.0), -all_time_calls[k], k)):
        prov_rows.append(
            {
                "key": pk,
                "label": _usage_provider_display_label(pk),
                "all_time_cost_usd": round(all_time_cost.get(pk, 0.0), 4),
                "all_time_paid_calls": all_time_calls[pk],
            }
        )

    ledger_row_count = sum(1 for item in entries if isinstance(item, dict))
    dated_row_count = sum(
        1
        for item in entries
        if isinstance(item, dict) and _parse_iso_datetime_utc(item.get("created_at")) is not None
    )

    return {
        "version": 1,
        "daily": daily_list,
        "providers": prov_rows,
        "ledger_row_count": ledger_row_count,
        "dated_row_count": dated_row_count,
    }


def build_usage_ledger_charts_from_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Roll up usage ledger rows into shapes consumed by Agent OS (os-dashboard.html).

    KPIs (8-week rolling window, UTC, ISO weeks):
    - area_requests: count of ledger rows per week (paid API calls recorded in _usage_ledger.json).
    - purpose_bars: share by provider/route bucket (Pixel Lab vs Gemini vs Room AI vs other).
    - donut: API outcome mix (success vs error vs other status) — not Copilot accept/revise until instrumented.
    """
    now = datetime.now(timezone.utc)
    this_monday = _monday_start_utc(now)
    week_starts: List[datetime] = [this_monday - timedelta(weeks=(7 - i)) for i in range(8)]
    window_start = week_starts[0]
    window_end = week_starts[7]

    filtered: List[Dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        created = _parse_iso_datetime_utc(item.get("created_at"))
        if created is None:
            continue
        wk = _monday_start_utc(created)
        if wk < window_start or wk > window_end:
            continue
        filtered.append(item)

    area_counts = [0] * 8
    purpose_counts = {"pixel_lab": 0, "gemini": 0, "openai": 0, "room_ai": 0, "other": 0}
    outcome_counts = {"success": 0, "error": 0, "other": 0}

    for item in filtered:
        wm = _monday_start_utc(_parse_iso_datetime_utc(item.get("created_at")) or now)
        try:
            idx = week_starts.index(wm)
        except ValueError:
            continue
        area_counts[idx] += 1

        prov = str(item.get("provider") or "").lower()
        ep = str(item.get("endpoint") or "").lower()
        if prov == "pixellab":
            purpose_counts["pixel_lab"] += 1
        elif prov == "gemini":
            purpose_counts["gemini"] += 1
        elif prov == "openai":
            purpose_counts["openai"] += 1
        elif "room" in ep or "layout" in ep or "copilot" in ep or "environment" in ep:
            purpose_counts["room_ai"] += 1
        else:
            purpose_counts["other"] += 1

        st = str(item.get("status") or "").lower()
        if st == "success":
            outcome_counts["success"] += 1
        elif st == "error":
            outcome_counts["error"] += 1
        else:
            outcome_counts["other"] += 1

    area_labels = [_iso_week_label(ws) for ws in week_starts]
    window_n = len(filtered)
    total_purpose = sum(purpose_counts.values()) or 1

    def _pct(part: int) -> int:
        return int(round(100.0 * float(part) / float(total_purpose)))

    purpose_bars = [
        {"label": "Pixel Lab", "value": _pct(purpose_counts["pixel_lab"]), "key": "good", "count": purpose_counts["pixel_lab"]},
        {"label": "Gemini", "value": _pct(purpose_counts["gemini"]), "key": "accent", "count": purpose_counts["gemini"]},
        {"label": "OpenAI", "value": _pct(purpose_counts["openai"]), "key": "good", "count": purpose_counts["openai"]},
        {"label": "Room AI", "value": _pct(purpose_counts["room_ai"]), "key": "warning", "count": purpose_counts["room_ai"]},
        {"label": "Other", "value": _pct(purpose_counts["other"]), "key": "muted", "count": purpose_counts["other"]},
    ]

    oc = outcome_counts
    total_o = oc["success"] + oc["error"] + oc["other"]
    if total_o == 0:
        donut = [
            {"label": "No calls (window)", "value": 100, "key": "muted", "count": 0},
        ]
        donut_n = 0
    else:
        donut = [
            {"label": "Success", "value": int(round(100.0 * oc["success"] / total_o)), "key": "good", "count": oc["success"]},
            {"label": "Error", "value": int(round(100.0 * oc["error"] / total_o)), "key": "warning", "count": oc["error"]},
            {"label": "Other", "value": int(round(100.0 * oc["other"] / total_o)), "key": "accent", "count": oc["other"]},
        ]
        donut_n = total_o

    eight_week_total = sum(area_counts)

    raw_entries = [item for item in entries if isinstance(item, dict)]

    return {
        "version": 1,
        "window_weeks": 8,
        "window_label_utc": "last_8_iso_weeks",
        "area_labels": area_labels,
        "area_requests": area_counts,
        "purpose_bars": purpose_bars,
        "donut": donut,
        "donut_n": donut_n,
        "ledger_entry_count_window": window_n,
        "eight_week_call_total": eight_week_total,
        "cost_rollups": build_usage_cost_rollups_from_entries(raw_entries),
    }


def summarize_usage_ledger_charts() -> Dict[str, Any]:
    ledger = load_usage_ledger()
    raw = [item for item in ledger.get("entries", []) if isinstance(item, dict)]
    return build_usage_ledger_charts_from_entries(raw)


def provider_call_allowed() -> None:
    settings = load_workbench_settings()
    if settings.get("safe_mode"):
        raise ValueError("Safe mode is enabled. Turn it off in the Safety panel before running paid generation actions.")


def default_room_layout(project_id: str, project_name: str = "Untitled Project") -> Dict[str, Any]:
    return {
        "version": 1,
        "meta": {
            "project_id": project_id,
            "project_name": project_name,
            "source": "sprite_workbench",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "notes": "Project-scoped room layout source of truth for the Room Creation tool.",
        },
        "rooms": [
            {
                "id": "R1",
                "name": "Room 1",
                "size": {"width": 1600, "height": 1200},
                "global": {"x": 600, "y": 360},
                "polygon": [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
                "platforms": [
                    {"id": "R1-P1", "x": 192, "y": 992, "len": 38, "tint": 0},
                ],
                "movingPlatforms": [],
                "doors": [],
                "keys": [],
                "abilities": [],
                "playerStart": {"x": 320, "y": 928},
                "edgeLinks": [],
                "removedEdges": [],
            }
        ],
    }


def default_room_layout_history(project_id: str, layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": "initial",
        "revisions": [
            {
                "revision_id": "initial",
                "created_at": now_iso(),
                "summary": "Initial room layout scaffold",
                "room_count": len((layout or {}).get("rooms") or []),
            }
        ],
    }


def _room_layout_point_valid(point: Any) -> bool:
    return (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(isinstance(value, (int, float)) for value in point)
    )


def validate_room_layout(layout: Any) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    room_index_by_id: Dict[str, Dict[str, Any]] = {}
    room_ids: List[str] = []

    if not isinstance(layout, dict):
        return {
            "status": "fail",
            "errors": ["Layout payload must be a JSON object."],
            "warnings": [],
            "summary": {"room_count": 0, "door_count": 0, "platform_count": 0, "linked_edge_count": 0},
            "checked_at": now_iso(),
        }

    rooms = layout.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        errors.append("Layout must contain a non-empty rooms array.")
        rooms = []

    platform_count = 0
    door_count = 0
    linked_edge_count = 0

    for idx, room in enumerate(rooms):
        if not isinstance(room, dict):
            errors.append("Room %d must be an object." % (idx + 1))
            continue
        room_id = str(room.get("id") or "").strip()
        if not room_id:
            errors.append("Room %d is missing an id." % (idx + 1))
            continue
        if room_id in room_index_by_id:
            errors.append("Room id %s is duplicated." % room_id)
            continue
        room_index_by_id[room_id] = room
        room_ids.append(room_id)

        polygon = room.get("polygon")
        if not isinstance(polygon, list) or len(polygon) < 3 or not all(_room_layout_point_valid(point) for point in polygon):
            errors.append("Room %s must have a polygon with at least three numeric points." % room_id)

        global_pos = room.get("global")
        if not isinstance(global_pos, dict) or not isinstance(global_pos.get("x"), (int, float)) or not isinstance(global_pos.get("y"), (int, float)):
            errors.append("Room %s must define numeric global.x and global.y." % room_id)

        player_start = room.get("playerStart")
        if player_start is None:
            warnings.append("Room %s has no playerStart." % room_id)
        elif not isinstance(player_start, dict) or not isinstance(player_start.get("x"), (int, float)) or not isinstance(player_start.get("y"), (int, float)):
            errors.append("Room %s playerStart must contain numeric x/y." % room_id)

        platforms = room.get("platforms") or []
        if not isinstance(platforms, list):
            errors.append("Room %s platforms must be a list." % room_id)
        else:
            platform_count += len(platforms)

        doors = room.get("doors") or []
        if not isinstance(doors, list):
            errors.append("Room %s doors must be a list." % room_id)
        else:
            door_count += len(doors)

        edge_links = room.get("edgeLinks") or []
        if not isinstance(edge_links, list):
            errors.append("Room %s edgeLinks must be a list." % room_id)
            continue
        for link in edge_links:
            if not isinstance(link, dict):
                errors.append("Room %s edge link entries must be objects." % room_id)
                continue
            edge_index = link.get("edgeIndex")
            target_room_id = str(link.get("targetRoomId") or "").strip()
            target_edge_index = link.get("targetEdgeIndex")
            if not isinstance(edge_index, int) or edge_index < 0 or (isinstance(polygon, list) and edge_index >= len(polygon)):
                errors.append("Room %s has an invalid edgeIndex in edgeLinks." % room_id)
            if not target_room_id:
                errors.append("Room %s edge link is missing targetRoomId." % room_id)
            if not isinstance(target_edge_index, int) or target_edge_index < 0:
                errors.append("Room %s edge link to %s has an invalid targetEdgeIndex." % (room_id, target_room_id or "unknown"))
            linked_edge_count += 1

    for room_id, room in room_index_by_id.items():
        target_polygon_counts = {rid: len((room_index_by_id.get(rid) or {}).get("polygon") or []) for rid in room_index_by_id}
        for link in room.get("edgeLinks") or []:
            target_room_id = str(link.get("targetRoomId") or "").strip()
            if target_room_id and target_room_id not in room_index_by_id:
                errors.append("Room %s links to missing target room %s." % (room_id, target_room_id))
                continue
            if target_room_id:
                target_edge_index = link.get("targetEdgeIndex")
                target_polygon_len = target_polygon_counts.get(target_room_id, 0)
                if isinstance(target_edge_index, int) and target_polygon_len and target_edge_index >= target_polygon_len:
                    errors.append("Room %s links to out-of-range edge %s on %s." % (room_id, target_edge_index, target_room_id))

    status = "pass"
    if errors:
        status = "fail"
    elif warnings:
        status = "warning"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "room_count": len(room_ids),
            "door_count": door_count,
            "platform_count": platform_count,
            "linked_edge_count": linked_edge_count,
        },
        "checked_at": now_iso(),
    }


def room_layout_wizard_complete(project: Dict[str, Any]) -> bool:
    history = project.get("room_layout_history") or {}
    validation = project.get("level_validation_report") or {}
    current_revision_id = str(history.get("current_revision_id") or "").strip()
    if not current_revision_id or current_revision_id == "initial":
        return False
    return str(validation.get("status") or "").lower() != "fail"
