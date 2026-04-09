#!/usr/bin/env python3
"""Run repeated Agent OS parity checks and persist shadow-run artifacts."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent.parent


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run repeated Agent OS parity checks and persist results.")
    ap.add_argument("--workspace-root", type=Path, default=APP_ROOT, help="MV workspace root")
    ap.add_argument("--iterations", type=int, default=3, help="Number of parity runs")
    ap.add_argument("--pause-sec", type=float, default=2.0, help="Pause between runs")
    ap.add_argument("--artifacts-dir", type=Path, default=APP_ROOT / "artifacts" / "agent-os-shadow", help="Artifact output directory")
    args = ap.parse_args()

    workspace_root = args.workspace_root.expanduser().resolve()
    out_dir = args.artifacts_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"workspace_root": str(workspace_root), "runs": []}
    for idx in range(max(1, args.iterations)):
        stamp = _now_stamp()
        cmd = [
            sys.executable,
            str(APP_ROOT / "scripts" / "compare_agent_os_parity.py"),
            "--workspace-root",
            str(workspace_root),
            "--internal-port",
            str(8770 + idx * 2),
            "--external-port",
            str(8771 + idx * 2),
        ]
        cp = subprocess.run(cmd, capture_output=True, text=True)
        run = {
            "index": idx + 1,
            "timestamp": stamp,
            "returncode": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
        }
        summary["runs"].append(run)
        (out_dir / f"parity-{stamp}-{idx + 1}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
        if cp.returncode != 0:
            break
        if idx + 1 < args.iterations:
            time.sleep(max(0.0, args.pause_sec))

    summary["ok"] = all(int(r["returncode"]) == 0 for r in summary["runs"])
    summary_path = out_dir / f"shadow-summary-{_now_stamp()}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"ok": summary["ok"], "summary": str(summary_path)}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
