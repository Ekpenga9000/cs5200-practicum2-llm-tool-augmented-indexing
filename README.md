# CS 5200 — Practicum 2: Tool-Augmented Reasoning for Database Index Selection

## Overview

This project investigates whether giving a large language model (LLM) access to a real computational tool — a query-cost estimator (`EXPLAIN`) — improves its database index recommendations compared to reasoning from schema/query text alone.

We compare two conditions across eight real-world database benchmarks:

- **Condition A (No-Tool):** the LLM reasons only from schema DDL and query text.
- **Condition B (Tool-Augmented):** the LLM can call an `estimate_cost()` function (backed by `EXPLAIN`) and iterate before finalizing its recommendation.

All eight benchmark runs use the **same shared pipeline**, built collaboratively in Phase 1, so results are directly comparable across schemas.

## Team & Roles

| Student | Phase 1 Component | Phase 2 Schemas | Theme |
|---|---|---|---|
| Louis | Baseline module | TPC-H, TPC-DS | Analytical / data warehouse |
| Sylfhen | Condition A module (No-Tool) | JOB, STATS | Join-order / cardinality estimation |
| Alan | Condition B module (Tool-Augmented) | TPC-C, TATP | OLTP |
| Ikenna | Measurement & aggregation module | SSB, CEB | Decision-support / cardinality estimation |

## Project Phases

### Phase 1 — Build the Shared Pipeline (Week 1, Jul 15–21)
Each team member builds and unit-tests one pipeline component against a simple test schema (Days 1–4), then the team merges all four components and runs a full end-to-end integration test together (Days 5–7).

**Before any code is written:** the team agrees on shared data formats — the schema/workload object, the recommendation object, and the baseline output format — to avoid integration issues later.

### Phase 2 — Independent Schema Runs (Weeks 2–4)
Once merged, each person runs the exact same shared pipeline against their two assigned benchmarks. This phase is schema setup, running the pipeline, and analysis — not new pipeline code.

Four steps per schema:
1. **Baseline** — set up schema/dataset, run `EXPLAIN ANALYZE` with no extra indexes.
2. **Condition A run** — no-tool LLM recommendations, apply indexes, measure improvement.
3. **Condition B run** — tool-augmented LLM recommendations, save full tool-call log, apply indexes, measure improvement.
4. **Within-schema analysis** — compare A vs. B vs. baseline, write a short summary.

### Week 4 — Cross-Domain Combination
All eight schema results are combined into one team-wide comparison table and joint analysis of whether tool access helps consistently across workload types.

## Repository Structure

```
/pipeline
  /baseline          # Louis — baseline module (EXPLAIN ANALYZE, no extra indexes)
  /condition-a        # Sylfhen — no-tool LLM module
  /condition-b        # Alan — tool-augmented LLM module
  /measurement        # Ikenna — measurement & aggregation module
/results
  /<student_name>/<schema_name>/
    schema.sql                  # DDL for the schema
    workload.csv                # query_id, query_text, complexity_tier
    baseline_results.csv        # query_id, execution_time_ms, query_plan_text
    condition_a_results.csv     # query_id, recommended_indexes, llm_reasoning_text,
                                 # execution_time_ms_after, improvement_vs_baseline
    condition_b_results.csv     # same as condition_a, plus tool_call_log
    tool_call_log.json          # (optional, if not embedded in condition_b_results.csv)
    analysis_summary.md         # half-page write-up: A vs. B vs. baseline
/combined
  combined_results.csv          # all eight schemas side by side
  cross_domain_analysis.md      # Week 4 team analysis
/report
  final_report.md               # 3–5 page consolidated team report
README.md
```

> **Important:** File and column names must be identical across every student's schema submissions. This is what makes the eight schemas combinable in Week 4 — confirm exact naming as a group during the Day 1 kickoff.

## Data Format Conventions

_(To be finalized during Day 1 kickoff — update this section once agreed.)_

- **Schema/workload object:** TBD
- **Recommendation object:** TBD
- **Baseline output format:** TBD

## Deliverables Checklist

- [ ] Phase 1: component source code + README (inputs, outputs, how to run standalone) — per component owner
- [ ] Phase 1: documented input/output data format
- [ ] Schema 1 (Week 2): full per-schema deliverable folder, per student
- [ ] Schema 2 (Week 3): full per-schema deliverable folder, per student
- [ ] Week 4: combined spreadsheet/table + cross-domain analysis
- [ ] Final team report (3–5 pages)

## Timeline

| Week | Dates | Milestone |
|---|---|---|
| 1 | Jul 15 – Jul 21 | Phase 1: build components, merge, integration test |
| 2 | Jul 22 | Run pipeline on Schema 1 |
| — | Jul 23 – Jul 26 | Practicum 2 Demo |
| 3 | Jul 27 – Jul 31 | Run pipeline on Schema 2 |
| 4 | Aug 1 – Aug 3 | Combine all eight results; final report |

## Notes

- Use the same LLM (model and version) across both conditions and both schemas per student — only tool access should differ between A and B.
- Keep all reasoning traces and tool-call logs; they're valuable data, not just intermediate output.
- Commit early and often — avoid a single large upload at the end.
- Flag any benchmark access/setup problems immediately rather than losing time on workarounds.
