"""
Unit test for the Condition B loop.

Runs entirely offline: a FakeAnthropicClient plays back a scripted
conversation (propose candidate -> see cost -> try a better candidate ->
finalize) so the calling loop, tool dispatch, and logging can be verified
without a live API key or a real database.

Run with:  python test_condition_b.py
"""

import json
from types import SimpleNamespace

from condition_b import run_condition_b
from mock_estimator import MockCostEstimator


class FakeAnthropicClient:
    """Mimics anthropic.Anthropic().messages.create(...) by replaying a
    fixed script of responses, one per call."""

    def __init__(self, scripted_responses):
        self._responses = list(scripted_responses)
        self._i = 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        response = self._responses[self._i]
        self._i += 1
        return response


def make_tool_use_block(tool_id, name, input_dict):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=input_dict)


def make_response(content_blocks, stop_reason="tool_use"):
    return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)


def build_toy_schema_workload():
    return {
        "schema_name": "toy_test",
        "ddl": "CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, order_date DATE, status TEXT);",
        "queries": [
            {
                "query_id": "Q1",
                "query_text": "SELECT * FROM orders WHERE customer_id = 42 AND order_date > '2026-01-01';",
                "complexity_tier": "Simple",
            }
        ],
    }


def test_full_loop_produces_valid_recommendation():
    scripted_responses = [
        # Turn 1: LLM tries a weak candidate (customer_id only)
        make_response([
            make_tool_use_block("t1", "estimate_index_cost", {
                "table": "orders", "columns": ["customer_id"], "query_id": "Q1"
            })
        ]),
        # Turn 2: LLM tries a better candidate (composite index)
        make_response([
            make_tool_use_block("t2", "estimate_index_cost", {
                "table": "orders", "columns": ["customer_id", "order_date"], "query_id": "Q1"
            })
        ]),
        # Turn 3: LLM finalizes with the composite index
        make_response([
            make_tool_use_block("t3", "finalize_recommendation", {
                "recommended_indexes": [
                    {"table": "orders", "columns": ["customer_id", "order_date"]}
                ],
                "reasoning": "Composite index covers both predicates in Q1's WHERE clause.",
            })
        ], stop_reason="tool_use"),
    ]

    client = FakeAnthropicClient(scripted_responses)
    estimator = MockCostEstimator()
    schema_workload = build_toy_schema_workload()

    result = run_condition_b(schema_workload, estimator, client)

    # -- assertions --
    assert result["condition"] == "B"
    assert result["schema_name"] == "toy_test"
    assert result["recommended_indexes"] == [
        {"table": "orders", "columns": ["customer_id", "order_date"]}
    ]
    assert "reasoning" not in result  # field is llm_reasoning_text, not reasoning
    assert result["llm_reasoning_text"].startswith("Composite index")

    # tool_call_log should have 2 "proposed" entries + 1 "accepted" entry
    decisions = [e["decision"] for e in result["tool_call_log"]]
    assert decisions.count("proposed") == 2
    assert decisions.count("accepted") == 1

    # second proposed candidate should have a lower cost than the first
    proposed_costs = [e["estimated_cost"] for e in result["tool_call_log"] if e["decision"] == "proposed"]
    assert proposed_costs[1] < proposed_costs[0]

    print("PASS: test_full_loop_produces_valid_recommendation")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    test_full_loop_produces_valid_recommendation()
