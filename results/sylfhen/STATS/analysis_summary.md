# STATS Schema — Analysis Summary

## Baseline

The no-index baseline for the 146 STATS-CEB queries, using real StackExchange-derived data across 8 tables and approximately 1 million rows, showed a wide range of execution times. Simple two-table joins completed in under 40 ms, while three particularly difficult queries—`s58`, `s120`, and `s122`—each required approximately 15–20+ minutes to execute in plain PostgreSQL without additional indexes.

This behavior is consistent with the known characteristics of the STATS-CEB benchmark. A small subset of its queries can generate extremely large intermediate join results, reaching into the tens of billions of rows. Consequently, the slowest queries are not necessarily representative of the overall dataset size; their performance is largely driven by the structure and cardinality of intermediate joins.

## Condition A — No Tool Access

Condition A recommended **60 indexes** across the 146 queries based solely on the schema DDL and query text. Because the model had no access to execution plans or database-level testing, it could not verify whether the proposed indexes would actually be used by PostgreSQL or whether they would meaningfully reduce query cost.

[Insert the tier-by-tier breakdown table once `condition_a_results_tier_summary.md` has been generated for STATS, using the same `summarize_by_tier.py` process applied to JOB.]

The resulting approach was therefore relatively broad: the model identified potentially useful access paths from the query structure, but recommendations could not be validated against actual planner behavior.

## Condition B — Tool-Augmented

Condition B took a substantially more selective approach. The tool-augmented pipeline performed **79 logged tool calls**, testing distinct candidate indexes against real PostgreSQL `EXPLAIN` cost estimates through temporary physical index creation rather than relying on HypoPG.

Of the 79 candidates tested, only **5 were ultimately accepted**, while 74 were explicitly rejected because they did not improve upon the existing accepted set. The final indexes were:

* `posts(CreationDate, Id, OwnerUserId)`
* `votes(VoteTypeId, PostId, CreationDate)`
* `comments(Score, CreationDate, UserId)`
* `postHistory(PostHistoryTypeId, CreationDate, UserId)`
* `postLinks(RelatedPostId, LinkTypeId, CreationDate)`

This represents a substantial reduction compared with Condition A's 60 recommendations. Condition B ultimately retained fewer than **10%** as many indexes, suggesting that access to empirical planner feedback encouraged the model to prioritize candidates more carefully rather than simply maximizing potential index coverage.

The tool results also provided concrete evidence for the accepted recommendations. For example, the `postHistory` composite index reduced the estimated cost of the three-table join in query `s106` from the millions to approximately **474,000**. Similarly, successive refinements to the `posts` composite index reduced the estimated cost of query `s20` from approximately **11,606 to 11,441**.

The testing process also allowed the model to distinguish between similar index designs rather than treating them as equally useful. For example, `comments(Score, UserId, CreationDate)` was tested and rejected in favor of `comments(Score, CreationDate, UserId)`, which the planner consistently preferred because the column ordering better supported the query's date-range filtering after the equality condition on `Score`.

### Performance Remeasurement Limitation

A complete before-and-after execution-time comparison could not be completed within the available time. Although the five recommended indexes were applied, rerunning the full 146-query workload required substantially more time than was available.

The three pathological queries identified in the baseline—`s58`, `s120`, and `s122`—were particularly problematic. Even with the recommended indexes, these queries can take many minutes because their cost is dominated by extremely large intermediate join results rather than simply inefficient scans of individual tables. This appears to be an inherent characteristic of the STATS-CEB workload rather than an artifact of the indexing pipeline.

As a result, `execution_time_ms_after` and `improvement_vs_baseline` are not populated in `condition_b_results.csv` for this submission. Importantly, this limitation affects the **performance measurement**, not the recommendation process itself. The five-index recommendation, its supporting reasoning, and the complete 79-call tool log were successfully produced.

## Comparison

The clearest finding from the STATS schema is therefore about **selectivity rather than measured performance**.

Condition A produced 60 recommendations without the ability to verify whether those indexes would actually benefit the workload. Condition B, by contrast, tested 79 candidates against real PostgreSQL cost estimates and ultimately converged on only 5 indexes. Each accepted index has a specific cost-based justification tied to one or more queries, while rejected candidates were removed when they failed to demonstrate an improvement over the existing set.

This provides evidence that tool access materially changed the model's indexing strategy: instead of broadly recommending potentially useful indexes, it used empirical feedback to narrow the recommendation to a much smaller set.

However, it would be premature to conclude that Condition B is definitively better in terms of **real-world execution performance**. Because the full before-and-after workload could not be completed, we do not yet have sufficient evidence to determine whether the five-index configuration outperforms Condition A's broader 60-index configuration. A controlled remeasurement under identical conditions would be the appropriate next step.

## Known Limitations

* **Incomplete performance measurement:** `execution_time_ms_after` and `improvement_vs_baseline` are empty in `condition_b_results.csv`. The Condition B recommendation and tool-call log are complete, but the full before-and-after measurement was not completed because of time constraints and the unusually slow STATS-CEB queries.

* **Condition A's unverified recommendations:** Condition A recommended 60 indexes without access to execution plans or database-level validation. Some recommendations appear redundant, including multiple differently named indexes targeting the same single column on `postHistory`. This reflects the broader "blind coverage" pattern also observed in the JOB schema.

* **No direct performance comparison:** The available results demonstrate a substantial difference in recommendation selectivity, but they do not establish which condition produces better execution times. That conclusion requires a controlled remeasurement of the complete workload.
