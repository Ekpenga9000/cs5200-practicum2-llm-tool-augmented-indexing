# Condition A Module (No-Tool LLM Index Recommendation)

## Inputs
- `schema.sql` — CREATE TABLE DDL for the target schema
- `workload.csv` — columns: query_id, query_text, complexity_tier

## Outputs
- `condition_a_results.csv` — columns: query_id, recommended_indexes,
  llm_reasoning_text, execution_time_ms_after, improvement_vs_baseline
  (last two filled in later by the measurement module)
- `condition_a_results_overall_indexes.txt` — full list of recommended indexes

## How to run standalone
python run_condition_a.py

## Notes
- No `tools` param passed to the API call — this is what makes it Condition A.
- Recommended indexes are validated against the schema DDL; hallucinated
  indexes are logged separately, not silently dropped.