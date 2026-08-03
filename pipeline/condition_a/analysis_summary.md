# JOB Schema — Analysis Summary

## Baseline
The No index baseline execution times for the 113 JOB queries ranged from
under 100ms (simple lookups) to over 40 seconds (large multi-way joins
like 23c), reflecting the real cost differences across the Simple/Medium/
Complex tiers.

## Condition A (No-Tool)
The LLM recommended 47 unique indexes across all 113 queries, based
purely on reading the schema DDL and query text. One recommended index
(on movie_info.info) failed to build due to Postgres's 8191-byte B-tree
row limit on that TEXT column. This represents a limitation Condition A had no way to detect without tool access.

After applying the 46 buildable indexes and running ANALYZE to refresh
planner statistics, results varied sharply by tier:

| Tier    | Queries | Avg Improvement | Regressed | Improved |
|---------|---------|------------------|-----------|----------|
| Simple  | 41      | 1.0%             | 14 (34%)  | 27       |
| Medium  | 35      | 24.6%            | 9 (26%)   | 26       |
| Complex | 37      | 50.2%            | 6 (16%)   | 31       |

Improvement grew and regression rate fell as query complexity increased.
On Simple queries, gains from useful indexes were largely canceled out
by regressions from unnecessary ones (e.g., 6d regressed 264%, 6f
regressed 231%). This is likely because Condition A recommends indexes for
every plausible join/filter columns without verifying whether the
planner will actually benefit, and added index maintenance overhead can
outweigh marginal gains on queries that were already fast. On Complex
queries, the same broad strategy paid off far more reliably (e.g., 23b
and 29b both improved ~99.9%).

## Condition B (Tool-Augmented)
[To be completed once Alan's shared module is available and run against
the same schema/workload.]

## Comparison
Condition A's core weakness: recommending indexes it cannot verify
will help. This shows up most clearly on the Simple tier, where restraint
matters and blind recommendations are as likely to hurt as help.
Condition B's access to real EXPLAIN cost estimates should, in
principle, let it avoid exactly these Simple-tier regressions by
testing candidates before committing to them. Whether that holds in
practice is the open question for this schema once Condition B results
are in.