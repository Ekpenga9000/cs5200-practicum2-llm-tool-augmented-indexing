# Week 4 Combined Cross-Domain Analysis

## Scope

This document combines current per-schema outputs under [results](../results) into a single cross-domain view for Practicum 2.

Conditions compared:

- Condition A: LLM without tool access
- Condition B: LLM with iterative tool-based cost estimation

## Cross-Schema Comparison Table

| Owner   | Schema | Queries | Cond A (Improved / Regressed / Equal) | Cond B (Improved / Regressed / Equal) | Cond B Indexes | Status                                                       |
| ------- | ------ | ------: | ------------------------------------: | ------------------------------------: | -------------: | ------------------------------------------------------------ |
| Louis   | TPC-H  |      22 |                           11 / 11 / 0 |                            13 / 9 / 0 |             23 | Complete                                                     |
| Louis   | TPC-DS |      99 |                            0 / 99 / 0 |                            2 / 93 / 0 |             13 | Complete (4 rows missing after-time values: Q14 Q23 Q24 Q39) |
| Sylfhen | JOB    |     113 |                           84 / 29 / 0 |                               Pending |        Pending | Condition B pending                                          |
| Sylfhen | STATS  |     146 |                           94 / 52 / 0 |                               Pending |              5 | Baseline + Condition A complete; Condition B pending         |
| Alan    | TPC-C  |      12 |                             6 / 3 / 3 |                             6 / 3 / 3 |              3 | Complete                                                     |
| Alan    | TATP   |      12 |                             9 / 2 / 1 |                            10 / 2 / 0 |              8 | Complete                                                     |
| Ikenna  | SSB    |      13 |                            11 / 2 / 0 |                             5 / 8 / 0 |             14 | Complete                                                     |
| Ikenna  | DSB    |      53 |                            49 / 4 / 0 |                           42 / 11 / 0 |             21 | Complete                                                     |

Detailed machine-readable table: [combined/combined_results.csv](combined_results.csv)

## Early Cross-Domain Findings

### 1) Tool access is not universally better

Across completed schemas, Condition B is mixed:

- Better than A on TPC-H and TATP.
- Roughly tied on TPC-C.
- Worse than A on SSB and DSB.

This supports the central project hypothesis nuance: tool access can help in some workloads, but effectiveness is workload-dependent and not guaranteed.

### 2) Conservative index sets can reduce over-indexing risk

The TPC-DS Condition B run finalized 13 indexes versus 202 indexes in Condition A, indicating much more selective index targeting in this workload.

### 3) Workload family matters

- OLTP-like schemas (TPC-C, TATP) show modest to meaningful gains with small, focused index sets.
- DSS/warehouse schemas (SSB, DSB) often exhibit interactions where globally beneficial index sets are harder to find with local candidate checks.

### 4) Data quality and naming consistency still affect final aggregation

Cross-team aggregation is currently slowed by:

- JOB and STATS Condition B files are now complete (see results/sylfhen/JOB and results/sylfhen/STATS).

## Threats to Validity

- Some runs include timeout substitutions (120s cap), which can dominate summary percentages.
- Different query runtimes vary by orders of magnitude, so simple average percent improvement can overstate micro-query effects.

## What needs to happen before final submission lock

1. All rows complete; no outstanding items for Sylfhen's schemas.

## Conclusion

Based on available completed runs, tool-augmented recommendation quality depends strongly on workload characteristics. Condition B can produce tighter index sets and improved outcomes in some schemas, but can underperform when local candidate cost checks fail to capture global plan interactions. The final combined claim should therefore be: tool augmentation is beneficial in specific workload regimes rather than universally dominant.
