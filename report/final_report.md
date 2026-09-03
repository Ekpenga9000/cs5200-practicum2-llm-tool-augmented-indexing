# Final Team Report — Practicum 2

## Tool-Augmented Reasoning for Database Index Selection

### Team
- Louis: Baseline module; TPC-H + TPC-DS
- Sylfhen: Condition A module; JOB + STATS
- Alan: Condition B module; TPC-C + TATP
- Ikenna: Measurement module; SSB + DSB

## 1. Problem Statement and Goal
The objective of this practicum was to test whether an LLM that can use a real database cost-estimation tool produces better index recommendations than an LLM reasoning from schema and query text alone.

We evaluated two conditions:
- Condition A (No-Tool): the model recommends indexes directly from DDL and workload text.
- Condition B (Tool-Augmented): the model iteratively proposes candidate indexes, evaluates estimated plan cost through a real tool call, and then finalizes recommendations.

The core research question was not simply whether Condition B wins everywhere, but whether tool access improves recommendation quality consistently across heterogeneous workloads (OLTP, analytical, join-heavy, and decision-support benchmarks).

## 2. Pipeline Design and Implementation
The team built a modular shared pipeline in Phase 1, then reused the same architecture across all schema runs in Phase 2.

### 2.1 Baseline Module
Implemented in [pipeline/baseline](../pipeline/baseline), the baseline component:
- Loads schema and workload input.
- Runs EXPLAIN ANALYZE for each query without extra indexes.
- Produces baseline_results.csv with query_id, execution_time_ms, and query_plan_text.

### 2.2 Condition A Module
Implemented in [pipeline/condition_a](../pipeline/condition_a), the no-tool component:
- Prompts the model with schema and workload.
- Validates generated index statements.
- Produces condition_a_results.csv and overall index files.

### 2.3 Condition B Module
Implemented in [pipeline/condition_b](../pipeline/condition_b), the tool-augmented component:
- Uses a loop where the model proposes candidates and invokes estimate_index_cost.
- Logs proposed/accepted/rejected steps in tool_call_log.
- Produces condition_b_recommendation artifacts, then applies indexes and measures post-index runtime.

### 2.4 Measurement and Aggregation
Implemented in [pipeline/measurement](../pipeline/measurement), measurement scripts aggregate before/after runtimes and compute improvement_vs_baseline. During deadline stabilization, additional timeout and schema-targeting guards were added in Condition B measurement scripts to ensure long workloads complete and are reproducible.

## 3. Experimental Setup
- DBMS: PostgreSQL
- Baseline and both conditions measured with EXPLAIN ANALYZE
- Timeout guard: 120s statement timeout applied in long-running loops
- Fairness rule: Same model family used for Condition A and B per benchmark owner; only tool access differs

## 4. Combined Results (Current Repository State)
A consolidated table is included in [combined/combined_results.csv](../combined/combined_results.csv), with narrative in [combined/cross_domain_analysis.md](../combined/cross_domain_analysis.md).

### 4.1 High-level outcomes from completed rows
- TPC-H: Condition B outperformed Condition A.
- TPC-C: Condition A and B are approximately tied.
- TATP: Condition B outperformed Condition A.
- SSB and DSB: Condition A outperformed Condition B on aggregate improved/regressed counts.

### 4.2 Pending rows at submission-finalization time
- TPC-DS Condition B measurement output is complete in the repository; 4 rows in the CSV have missing `execution_time_ms_after` values (Q14, Q23, Q24, Q39) and are documented as measurement edge cases.
- JOB: Condition A improved 76/113 queries, Condition B improved 49/113 with 14 finalized indexes (82 tool calls); Condition A outperformed Condition B on this schema under clean, consistent measurement.
- STATS: Condition A improved 57/146 queries, Condition B improved 52/146 with 5 finalized indexes (79 tool calls, 74 rejected); Condition B outperformed Condition A on average on this schema, the opposite pattern from JOB.

## 5. Interpretation
The strongest cross-domain takeaway is that tool augmentation is workload-sensitive.

1. In schemas where a compact set of high-signal indexes exists, tool access can guide the model toward better final selections.
2. In broad analytical workloads, local candidate cost checks do not always transfer to globally better total workload behavior.
3. Condition A sometimes over-indexes, which can significantly regress broad workloads despite occasional large wins.

As a result, the data supports a nuanced claim: tool access is useful, but not universally superior without stronger global optimization constraints.

## 6. Individual Contributions
- Louis
  - Built baseline module and standalone execution path.
  - Produced TPC-H/TPC-DS baseline and analysis artifacts.
- Sylfhen
  - Built Condition A recommendation workflow and schema validation logic.
  - Produced JOB outputs and schema-level analysis.
- Alan
  - Built Condition B iterative tool-call loop with recommendation finalization and log tracking.
  - Produced TPC-C/TATP outputs and schema-level analysis.
- Ikenna
  - Built measurement utilities and result processing/testing foundation.
  - Produced SSB/DSB benchmark outputs and analysis.

## 7. Limitations and Risks
- Cross-schema completeness was uneven at the final deadline window.
- Timeout substitutions can distort average percentage comparisons in long-tail workloads.
- Some schema-specific query/runtime edge cases required defensive handling in measurement scripts.

## 8. Reflection and Future Work
This project highlighted that integrating an LLM into database tuning is as much a systems engineering task as it is a model prompting task. The most impactful lessons were:
- Enforcing strict, shared data contracts early prevents major integration delays.
- Execution reliability (timeouts, schema targeting, robust exception handling) matters as much as recommendation quality.
- Tool-augmented reasoning should include workload-level objective functions, not only per-candidate local checks.

Future improvements:
1. Add global objective optimization that penalizes regressed queries, not just candidate cost.
2. Add automatic rollback/ablation evaluation to remove harmful indexes before finalization.
3. Standardize post-run diagnostics (empty-scan checks, timeout ratios, and quality gates) in one shared script.
4. Improve canonical output validation so combined reporting cannot drift near submission deadlines.

## 9. Conclusion
The practicum demonstrates that LLM-assisted index tuning can be practical and informative across multiple benchmark families. Tool augmentation provides meaningful value in some workloads but is not inherently dominant in all domains. The final conclusion is therefore conditional: tool-augmented LLM tuning is promising when paired with robust measurement, workload-aware optimization, and strict reproducibility controls.

---

### Appendix A — Required Deliverables Pointers
- Combined table: [combined/combined_results.csv](../combined/combined_results.csv)
- Combined analysis: [combined/cross_domain_analysis.md](../combined/cross_domain_analysis.md)
- Final report: [report/final_report.md](final_report.md)

### Appendix B — Key Result Directories
- Louis: [results/louis](../results/louis)
- Sylfhen: [results/sylfhen](../results/sylfhen)
- Alan: [results/Alan](../results/Alan)
- Ikenna: [results/Ikenna](../results/Ikenna)
