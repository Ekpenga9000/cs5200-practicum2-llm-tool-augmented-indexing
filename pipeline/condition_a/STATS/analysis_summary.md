# STATS Schema — Analysis Summary

**Note on methodology:** This summary reflects a full redo of the baseline
and both conditions' measurements, using a genuinely clean database, a
single consistent session/cache state, and the median of 7 EXPLAIN ANALYZE
runs per query, matching the methodology used elsewhere on the team. An
earlier version of this analysis was incomplete (Condition B's performance
remeasurement had not been run); the numbers below are the first complete,
valid comparison for this schema.

## Baseline
Median-of-7 execution times for the 146 STATS-CEB queries (real
StackExchange-derived data) ranged from under 30ms for simple two-table
joins to three genuinely pathological outliers -- s58, s120, and s122 --
each taking many minutes per execution regardless of indexing, a
documented property of this benchmark's known-hard queries rather than an
artifact of this pipeline.

## Condition A (No-Tool)
The LLM recommended 65 indexes; 65 were successfully applied.

| Tier    | Queries | Avg Improvement | Regressed | Improved |
|---------|---------|------------------|-----------|----------|
| Simple  | 88      | -16.3%           | 55 (63%)  | 33       |
| Medium  | 28      | -99.1%           | 16 (57%)  | 12       |
| Complex | 30      | -37.4%           | 18 (60%)  | 12       |

Every tier regressed on average. Condition A's broad, unverified index set
(65 indexes for a schema with only 8 tables) appears to have imposed real
overhead -- more indexes for the planner to consider and maintain -- while
only helping a minority of queries meaningfully (best cases like s41 at
+72.2% and s55 at +85.5% were the exception, not the rule). The three known
pathological queries (s58, s120, s122) were dramatically slower under
Condition A's index set than in the clean baseline, suggesting the added
indexes pushed the planner toward materially worse plans for these
specific enormous joins.

## Condition B (Tool-Augmented)
The tool-augmented pipeline logged 79 tool calls (5 accepted, 74 rejected)
and finalized just 5 indexes -- roughly 8% of Condition A's count.

| Tier    | Queries | Avg Improvement | Regressed | Improved |
|---------|---------|------------------|-----------|----------|
| Simple  | 88      | -3.5%            | 63 (72%)  | 25       |
| Medium  | 28      | +1.4%            | 18 (64%)  | 10       |
| Complex | 30      | +2.9%            | 13 (43%)  | 17       |

## Comparison
On this schema, **Condition B clearly outperformed Condition A on every
tier** -- Medium and Complex tiers even turned net positive, versus
Condition A's uniformly negative averages. This is the opposite pattern
from JOB, and it is consistent with the core hypothesis behind tool
augmentation: with only 8 tables and a much smaller, well-chosen index set,
Condition B avoided imposing the broad overhead that hurt Condition A
across the board. The majority of queries still regressed slightly under
both conditions (STATS's queries are mostly already fast, so any added
index carries proportionally larger relative overhead), but Condition B's
regressions were consistently smaller in magnitude (worst case -56.44% vs.
Condition A's -1605.2%).

## Comparison across schemas (JOB vs. STATS)
Taken together with JOB's results, the two schemas show opposite winners:
Condition A wins on JOB (21 tables, heavily-joined queries where broad
coverage pays off), while Condition B wins on STATS (8 tables, where a
smaller, verified index set avoids unnecessary overhead). This suggests
tool-augmented cost estimation's value may depend on schema
characteristics -- specifically, how many plausible index candidates exist
and how much they compete or interact -- rather than being a uniform
improvement regardless of workload.

## Known limitations
- The three pathological queries (s58, s120, s122) dominate their tiers'
  averages; their absolute magnitude means a single query's regression or
  improvement can swing a tier's reported average substantially.
- Both conditions' Simple-tier averages are negative, suggesting that at
  this schema's scale, index overhead outweighs benefit for the majority
  of already-fast queries regardless of condition -- a pattern worth
  further investigation with a larger or more index-sensitive Simple-tier
  workload.
