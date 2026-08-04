# JOB Schema — Analysis Summary

## Baseline
The No index baseline execution times for the 113 JOB queries ranged from
under 100ms (simple lookups) to over 40 seconds (large multi-way joins
like 23c), reflecting real cost differences across the Simple/Medium/
Complex tiers.

## Condition A (No-Tool)
The LLM recommended 47 unique indexes across all 113 queries, based
purely on reading the schema DDL and query text. One recommended index
(on movie_info.info) failed to build due to Postgres's 8191-byte B-tree
row limit on that TEXT column. This a limitation Condition A had no way
to detect without tool access.

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
every plausible join/filter column without verifying whether the
planner will actually benefit. On Complex queries, the same broad
strategy paid off far more reliably (e.g., 23b and 29b both improved
~99.9%).

## Condition B (Tool-Augmented)
Not yet completed for this schema. Attempted runs against the full
113-query JOB workload surfaced two robustness gaps in the shared
Condition B module that don't appear at small-scale (toy/TPC-C-sized)
testing:
1. `real_index_estimator.py` crashed the whole run on the first
   candidate index that exceeded Postgres's B-tree size limit, with
   no error handling around the CREATE INDEX call.
2. `condition_b.py` assumed the LLM's `finalize_recommendation` tool
   call would always include a `reasoning` field, which is not
   guaranteed by the tool use API and failed with a KeyError once the
   model omitted it on a 113 query prompt.

Both were patched locally to keep testing, but a full real run against
113 queries with the iterative propose-estimate-iterate loop represents
a meaningfully larger API cost than the module's original TPC-C test
case. Given that, this run is being deferred, to be completed either
by re-running with these fixes upstreamed, or once the cost tradeoff is
discussed with the team.

## Comparison
Pending Condition B results.
