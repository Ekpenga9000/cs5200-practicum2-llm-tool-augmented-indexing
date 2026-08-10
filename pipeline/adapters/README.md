# Adapter Layer

This folder contains the normalization layer that sits between the four shared pipeline modules.

It exists because the repo currently contains multiple incompatible schemas and output conventions:

- Baseline uses one JSON object with `schema_name`, `schema_ddl`, and `workload[]`.
- Condition A uses `schema.sql` plus `workload.csv`.
- Condition B uses one JSON object with `schema_name`, `ddl`, and `queries[]`.
- Recommendation outputs are also split across CSV and JSON variants, with inconsistent field names and sometimes a separate `tool_call_log.json`.

The adapter keeps those modules untouched and translates their inputs and outputs into a consistent shape.

## What it normalizes

### Schema / workload input

Canonical internal form:

```json
{
  "schema_name": "toy_library",
  "schema_ddl": "CREATE TABLE ...",
  "workload": [
    {
      "query_id": "Q1",
      "query_text": "SELECT ...",
      "complexity_tier": "Simple"
    }
  ]
}
```

Supported sources:

- Baseline JSON
- `schema.sql` + `workload.csv`
- Condition B JSON (`ddl` + `queries`)

### Recommendation output

The adapter accepts these variants:

- `condition_a_results.csv`
- `condition_a_recommendation.csv`
- `condition_a_recommendation.json`
- `condition_b_recommendation.json`
- `condition_b_results.csv`
- a Condition B recommendation JSON with a separate `tool_call_log.json`

It preserves a canonical row shape with:

- `query_id`
- `recommended_indexes`
- `llm_reasoning_text`
- `execution_time_ms_after`
- `improvement_vs_baseline`
- `tool_call_log`

When the source is a recommendation JSON with no row-level output, the adapter still writes a normalized recommendation JSON and a best-effort CSV row for compatibility.

## CLI

From this folder:

```bash
npm run adapt -- --mode schema-workload --input ./some-file.json --to baseline --output ./out/
npm run adapt -- --mode schema-workload --input ./some-file.json --to condition_a --output ./out/
npm run adapt -- --mode recommendation --input ./results/Ikenna/dsb/condition_a_recommendation.csv --source condition_a --output ./out/
```

## Smoke test

The smoke test uses real repo fixtures:

- `pipeline/baseline/test-data/toy-library.json`
- `results/Ikenna/dsb/condition_a_recommendation.csv`
- `results/Alan/tpcc/condition_b_recommendation.json`

Run it with:

```bash
npm run smoke-test
```

## Notes

- Missing fields are warned about and left blank or defaulted when possible.
- The adapter is intentionally low risk: it only reads and writes files, and it does not change the teammate-owned modules.