# TATP (Schema 2) — Within-Schema Analysis

**Owner:** Alan · Baseline (PK/FK only) vs. Condition A (no-tool) vs. Condition B (tool-augmented)

## Setup

TATP (Telecom Application Transaction Processing) at 100,000 subscribers
(`load_tatp_data.py`, seed 42, COPY-loaded): ~250k access_info, ~250k
special_facility, ~375k call_forwarding. This size is large enough that lookups
on non-key columns (`sub_nbr`, `vlr_location`, `is_active`, `start_time`) have
real cost, so index effects are measurable rather than noise. Same LLM
(`claude-sonnet-4-6`) for both conditions; only tool access differs. Every number
is the **median of 7 `EXPLAIN ANALYZE` runs after one warm-up**, measured on a
freshly reset (PK/FK-only) DB before each condition's indexes are applied.

## Recommended indexes

**Both** recommended: `subscriber(sub_nbr)`, `special_facility(is_active, sf_type)`,
`call_forwarding(start_time)`, `subscriber(vlr_location…)`, `subscriber(msc_location…)`.

| Condition | Distinctive choices |
|---|---|
| A (no-tool) — 7 idx | plain `subscriber(vlr_location)` and `(msc_location)`; covering `call_forwarding(s_id,sf_type,start_time,end_time,numberx)`; `special_facility(s_id,is_active,sf_type)`. Its own validator wrongly rejected 2 *valid* `bit_*` indexes. |
| B (tool) — 8 idx | **covering** `subscriber(vlr_location, s_id, msc_location)` and `(msc_location, s_id)` (enables index-only scans); extra `bit_1` / `byte2_1` indexes. |

## Results (median ms; improvement vs. baseline)

| Query | Tier | Baseline | Cond A | Cond B |
|---|---|---|---|---|
| Q1 | Simple | 0.006 | 0.009 (−50%) | 0.007 (−17%) |
| Q2 (sub_nbr lookup) | Simple | 4.003 | **0.012 (+99.7%)** | **0.012 (+99.7%)** |
| Q3 | Simple | 0.007 | 0.007 (0%) | 0.010 (−43%) |
| Q4 | Simple | 0.011 | 0.009 (+18%) | 0.007 (+36%) |
| Q5 | Medium | 0.014 | 0.016 (−14%) | 0.013 (+7%) |
| Q6 (is_active filter) | Medium | 31.255 | **0.692 (+97.8%)** | **0.668 (+97.9%)** |
| Q7 (vlr range) | Medium | 5.212 | 1.349 (+74.1%) | **0.745 (+85.7%)** |
| Q8 | Simple | 0.015 | 0.013 (+13%) | 0.008 (+47%) |
| Q9 (start_time scan) | Medium | 31.749 | 8.731 (+72.5%) | **7.310 (+77.0%)** |
| Q10 (join+agg) | Complex | 46.281 | 44.838 (+3.1%) | **41.918 (+9.4%)** |
| Q11 (3-table join) | Complex | 44.121 | 37.782 (+14.4%) | 36.899 (+16.4%) |
| Q12 (join+agg) | Complex | 47.117 | 46.804 (+0.7%) | **43.080 (+8.6%)** |

## What we found

**A workload with real index opportunities.** Unlike TPC-C, TATP has several
queries that scan on *non-key* columns and cost real milliseconds at baseline:
Q2 (`sub_nbr`, 4 ms), Q6 (`is_active`, 31 ms), Q7 (`vlr_location` range, 5 ms),
Q9 (`start_time`, 32 ms), and the complex joins Q10–Q12 (~45 ms each). These are
the signal-bearing queries. Q1/Q3/Q4/Q5/Q8 are microsecond PK point lookups —
noise either way.

**Both conditions nail the obvious wins.** Q2 and Q6 improved ~98–99.7% under
*both* — a single-column index on the scanned column is unmissable, and both
models found it. Tie.

**Tool access is consistently equal-or-better, and clearly better on three
queries.** Condition B never lost to A on a signal query and won materially on:
- **Q7 (+85.7% vs +74.1%)** — B chose a *covering* index `(vlr_location, s_id,
  msc_location)` so the query is index-only; A's plain `(vlr_location)` still
  needs heap fetches.
- **Q10 (+9.4% vs +3.1%)** and **Q12 (+8.6% vs +0.7%)** — B's covering subscriber
  indexes feed the joins without heap access; A's leaner indexes help less.

Q9 and Q11 were near-ties (B marginally ahead). No B regression on any query
that carries real cost.

**Net.** On TATP, tool access **helped** — it matched Condition A on the obvious
single-column wins and produced strictly better (covering) index choices on the
range/join queries (Q7, Q10, Q12), with no regressions on the costly queries.

## Cross-schema note (TPC-C vs. TATP)

This is the opposite of my TPC-C result, where the tool tied-or-*hurt* (it
regressed Q11 with a bad stock-index column order). The difference is the
workload: TPC-C's queries are almost all fast PK point lookups with little index
headroom, so the tool's per-candidate cost checks had little to work with and
occasionally misfired; TATP has genuine non-key scan/range/join opportunities
with measurable cost, and there the cost tool let the model pick better
(covering) index shapes. **Tentative takeaway for Week 4: tool-augmented index
selection pays off when the workload has real, cost-visible index opportunities,
and adds little (or can mislead) when queries are already trivially fast.**

## Caveats

- Sub-0.05 ms deltas (Q1/Q3/Q4/Q5/Q8) are timer noise, not effects.
- Both conditions recommend many indexes (7–8); we measure read improvement
  only — the write/storage cost of that many indexes is not evaluated here.
- Condition A's module rejected two *valid* `bit_*` indexes as "hallucinated"
  (a false positive in its validator); it didn't affect the signal queries.
