# TPC-C (Schema 1) — Within-Schema Analysis

**Owner:** Alan · Baseline (PK/FK only) vs. Condition A (no-tool) vs. Condition B (tool-augmented)

## Setup

Standard TPC-C at the smallest real scale factor — **1 warehouse** (`load_tpcc_data.py`,
seed 42, COPY-loaded): 10 districts, 3,000 customers/district (30,000), **100,000
items**, **100,000 stock**, 30,000 orders, ~300,000 order-lines. (An earlier toy
sub-scale with only 100 items/stock made every query sub-microsecond and index
effects pure noise; this is the corrected, standard-cardinality run.) Same LLM
(`claude-sonnet-4-6`) for both conditions; only tool access differs. Every number
is the **median of 7 `EXPLAIN ANALYZE` runs after one warm-up**, measured on a
freshly reset (PK/FK-only) DB before each condition's indexes are applied, so
baseline / A / B are directly comparable.

## Recommended indexes

| Table | Condition A (no-tool) | Condition B (tool) |
|---|---|---|
| customer | `(c_w_id, c_d_id, c_last, c_first)` | same |
| orders | `(o_w_id, o_d_id, o_c_id, o_id)` | same |
| order_line | `(ol_w_id, ol_d_id, ol_o_id)` | *(not recommended)* |
| stock | `(s_w_id, s_i_id, s_quantity)` | `(s_w_id, s_quantity, s_i_id)` — range col in the middle |

## Results (median ms; improvement vs. baseline)

| Query | Tier | Baseline | Cond A | Cond B |
|---|---|---|---|---|
| Q1 | Simple | 0.005 | 0.006 (−20%) | 0.005 (0%) |
| Q2 | Simple | 0.007 | 0.008 (−14%) | 0.006 (+14%) |
| Q3 | Simple | 0.008 | 0.008 (0%) | 0.007 (+13%) |
| Q4 | Simple | 0.006 | 0.006 (0%) | 0.006 (0%) |
| Q5 | Simple | 0.007 | 0.007 (0%) | 0.009 (−29%) |
| Q6 | Medium | 0.210 | **0.009 (+96%)** | **0.009 (+96%)** |
| Q7 | Medium | 0.189 | **0.009 (+95%)** | **0.007 (+96%)** |
| Q8 | Simple | 0.010 | 0.009 (+10%) | 0.008 (+20%) |
| Q9 | Medium | 0.007 | 0.009 (−29%) | 0.007 (0%) |
| Q10 | Medium | 0.015 | 0.013 (+13%) | 0.016 (−7%) |
| Q11 | Complex | 0.252 | **0.219 (+13%)** | **0.494 (−96%)** |
| Q12 | Complex | 197.99 | 187.39 (+5%) | 191.50 (+3%) |

## What we found

**Signal vs. noise.** Q1–Q5 / Q8–Q10 are single-row PK/point lookups that run in
microseconds no matter what — no index can speed up a primary-key lookup, so
their ±10–30% swings are timer jitter, not effects. The four queries with real
signal are Q6, Q7 (mid-tier lookups), and Q11, Q12 (the complex ones).

**The easy wins are a tie.** Q6 and Q7 both improved ~95% under *both* conditions,
because both models recommended the *identical* `customer` and `orders` indexes
whose column order matches the `WHERE` + `ORDER BY … LIMIT 1` access pattern. The
right index is obvious from the query text alone, so tool access adds nothing.

**Where tool access actively HURT — Q11.** This is the headline. The no-tool
Condition A *improved* Q11 by ~13%, but the tool-augmented Condition B *regressed*
it by ~96% (0.25 → 0.49 ms, roughly 2× slower than doing nothing). The cause is in
the index choices: A recommended `stock(s_w_id, s_i_id, s_quantity)` plus an
`order_line` index, which supports Q11's join on `s_i_id`. B instead recommended
`stock(s_w_id, s_quantity, s_i_id)` — putting the *range* predicate `s_quantity < 15`
ahead of the join key `s_i_id`, which the planner still picks but which executes a
worse plan — and B dropped the `order_line` index entirely. So the tool's
per-candidate cost checks led B to a **worse** index design here, not a better one.

**The dominant query is a wash.** Q12 (~198 ms, the only query where absolute time
matters) came out ~+3–5% for both conditions — within run-to-run variance for a
parallel, memoized plan at this size. Neither condition meaningfully helped or hurt it.

**Net.** On the corrected, standard-scale TPC-C workload, tool access did **not**
improve index quality: it tied on the obvious wins (Q6/Q7), was a wash on the
dominant query (Q12), and **actively regressed Q11** by choosing a poorer stock
index column order and omitting an order_line index. If anything, the no-tool
Condition A produced the marginally better index set on this OLTP workload.

## Caveats / notes for the cross-schema comparison

- Wall-clock deltas below ~0.05 ms are ties; the planner **cost** estimates
  (in `tool_call_log.json`) are the more stable signal for the point queries.
- Q12 (~190 ms, parallel + memoized) has real run-to-run variance; its ±3–5%
  should be read as "no change."
- **TPC-C takeaway for Week 4:** on this OLTP workload the tool did not help and
  in one case hurt (Q11) — a concrete example of tool-augmented reasoning
  producing a *worse* decision (bad index column order) than the no-tool baseline.
  Whether that pattern holds on analytical / large-scan workloads is the Week-4
  cross-domain question.
