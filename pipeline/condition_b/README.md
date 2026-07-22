# Condition B — Tool-Augmented Index Recommendation

Owner: Alan

## What it does

Given a schema (DDL) and a workload of queries, an LLM proposes candidate
indexes and calls a real cost-estimation tool (`estimate_index_cost`,
backed by Postgres's HypoPG "hypothetical index" feature) before finalizing
its recommendation. The LLM may call the tool as many times as it wants,
trying and discarding candidates. Every call is logged, then the LLM calls
`finalize_recommendation` exactly once to end the loop.

This module's job stops at producing the recommendation + tool call log.
Actually creating the final indexes and re-running `EXPLAIN ANALYZE` is
Ikenna's measurement module's job.

## Files

| File | Purpose |
|---|---|
| `condition_b.py` | Core loop: `run_condition_b(schema_workload, cost_estimator, client)`. Pure logic, no DB/API-specific code — takes the estimator and LLM client as injected dependencies so it's testable offline. |
| `hypopg_estimator.py` | Production cost estimator. Wraps a Postgres connection, uses HypoPG to estimate cost of a candidate index without physically creating it. |
| `mock_estimator.py` | Offline stand-in for `hypopg_estimator.py`, used in unit tests — no DB needed. |
| `test_condition_b.py` | Unit test. Uses a `FakeAnthropicClient` that replays a scripted tool-call conversation, so the whole loop (propose → estimate → iterate → finalize) is verified without a live API key or database. |
| `run.py` | Real entry point for Phase 2 — connects to Postgres, calls the real Anthropic API, writes the final `Recommendation` JSON to disk. |

## Input / Output formats (agreed with team, 2026-07-22)

**Input** — `SchemaWorkload`:
```json
{
  "schema_name": "tpcc",
  "ddl": "CREATE TABLE ...",
  "queries": [
    {"query_id": "Q1", "query_text": "SELECT ...", "complexity_tier": "Simple"}
  ]
}
```

**Output** — `Recommendation` (this is what gets handed to Ikenna's measurement module):
```json
{
  "schema_name": "tpcc",
  "condition": "B",
  "recommended_indexes": [
    {"table": "orders", "columns": ["customer_id", "order_date"]}
  ],
  "llm_reasoning_text": "...",
  "tool_call_log": [
    {"step": 1, "candidate_index": {...}, "estimated_cost": 1234.5, "decision": "proposed", "note": "query_id=Q1", "timestamp": ...},
    {"step": 2, "candidate_index": {...}, "estimated_cost": null, "decision": "accepted", "note": "final recommendation", "timestamp": ...}
  ]
}
```

## How to run standalone

**Unit test (no DB, no API key needed):**
```bash
pip install anthropic psycopg2-binary   # psycopg2 only needed for production path
python test_condition_b.py
```

**Real run against a live schema (Phase 2):**
```bash
pip install anthropic psycopg2-binary
export ANTHROPIC_API_KEY=...

# once per target DB:
psql -d tpcc -c "CREATE EXTENSION IF NOT EXISTS hypopg;"

python run.py schema_workload.json recommendation_out.json
```

## Notes for whoever picks this up (Ikenna's measurement module, integration)

- `recommended_indexes` is a flat list of `{table, columns}` objects — apply
  them as real `CREATE INDEX` statements, then re-run `EXPLAIN ANALYZE` per
  query to get `execution_time_ms_after` for `condition_b_results.csv`.
- `tool_call_log` should be saved as its own `tool_call_log.json` per the
  per-schema deliverable spec (Section 6.2), or inlined as a column if your
  CSV writer handles nested JSON — team agreed a separate file is cleaner.
- Model is pinned via `MODEL` at the top of `condition_b.py` — must match
  whatever Sylfhen's Condition A module uses, and stay the same across both
  schemas, per the assignment's fairness requirement.
- If a schema doesn't support HypoPG (e.g. MySQL for TATP), swap in a
  different estimator implementing the same
  `estimate_cost(candidate_index, query_text) -> {"estimated_cost", "plan_text"}`
  interface — `condition_b.py` doesn't need to change.
