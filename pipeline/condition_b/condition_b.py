"""
Condition B (Tool-Augmented) pipeline component.
Owner: Alan

Given a schema (DDL) and a workload (list of queries), lets an LLM propose
candidate indexes, call a real cost-estimation tool before committing, and
iterate until it finalizes a recommendation. Every tool call is logged.

Shared object formats (agreed with team, 2026-07-22):

SchemaWorkload = {
    "schema_name": str,
    "ddl": str,
    "queries": [{"query_id": str, "query_text": str, "complexity_tier": "Simple"|"Medium"|"Complex"}]
}

Recommendation = {
    "schema_name": str,
    "condition": "B",
    "recommended_indexes": [{"table": str, "columns": [str, ...]}],
    "llm_reasoning_text": str,
    "tool_call_log": [ ... ]   # see ToolCallLogger
}

This module only produces the Recommendation + tool_call_log. Applying the
indexes for real and re-running EXPLAIN ANALYZE is Ikenna's measurement
module's job -- Condition B hands its Recommendation to that module.
"""

import json
import time

MODEL = "claude-sonnet-4-6"  # keep identical across Condition A, B, and both schemas

SYSTEM_PROMPT = (
    "You are a database index-tuning assistant. You will be given a schema "
    "DDL and a workload of queries. Propose indexes that reduce total query "
    "cost. Before finalizing, use the estimate_index_cost tool to check the "
    "real planner cost of each candidate -- do not guess blindly. You may "
    "call the tool as many times as needed, including to reject bad ideas. "
    "When done, call finalize_recommendation exactly once."
)

TOOLS = [
    {
        "name": "estimate_index_cost",
        "description": (
            "Estimate the query planner's cost if a candidate index existed, "
            "WITHOUT actually creating it. Use this to try out index ideas "
            "before committing. Call it as many times as you need."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "query_id": {"type": "string", "description": "id of the query to test cost against"},
            },
            "required": ["table", "columns", "query_id"],
        },
    },
    {
        "name": "finalize_recommendation",
        "description": (
            "Call this ONCE you are done iterating, to submit your final list "
            "of recommended indexes and your reasoning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "recommended_indexes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "table": {"type": "string"},
                            "columns": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["table", "columns"],
                    },
                },
                "reasoning": {"type": "string"},
            },
            "required": ["recommended_indexes", "reasoning"],
        },
    },
]


class ToolCallLogger:
    """Accumulates the full tool-call trace for the deliverable."""

    def __init__(self):
        self.entries = []

    def log(self, step, candidate_index, estimated_cost, decision, note=""):
        self.entries.append({
            "step": step,
            "candidate_index": candidate_index,
            "estimated_cost": estimated_cost,
            "decision": decision,   # "proposed" | "accepted"
            "note": note,
            "timestamp": time.time(),
        })

    def as_json(self):
        return json.dumps(self.entries, indent=2)


def run_condition_b(schema_workload: dict, cost_estimator, client) -> dict:
    """
    schema_workload: SchemaWorkload dict (see module docstring)
    cost_estimator: any object exposing
                     .estimate_cost(candidate_index: dict, query_text: str) -> {"estimated_cost": float, "plan_text": str}
                     (real HypoPG-backed estimator in production, MockCostEstimator in tests)
    client: any object exposing .messages.create(...) matching the Anthropic
            Messages API shape (real anthropic.Anthropic() in production,
            FakeAnthropicClient in tests)

    Returns a Recommendation dict ready to hand to the measurement module.
    """
    logger = ToolCallLogger()
    queries_by_id = {q["query_id"]: q["query_text"] for q in schema_workload["queries"]}

    user_prompt = (
        f"Schema DDL:\n{schema_workload['ddl']}\n\n"
        f"Workload:\n" + "\n".join(
            f"- {q['query_id']} ({q['complexity_tier']}): {q['query_text']}"
            for q in schema_workload["queries"]
        )
    )

    messages = [{"role": "user", "content": user_prompt}]
    step = 0
    final_recommendation = None

    while final_recommendation is None:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            step += 1
            if block.name == "estimate_index_cost":
                candidate = {"table": block.input["table"], "columns": block.input["columns"]}
                query_text = queries_by_id[block.input["query_id"]]
                result = cost_estimator.estimate_cost(candidate, query_text)

                logger.log(step, candidate, result["estimated_cost"], "proposed",
                            note=f"query_id={block.input['query_id']}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            elif block.name == "finalize_recommendation":
                for idx in block.input["recommended_indexes"]:
                    logger.log(step, idx, None, "accepted", note="final recommendation")
                final_recommendation = {
                    "schema_name": schema_workload["schema_name"],
                    "condition": "B",
                    "recommended_indexes": block.input["recommended_indexes"],
                    "llm_reasoning_text": block.input["reasoning"],
                    "tool_call_log": logger.entries,
                }
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Recommendation recorded.",
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        if response.stop_reason != "tool_use" and final_recommendation is None:
            raise RuntimeError("LLM stopped without calling finalize_recommendation")

    return final_recommendation
