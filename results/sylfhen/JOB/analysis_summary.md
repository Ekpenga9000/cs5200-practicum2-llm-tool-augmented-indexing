# JOB Schema — Analysis Summary

**Note on methodology:** This summary reflects a full redo of the baseline
and both conditions' measurements, using a genuinely clean database (no
leftover indexes from either condition), a single consistent Postgres
session/cache state, and the median of 7 EXPLAIN ANALYZE runs per query --
matching the methodology used elsewhere on the team (Alan's TPC-C/TATP). An
earlier version of this analysis was invalidated by a stale baseline
captured under different cache conditions; the numbers below supersede it.

## Baseline
Median-of-7 execution times for the 113 JOB queries, no additional indexes,
ranged from well under 100ms for simple lookups to tens of seconds for the
workload's known-expensive multi-way joins (the 16-30 query series in
particular).

## Condition A (No-Tool)
The LLM recommended 47 indexes; 46 were successfully applied (one index on
`movie_info.info` failed to build due to Postgres's 8191-byte B-tree row
size limit on that TEXT column -- a limitation Condition A had no way to
detect without tool access).

| Tier    | Queries | Avg Improvement | Regressed | Improved |
|---------|---------|------------------|-----------|----------|
| Simple  | 41      | -91.1%           | 20 (49%)  | 21       |
| Medium  | 35      | -12.5%           | 8 (23%)   | 27       |
| Complex | 37      | +29.9%           | 9 (24%)   | 28       |

Improvement grew and regression rate fell as query complexity increased,
consistent with the earlier (pre-redo) finding: blanket indexing pays off
more reliably on heavily-joined queries, where almost any relevant index
reduces some intermediate result size. On Simple queries, the net effect
was negative overall -- regressions like 4a (-993.6%) and 10c (-588.8%)
outweighed the gains from genuinely useful indexes, because unnecessary
indexes still carry real maintenance/planning overhead even on queries
that were already fast.

## Condition B (Tool-Augmented)
The tool-augmented pipeline logged 82 tool calls and finalized just 14
indexes -- a third of Condition A's count, reflecting the model's ability
to test candidates against real cost estimates before committing rather
than covering every plausible join/filter column.

| Tier    | Queries | Avg Improvement | Regressed | Improved |
|---------|---------|------------------|-----------|----------|
| Simple  | 41      | -215.7%          | 27 (66%)  | 14       |
| Medium  | 35      | -1063.5%         | 17 (49%)  | 18       |
| Complex | 37      | -5332.4%         | 20 (54%)  | 17       |

## Comparison
On this schema, under clean and consistent measurement conditions,
**Condition A outperformed Condition B on every tier** -- the opposite of
what tool access would be expected to produce. Condition B's smaller,
supposedly-verified index set produced dramatically worse average outcomes,
driven by a small number of catastrophic regressions (22d: -116,881%; 22c:
-41,334%; 25c: -15,017%) that far outweighed its wins.

The likely explanation is the same one surfaced independently by teammates
on other schemas (Ikenna's SSB, Alan's TPC-C): Condition B's cost tool
verifies one candidate index against one query at a time. It has no
visibility into how that index changes the planner's behavior across the
*rest* of the workload once several new indexes coexist. A candidate that
looked favorable in isolation can still push the planner toward a worse
overall plan shape for a different query that shares the same tables --
exactly the pattern behind JOB's worst Condition B regressions.

## Known limitations
- One Condition A index (`movie_info.info`) could not be physically built
  due to a Postgres row-size limit; Condition B's tool access would
  presumably have caught this before finalizing, though this was not
  directly tested since Condition B did not select that column.
- Three queries (17d, 17f, and the 26-30 series) are inherently expensive
  under both conditions due to large intermediate join sizes; their
  regressions/improvements dominate the Complex tier's totals and should
  be read with that in mind.
