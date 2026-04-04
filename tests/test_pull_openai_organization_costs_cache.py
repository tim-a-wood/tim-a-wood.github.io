"""Tests for OpenAI org usage → personal cache helpers."""
from __future__ import annotations

import importlib
import os
import unittest
from datetime import datetime, timezone
from unittest import mock


class PullOpenaiOrganizationCostsCacheTests(unittest.TestCase):
    def test_usage_buckets_add_token_estimate_usd(self):
        mod = importlib.import_module("scripts.pull_openai_organization_costs_cache")
        ts = int(datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        buckets = [
            {
                "start_time": ts,
                "results": [
                    {
                        "object": "organization.usage.completions.result",
                        "num_model_requests": 5,
                        "input_tokens": 1_000_000,
                        "output_tokens": 500_000,
                    }
                ],
            }
        ]
        with mock.patch.dict(
            os.environ,
            {"OPENAI_USAGE_ESTIMATE_USD_PER_M_INPUT": "0.1", "OPENAI_USAGE_ESTIMATE_USD_PER_M_OUTPUT": "0.2"},
            clear=False,
        ):
            entries = mod.usage_buckets_to_ledger_entries(buckets)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["usage"]["rollup_call_count"], 5)
        # 1M * 0.1/1M + 0.5M * 0.2/1M = 0.1 + 0.1 = 0.2
        self.assertAlmostEqual(float(entries[0]["usage_cost_usd"]), 0.2, places=5)
        self.assertEqual(entries[0]["usage"].get("cost_estimate_source"), "token_rates_env")


if __name__ == "__main__":
    unittest.main()
