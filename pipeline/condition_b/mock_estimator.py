"""
Mock cost estimator for unit-testing the Condition B loop against a simple
schema, without needing Postgres/HypoPG or a live LLM. Matches the same
interface as HypoPGCostEstimator so it's a drop-in replacement.
"""


class MockCostEstimator:
    """
    Returns a deterministic, decreasing cost each time a NEW candidate is
    proposed, and the same cost if the same candidate is proposed again --
    just enough behavior to unit-test the calling loop and logging.
    """

    def __init__(self):
        self._seen = {}
        self._next_cost = 1000.0

    def estimate_cost(self, candidate_index: dict, query_text: str) -> dict:
        key = (candidate_index["table"], tuple(candidate_index["columns"]))
        if key not in self._seen:
            self._seen[key] = self._next_cost
            self._next_cost = max(10.0, self._next_cost * 0.4)
        cost = self._seen[key]
        return {
            "estimated_cost": cost,
            "plan_text": f"(mock plan) Index Scan using hypothetical index on {candidate_index['table']}",
        }
