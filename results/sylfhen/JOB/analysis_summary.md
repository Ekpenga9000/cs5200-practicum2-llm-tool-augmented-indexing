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

## Case Study: Query 22d — Why a Recommended Index Caused a 30-Minute Regression

Query 22d was Condition B's single worst regression (-116,881% vs. baseline).
Investigation (prompted by a teammate review, see below) confirms this is a
genuine finding about index design, not a measurement artifact.

**Verification steps taken before diagnosing:**
- Confirmed `search_path`/schema resolution was not a factor: all JOB tables
  live in `public`, and the `schema_name: "postgres"` field in Condition B's
  input JSON is only used to select the database to connect to -- it has no
  effect on table/schema resolution.
- Discovered the live database had drifted from the state Condition B was
  actually measured under (76 indexes present instead of the correct 35,
  because a later Condition A remeasurement ran on the same database without
  first dropping Condition B's indexes). Restored the exact 35-index state
  (21 primary keys + Condition B's 14 recommended indexes) before running
  any diagnostic query, so the analysis below reflects the actual measured
  condition.

**What the plan shows:**
Total execution time: 1,846,133 ms (~30.8 minutes). Planning time: 81 ms.
Essentially all runtime (99.99%) is concentrated in one Nested Loop join,
estimated by the planner at 1 row but producing 46,281 actual rows. Its
inner side performs an Index Only Scan on `movie_info_idx` using Condition
B's recommended composite index `(info_type_id, info, movie_id)`, executed
47,475 times (once per outer row) at roughly 35 ms each -- about 1.67
million ms total, ~90% of the query's entire runtime.

**Root cause:** the index's column order is efficient only when the middle
column (`info`) is filtered by equality. This query filters it with a range
predicate (`info < '8.5'`), and `movie_id` -- the value each outer-loop
iteration actually needs to locate -- sits after that open-ended range in
the index's key order. Rather than binary-searching directly to the target
`movie_id`, each of the 47,475 iterations must scan across a substantial
portion of the rating range checking every entry's `movie_id`. This
structural inefficiency was compounded by a severe cardinality
misestimate (planner expected ~1 row, actual was 46,281), which is why the
planner chose a nested-loop strategy in the first place -- a reasonable
choice for the estimate it had, catastrophic for the reality.

**Interpretation:** the recommended index was not ignored by the planner --
it was used exactly as built. Its column ordering was simply mismatched to
this specific query's predicate shape (range vs. equality), and Condition
B's cost-estimation tool, which tests one candidate against one query at a
time via real EXPLAIN cost, did not surface this because the same index
performs well for other queries in the workload that filter `info` by
equality. This is a concrete, mechanistic example of the broader
cross-schema pattern (also observed independently by teammates on SSB and
TPC-C): tool-augmented verification reduces some categories of error but
cannot see column-order/predicate-type interactions that only manifest
once a candidate index is evaluated against the query that actually
exposes its weakness.
