"""Unit tests for My Actions multi-agent chat helpers in os_dashboard_supervisor."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.os_dashboard_supervisor import (  # noqa: E402
    my_actions_agent_slug_from_status_filename,
    my_actions_collect_relevant_agent_slugs,
)


def test_my_actions_agent_slug_from_status_filename() -> None:
    assert my_actions_agent_slug_from_status_filename("engineering-status.json") == "engineering"
    assert my_actions_agent_slug_from_status_filename("orchestration-status.json") == "orchestrator"
    assert my_actions_agent_slug_from_status_filename("foo/bar/qa-status.json") == "qa"
    assert my_actions_agent_slug_from_status_filename("readme.md") is None
    assert my_actions_agent_slug_from_status_filename("") is None


def test_my_actions_collect_relevant_agent_slugs_order_and_dedupe() -> None:
    ticket: dict = {
        "ownerAgent": "qa",
        "sourceRaw": "eng ld",
        "synthesisSources": ["engineering-status.json"],
    }
    slugs = my_actions_collect_relevant_agent_slugs(ticket)
    assert slugs[0] == "orchestrator"
    assert slugs == ["orchestrator", "qa", "engineering", "level-design"]


if __name__ == "__main__":
    test_my_actions_agent_slug_from_status_filename()
    test_my_actions_collect_relevant_agent_slugs_order_and_dedupe()
    print("ok")
