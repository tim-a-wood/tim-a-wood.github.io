#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import workbench_local_control as wlc


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        projects = root / "tools" / "2d-sprite-and-animation" / "projects-data" / "demo-project"
        projects.mkdir(parents=True)
        payload = {
            "rooms": [
                {
                    "id": "R1",
                    "environment": {
                        "ai_helpfulness": {
                            "suggestions": [
                                {
                                    "decision": {"outcome": "accept"},
                                    "effort": {"preview_views": 2},
                                    "reliability": {"latency_ms": 420, "errors": [], "cancellations": 0, "crashes_near_ai_use": 0},
                                    "persistence": {"status": "persisted"},
                                },
                                {
                                    "decision": {"outcome": "tweak"},
                                    "effort": {"preview_views": 1},
                                    "reliability": {"latency_ms": 780, "errors": [{"message": "x"}], "cancellations": 0, "crashes_near_ai_use": 0},
                                    "persistence": {"status": "superseded"},
                                },
                                {
                                    "decision": {"outcome": "reject"},
                                    "effort": {"preview_views": 0},
                                    "reliability": {"latency_ms": 920, "errors": [], "cancellations": 1, "crashes_near_ai_use": 1},
                                    "persistence": {"status": "pending"},
                                },
                            ]
                        }
                    },
                }
            ]
        }
        (projects / "room_layout.json").write_text(json.dumps(payload), encoding="utf-8")

        original_root = wlc.REPO_ROOT
        try:
            wlc.REPO_ROOT = root
            summary = wlc._build_room_ai_helpfulness_summary()
        finally:
            wlc.REPO_ROOT = original_root

        assert summary["requested"] == 3
        assert summary["decided"] == 3
        assert summary["accepted"] == 1
        assert summary["tweaked"] == 1
        assert summary["rejected"] == 1
        assert summary["persisted"] == 1
        assert summary["helpful_rate_pct"] == 67
        assert summary["persisted_accept_rate_pct"] == 100
        assert summary["error_count"] == 1
        assert summary["cancellation_count"] == 1
        assert summary["crash_count"] == 1
        assert summary["mean_latency_ms"] == 707
        assert isinstance(summary["low_sample_note"], str) and summary["low_sample_note"]
        assert len(summary["donut"]) == 3

    print("room_ai_helpfulness_dashboard.test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
