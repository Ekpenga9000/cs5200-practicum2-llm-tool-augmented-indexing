# TPC-C (Schema 1) — Within-Schema Analysis

**Owner:** Alan · **Condition:** B (Tool-Augmented) vs. no-index baseline

## Setup

Deterministic reduced-scale TPC-C (`load_tpcc_data.py`, seed 42): 1 warehouse,
10 districts, 300 customers/district (~3,000 customers), 100 items, ~10
orders/customer (~30,000 orders, ~300k order-lines). Baseline = PK/FK indexes
only, measured on a freshly rebuilt DB. Each query timed as the median of 7
`EXPLAIN ANALYZE` runs (warm cache). Condition B ran a tool-augmented loop of
**35 logged tool calls (23 candidates proposed, 9 rejected, 3 accepted)** and
finalized 3 indexes:

- `customer (c_w_id, c_d_id, c_last, c_first)`
- `orders (o_w_id, o_d_id, o_c_id, o_id)`
- `order_line (ol_w_id, ol_d_id, ol_o_id, ol_i_id, ol_amount)`

## Results (baseline → Condition B, ms)

| Query | Tier | Baseline | Cond B | Δ | Note |
|---|---|---|---|---|---|
| Q1 | Simple | 0.008 | 0.008 | 0.0% | noise |
| Q2 | Simple | 0.008 | 0.010 | −25.0% | noise |
| Q3 | Simple | 0.007 | 0.008 | −14.3% | noise |
| Q4 | Simple | 0.009 | 0.010 | −11.1% | noise |
| Q5 | Simple | 0.010 | 0.010 | 0.0% | noise |
| Q6 | Medium | 0.040 | 0.011 | **+72.5%** | customer index (c_last lookup + c_first sort) |
| Q7 | Medium | 0.170 | 0.010 | **+94.1%** | orders index (equality filter + o_id DESC LIMIT 1) |
| Q8 | Simple | 0.009 | 0.011 | −22.2% | noise |
| Q9 | Medium | 0.009 | 0.010 | −11.1% | noise |
| Q10 | Medium | 0.012 | 0.016 | −33.3% | noise |
| Q11 | Complex | 0.067 | 0.055 | **+17.9%** | order_line index helps the join |
| Q12 | Complex | 88.174 | 101.915 | **−15.6%** | regression (see below) |

## What we found

**Signal vs. noise.** At the smallest scale factor most queries run in tens of
microseconds — at or below timer resolution — so the ±10–30% swings on Q1–Q5,
Q8–Q10 are jitter, not real effects. Only four queries carry measurable signal:
Q6, Q7, Q11 (wins) and Q12 (regression).

**Where tool-augmentation clearly helped.** The two mid-tier point-lookup
queries improved most: Q7 (−94%, `orders` composite index directly serves the
`WHERE` + `ORDER BY ... LIMIT 1`) and Q6 (−73%, `customer` index serves the
`c_last` predicate and the `c_first` sort with no separate sort step). Q11's
join saw a smaller but real ~18% gain. In every case the index *column order*
matched the query's access pattern — exactly what the cost tool was used to
verify before finalizing.

**Where it hurt — the headline caveat.** Q12, the only query with a
non-trivial absolute cost (~88 ms), got **~14 ms slower** under Condition B.
That single regression outweighs the combined microsecond-level gains of every
other query. The `order_line (…, ol_i_id, ol_amount)` index changed Q12's plan
(memoized per-order index-only lookups) into a shape the planner costed lower
per-candidate but that runs slower end-to-end. This is the key lesson: the tool
estimates cost **per candidate against a single query**, so it can miss
whole-workload / plan-shape interactions — tool access reduced the index set
(it rejected the bloated 9-column covering index an earlier run had accepted)
but did **not** prevent a net regression on the workload's dominant query.

**Net.** By tier: Simple = no real change; Medium = strong wins on the two
index-friendly lookups; Complex = one modest win (Q11) and one meaningful
regression (Q12). Because Q12 dominates absolute runtime, **total workload time
went up under Condition B** even though 3 of the 4 signal-bearing queries
improved.

## Caveats / notes for the cross-schema comparison

- Wall-clock deltas below ~0.1 ms should be treated as ties; the planner
  **cost** estimates (in `tool_call_log.json`) are the more stable signal at
  this scale.
- **Condition A (no-tool) comparison pending** — to be filled in once Sylfhen's
  Condition A module is run on this same DB/dump, so A vs. B is apples-to-apples.
