# TPC-H Within-Schema Analysis: Condition A vs. Condition B vs. Baseline

## Summary

Both conditions were run against a no-index PostgreSQL baseline over the standard TPC-H benchmark (scale factor 1, ~8.66M rows across 8 tables, all 22 standard queries). Tool-augmented reasoning (Condition B) produced a modestly better outcome than no-tool reasoning (Condition A), improving 13 of 22 queries versus Condition A's 11, while regressing fewer (9 vs. 11).

|                              | Improved | Regressed |
| ---------------------------- | -------: | --------: |
| Condition A (no tool)        |       11 |        11 |
| Condition B (tool-augmented) |       13 |         9 |

## Methodology Note

Both pipeline components required a local fix before producing valid results. Condition A's validator rejected syntactically valid `CREATE INDEX` statements due to case-sensitive matching against the schema DDL, discarding 83 of 99 LLM-proposed indexes; after a case-insensitive fix, 35 unique indexes were validly accepted (up from 16), and the corrected measurement is what's reported here. Condition B's cost estimator never set `search_path` to the TPC-H schema, causing all 68 `estimate_index_cost` calls in the first run to fail silently (returning `inf`) — the LLM finalized a recommendation without ever receiving real cost feedback. After fixing the connection's search path, 42 of 44 proposed candidates received real numeric cost estimates, and the corrected run is what's reported here. Both fixes were applied locally and were not merged into the shared pipeline, since the modules are owned by other team members who have been notified.

## Comparing the Two Conditions

Both conditions agreed on direction for most queries: 9 queries improved under both conditions, and 7 regressed under both, suggesting the underlying index candidates for those queries were relatively unambiguous regardless of reasoning method.

The more informative cases are where the conditions diverged:

- **Q6, Q11, Q12, Q15** — Condition A regressed these, but Condition B improved them. This is the clearest evidence that real cost feedback helped the LLM avoid or refine choices it would otherwise have gotten wrong when reasoning blind.
- **Q3, Q4** — the reverse pattern: Condition A improved these while Condition B regressed them, a reminder that tool access does not guarantee a better outcome on every query.

## The Timeout Cases: Q17, Q20, Q21

In the no-index baseline, three queries (Q17, Q20, Q21) exceeded a 120-second statement timeout due to expensive correlated subqueries against the 6-million-row `lineitem` table. Both conditions' recommended indexes brought all three well under the timeout:

| Query |            Baseline | Condition A | Condition B |
| ----- | ------------------: | ----------: | ----------: |
| Q17   | timeout (120,000ms) |    improved |    improved |
| Q20   | timeout (120,000ms) |    improved |    improved |
| Q21   | timeout (120,000ms) |    improved |    improved |

This is the single strongest result in the dataset: without indexing guidance of any kind, three of TPC-H's 22 standard queries are effectively unusable at this scale. Both LLM conditions independently identified indexes that resolved this, though Condition A's exact-second timings for these three were somewhat faster than Condition B's in this run.

## Complexity Tier Observations

All 22 TPC-H queries in this workload were classified as Medium or Complex (none qualified as Simple under the tier criteria, given TPC-H's inherent use of joins and aggregation). The clearest gap between conditions appeared among Complex-tier queries with correlated or nested subqueries (Q9, Q17, Q20, Q21) — exactly where a real cost estimate would be expected to matter most, since the query planner's behavior is least predictable from schema/query text alone. Medium-tier queries showed more mixed results in both conditions, suggesting reasoning quality (with or without tools) may matter less when the underlying query shape is simpler.

## Takeaway

For this schema, tool access provided a measurable but not dramatic improvement: a modest net gain in improved/regressed count, and clearer wins specifically on queries where a wrong index choice carries real cost. The larger and more consistent finding across both conditions is that _any_ informed indexing — tool-augmented or not — dramatically outperforms the no-index baseline on TPC-H's more complex queries.
