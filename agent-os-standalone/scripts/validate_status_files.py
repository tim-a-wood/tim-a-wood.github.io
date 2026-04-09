#!/usr/bin/env python3
"""
Validate all *-status.json agent dashboard files against the charter directives.

Checks (per docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md):
  SF-1  Required top-level fields present
  SF-2  schema_version == "v1.0"
  SF-3  Priority objects have required fields (id, title, status, risk, note)
  SF-4  priority.status is a valid enum value
  SF-5  priority.risk is a valid enum value
  SF-6  Max 5 non-done priorities
  SF-7  output_location non-null and file exists when last_run is set
  SF-8  proposed_solution present on active/blocked priorities

Usage:
  python3 scripts/validate_status_files.py              # all *-status.json in repo root
  python3 scripts/validate_status_files.py path/to/file.json ...  # specific files
  python3 scripts/validate_status_files.py --warn-only  # exit 0 even on failures
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from scripts.agent_os_roots import WORKSPACE_ROOT

REPO_ROOT = WORKSPACE_ROOT

REQUIRED_TOP_LEVEL = {"schema_version", "updated", "priorities", "actions"}
VALID_STATUSES = {"queued", "in-progress", "needs-review", "paused", "done"}
ACTIVE_STATUSES = {"queued", "in-progress", "needs-review"}
VALID_RISKS = {"low", "med", "high"}


def validate_file(path: Path) -> list[str]:
    """Return a list of violation strings. Empty list = clean."""
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["Root value must be a JSON object"]

    # SF-1: required top-level fields
    missing = REQUIRED_TOP_LEVEL - data.keys()
    if missing:
        errors.append(f"SF-1  Missing required top-level fields: {sorted(missing)}")

    # SF-2: schema_version value
    sv = data.get("schema_version")
    if sv is None:
        errors.append('SF-2  schema_version is absent (must be "v1.0")')
    elif sv != "v1.0":
        errors.append(f'SF-2  schema_version must be "v1.0", got {sv!r}')

    # Validate priorities and opportunities arrays with the same rules
    for array_key in ("priorities", "opportunities"):
        items = data.get(array_key)
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"  {array_key} must be an array")
            continue

        active_count = 0
        for i, item in enumerate(items):
            loc = f"{array_key}[{i}]"
            if not isinstance(item, dict):
                errors.append(f"  {loc} must be an object")
                continue

            # SF-3: required fields
            for field in ("id", "title", "status", "risk", "note"):
                if field not in item:
                    errors.append(f"SF-3  {loc} missing required field '{field}'")
                elif field in ("title", "note"):
                    if not isinstance(item[field], str) or not item[field].strip():
                        errors.append(f"SF-3  {loc}.{field} must be a non-empty string")

            # SF-4: status enum
            status = item.get("status")
            if status is not None and status not in VALID_STATUSES:
                errors.append(
                    f"SF-4  {loc}.status invalid: {status!r} "
                    f"(allowed: {sorted(VALID_STATUSES)})"
                )

            # SF-5: risk enum
            risk = item.get("risk")
            if risk is not None and risk not in VALID_RISKS:
                errors.append(
                    f"SF-5  {loc}.risk invalid: {risk!r} "
                    f"(allowed: {sorted(VALID_RISKS)})"
                )

            # SF-6: count active priorities (only for priorities array, not opportunities)
            if array_key == "priorities" and status in ACTIVE_STATUSES:
                active_count += 1

            # SF-8: proposed_solution on active/blocked priorities
            if status in ACTIVE_STATUSES and array_key == "priorities":
                ps = item.get("proposed_solution")
                if not ps or (isinstance(ps, str) and not ps.strip()):
                    errors.append(
                        f"SF-8  {loc} has active status '{status}' but missing proposed_solution"
                    )

        if array_key == "priorities" and active_count > 5:
            errors.append(
                f"SF-6  {active_count} active priorities (max 5 allowed)"
            )

    # SF-7: output_location set and file exists when last_run is non-null
    actions = data.get("actions")
    if isinstance(actions, list):
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            last_run = action.get("last_run")
            output_loc = action.get("output_location")
            action_id = action.get("id", f"actions[{i}]")
            if last_run is not None:
                if output_loc is None:
                    errors.append(
                        f"SF-7  action '{action_id}' has last_run={last_run!r} "
                        f"but output_location is null"
                    )
                else:
                    target = Path(output_loc) if Path(output_loc).is_absolute() else REPO_ROOT / output_loc
                    if not target.exists():
                        errors.append(
                            f"SF-7  action '{action_id}' output_location does not exist: {output_loc}"
                        )

    return errors


def main(argv: list[str]) -> int:
    warn_only = "--warn-only" in argv
    paths_raw = [a for a in argv if not a.startswith("--")]

    if paths_raw:
        files = [Path(p) for p in paths_raw]
    else:
        files = sorted(REPO_ROOT.glob("*-status.json"))

    if not files:
        print("validate_status_files: no status files found", file=sys.stderr)
        return 0

    total_errors = 0
    for path in files:
        errors = validate_file(path)
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        if errors:
            print(f"\n{rel}  [{len(errors)} violation(s)]")
            for err in errors:
                print(f"  {err}")
            total_errors += len(errors)
        else:
            print(f"{rel}  OK")

    if total_errors:
        print(f"\n{total_errors} violation(s) across {len(files)} file(s).")
        return 0 if warn_only else 1

    print(f"\nAll {len(files)} status file(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
