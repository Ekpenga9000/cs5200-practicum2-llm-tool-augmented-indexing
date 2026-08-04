# TPC-C (Schema 1) — Within-Schema Analysis

**Owner:** Alan · Baseline (PK/FK only) vs. Condition A (no-tool) vs. Condition B (tool-augmented)

## Setup

Deterministic reduced-scale TPC-C (`load_tpcc_data.py`, seed 42): 1 warehouse,
10 districts, 300 customers/district (~3,000 customers), 100 items, ~10
orders/customer (~30,000 orders, ~300k order-lines). Same LLM
(`claude-sonnet-4-6`) for both conditions; only tool access differs. Every
number below is the **median of 7 `EXPLAIN ANALYZE` runs after one warm-up**,
measured on a freshly reset (PK/FK-only) DB before each condition's indexes are
applied, so baseline / A / B are directly comparable.

## Recommended indexes

| Table | Condition A (no-tool) | Condition B (tool) |
|---|---|---|
| customer | `(c_w_id, c_d_id, c_last, c_first)` | same |
| orders | `(o_w_id, o_d_id, o_c_id, o_id)` | same |
| order_line | `(ol_w_id, ol_d_id, ol_o_id, ol_i_id)` | `(…, ol_i_id, ol_amount)` — extra covering col |
| stock | `(s_w_id, s_i_id, s_quantity)` | *(not recommended — B tried and rejected it)* |

Condition B logged 35 tool calls (23 proposed, **9 rejected**, 3 accepted);
Condition A had 0 hallucinated/rejected indexes.

## Results (median ms; improvement vs. baseline)

| Query | Tier | Baseline | Cond A | Cond B |
|---|---|---|---|---|
| Q1 | Simple | 0.008 | 0.006 (+25%) | 0.008 (0%) |
| Q2 | Simple | 0.008 | 0.007 (+13%) | 0.010 (−25%) |
| Q3 | Simple | 0.007 | 0.007 (0%) | 0.008 (−14%) |
| Q4 | Simple | 0.009 | 0.011 (−22%) | 0.010 (−11%) |
| Q5 | Simple | 0.010 | 0.010 (0%) | 0.010 (0%) |
| Q6 | Medium | 0.040 | **0.008 (+80%)** | **0.011 (+73%)** |
| Q7 | Medium | 0.170 | **0.010 (+94%)** | **0.010 (+94%)** |
| Q8 | Simple | 0.009 | 0.008 (+11%) | 0.011 (−22%) |
| Q9 | Medium | 0.009 | 0.010 (−11%) | 0.010 (−11%) |
| Q10 | Medium | 0.012 | 0.013 (−8%) | 0.016 (−33%) |
| Q11 | Complex | 0.067 | **0.051 (+24%)** | **0.055 (+18%)** |
| Q12 | Complex | 88.174 | **138.046 (−57%)** | **101.915 (−16%)** |

## What we found

**Signal vs. noise.** At the smallest scale factor, Q1–Q5 / Q8–Q10 run in tens
of microseconds — at or below timer resolution — so their ±10–30% swings are
jitter in *both* conditions, not real effects. Only four queries carry
measurable signal: Q6, Q7, Q11 (wins) and Q12 (regression).

**The easy wins are a tie.** Q6 and Q7 (mid-tier point lookups) improved ~73–94%
under both conditions, because both models recommended the *identical*
`customer` and `orders` indexes whose column order matches the `WHERE` + `ORDER
BY … LIMIT 1` access pattern. Tool access made no difference here — the right
index is obvious from the query text alone.

**Where the tool mattered — the dominant query.** Q12 is the only query with a
non-trivial absolute cost (~88 ms), and both conditions *regressed* it (the
recommended `order_line` index pushes the planner into a memoized per-order
nested-loop plan that it costs cheaper but that actually runs slower at this
scale). But the **no-tool** Condition A regressed it by **−57% (+50 ms)**, while
the **tool-augmented** Condition B regressed it by only **−16% (+14 ms)** — the
tool let B verify planner cost and steer toward the `ol_amount`-covering index
(enabling index-only scans) and *drop* the redundant `stock` index that A kept.
Because Q12 dominates absolute runtime, this ~36 ms gap is the whole story:
**tool access roughly halved the worst-case damage and produced a leaner index
set**, even though it didn't fully prevent the regression.

**Net.** By tier — Simple: no real change (noise). Medium: strong, condition-
independent wins on Q6/Q7. Complex: small win on Q11 (A slightly ahead, helped
by its extra `stock` index) and a regression on Q12 that **tool access made far
less severe**. Both conditions increase total workload time (Q12 dominates), but
Condition B lands much closer to baseline than Condition A.

## Caveats / notes for the cross-schema comparison

- Wall-clock deltas below ~0.1 ms are ties; planner **cost** estimates (in
  `tool_call_log.json`) are the more stable signal at this scale.
- Q12 (~88–140 ms, parallel + memoized plan) has real run-to-run variance;
  the A-vs-B gap is large enough to be a genuine plan difference, but the exact
  percentage will move a few points between runs.
- **TPC-C takeaway for Week 4:** tool access did *not* help on queries with an
  obvious index, but it *reduced the worst-case regression* on the workload's
  heaviest query and avoided a redundant index — a modest but real pro-tool
  signal on an OLTP workload.
