# JOB Schema — Analysis Summary

## Baseline
No-index baseline execution times for the 113 JOB queries ranged from
under 100ms (simple lookups) to over 40 seconds (large multi-way joins
like 23c), reflecting real cost differences across the Simple/Medium/
Complex tiers.

## Condition A (No-Tool)
The LLM recommended 47 unique indexes across all 113 queries, based
purely on reading the schema DDL and query text. One recommended index
(on movie_info.info) failed to build due to Postgres's 8191-byte B-tree
row limit on that TEXT column -- a limitation Condition A had no way
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
regressed 231%) -- likely because Condition A recommends indexes for
every plausible join/filter column without verifying whether the
planner will actually benefit. On Complex queries, the same broad
strategy paid off far more reliably (e.g., 23b and 29b both improved
~99.9%).

## Condition B (Tool-Augmented)
The tool-augmented pipeline completed successfully: across 82 logged
tool calls, the LLM proposed and tested candidate indexes against real
EXPLAIN cost estimates before finalizing a recommendation of just 14
indexes -- roughly a third of Condition A's 47. That gap is itself a
notable finding: with the ability to verify candidates before
committing, the model converged on a much more selective, conservative
index set rather than covering every plausible join/filter column.

The performance measurement for this recommendation, however, is not
reportable as a fair comparison. The baseline_results.csv used for the
before/after comparison was captured two days prior to the Condition B
measurement run, during which the Postgres container was restarted
(following an interrupted overnight run) and its buffer cache cleared.
Measuring Condition B's indexes against a stale, cold-cache baseline
produced implausible results -- widespread multi-thousand-percent
regressions even on queries with no relationship to the applied
indexes -- consistent with environment drift rather than an actual
effect of the 14 recommended indexes. Re-measuring Condition B against
a freshly captured baseline, taken in the same session/cache state, is
required before these performance numbers can be trusted, and was not
completed in the time available.

## Comparison
Condition A’s core weakness—recommending indexes that it cannot verify—becomes particularly apparent on the Simple tier, where restraint is important and untested recommendations can be as harmful as they are helpful.

Condition B’s access to tools clearly changed its behavior in the expected direction: it produced fewer recommendations and tested candidates more deliberately. The key question is whether this increased selectivity translates into better real-world performance than Condition A’s broader approach. That question remains unresolved because of the baseline measurement issue described above, rather than because of any apparent flaw in Condition B’s recommendation process.

## Known Limitations

* **Invalid before/after timing comparison:** Condition B’s before-and-after timing comparison is not reliable because the baseline was captured under different cache conditions. A new measurement under consistent conditions is needed before drawing conclusions about the relative performance of the two approaches.

* **Unverifiable index recommendation:** Condition A recommended an index that could not be physically created due to PostgreSQL’s B-tree row-size limit on a `TEXT` column. Condition B’s tool access would presumably have allowed it to identify this issue before finalizing the recommendation. This should be confirmed once a valid Condition B performance measurement is available.

* **Robustness issues in Condition B:** Two robustness issues were identified and locally patched in the shared Condition B module during testing at JOB’s full 113-query scale: unhandled index-build failures and a missing-field error in `finalize_recommendation`. Both issues were reported to the team separately.

