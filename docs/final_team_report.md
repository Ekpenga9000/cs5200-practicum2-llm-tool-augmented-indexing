# Final Team Report: LLM-Based Index Recommendation — No-Tool vs. Tool-Augmented

**Team:** Sylfhen, Louis, Alan, Ikenna
**Practicum 2 — CS 5200**

---

## 1. Research Question

This project compares two approaches to LLM-based database index recommendation: **Condition A**, where the LLM reads only a schema's DDL and a query workload and recommends indexes with no other input, and **Condition B**, where the LLM can iteratively test candidate indexes against real PostgreSQL planner cost estimates before finalizing a recommendation. Every team member ran both conditions against two assigned schemas, using identical shared pipeline code (baseline measurement module, Condition A module, Condition B module) and the same pinned LLM model, so that results are comparable across all eight schemas.

The central question: **does giving an LLM access to real cost-estimation tools produce measurably better index recommendations than a no-tool LLM, and does that advantage hold consistently across different kinds of workloads** — OLTP-style (TPC-C), star-schema analytical (SSB, DSB), and complex real-world join-heavy workloads (JOB, STATS)?

This report covers the five schema analyses completed and available at the time of writing: **JOB and STATS** (Sylfhen), **TPC-C** (Alan), and **SSB and DSB** (Ikenna). Louis's two schema analyses were not available for inclusion in this draft and should be added once complete.

---

## 2. Methodology

Each schema followed the same three-stage pipeline:

1. **Baseline** — the workload is run against the schema with no additional indexes (primary/foreign keys only), using `EXPLAIN ANALYZE`, to establish reference execution times.
2. **Condition A** — the LLM is given the schema DDL and full query workload as plain text and asked to recommend indexes, with no tool access and no ability to verify its guesses.
3. **Condition B** — the LLM is given the same information plus a cost-estimation tool. It can propose a candidate index, see PostgreSQL's real planner cost estimate for that candidate against a specific query, and iterate — trying and discarding candidates — before calling a `finalize_recommendation` tool exactly once. Every tool call (candidate, estimated cost, accept/reject decision) is logged.

Recommended indexes from both conditions are then physically applied and the workload is re-run to measure real before/after execution time, expressed as percent improvement relative to baseline.

---

## 3. Cross-Schema Results

| Schema | Owner | Workload Type | Cond A: # Indexes | Cond A: Avg Improvement | Cond B: # Indexes | Cond B: Tool Calls | Cond B: Avg Improvement |
|---|---|---|---|---|---|---|---|
| JOB | Sylfhen | Complex real-world joins (IMDB) | 47 | 1.0% (Simple) / 24.6% (Medium) / 50.2% (Complex) | 14 | 82 | *Not measured — see §5* |
| STATS | Sylfhen | Complex real-world joins (StackExchange) | 60 | *Pending tier summary* | 5 | 79 (5 accepted, 74 rejected) | *Not measured — see §5* |
| TPC-C | Alan | OLTP, micro scale factor | *Pending* | *Pending* | 3 | 35 (3 accepted, 9 rejected, 23 proposed) | Net negative overall (one query's regression outweighs all other gains) |
| SSB | Ikenna | Star-schema analytical | 18 | Large wins on select queries; regressions on Q1.1, Q3.1 | 14 | 81 | Large wins on select queries; widespread regressions elsewhere (Q2.1, Q4.3) |
| DSB | Ikenna | Decision-support / star-schema | 139 | 69.51% | 21 | 68 | 39.24% |

**Note on missing cells:** Condition A vs. B comparisons for JOB and TPC-C are incomplete at time of writing — JOB's Condition B performance numbers were invalidated by a stale baseline (caught and documented, see §5), and TPC-C's Condition A run had not yet been completed against the same database dump as of Alan's write-up.

---

## 4. Key Findings

### 4.1 Condition B consistently recommends far fewer indexes than Condition A

This is the most consistent pattern across every schema with data on both conditions:

- JOB: 47 (A) vs. 14 (B)
- STATS: 60 (A) vs. 5 (B)
- SSB: 18 (A) vs. 14 (B)
- DSB: 139 (A) vs. 21 (B)

In every case, tool access led the model to converge on a smaller, more selective set of indexes. Condition A, with no way to verify whether a candidate actually helps, tends to recommend an index for nearly every plausible join or filter column it can identify from reading the query text — a "blanket coverage" strategy. Condition B's access to real cost feedback lets it test and discard weak candidates before committing, and the tool-call logs show this happening explicitly: DSB's Condition B made 68 tool calls to arrive at 21 final indexes; STATS made 79 calls to arrive at just 5, rejecting 74 candidates along the way with specific, cited reasoning for each rejection.

### 4.2 Neither condition reliably wins — both show real regressions

Across every schema, both conditions produced at least some queries that got *slower* after indexing, not faster:

- **JOB (Condition A):** Simple-tier queries averaged only 1.0% improvement because gains from useful indexes were largely canceled out by regressions from unnecessary ones (individual queries regressed by over 200%).
- **SSB:** Condition A made Q1.1 and Q3.1 slower (44.23% and 42.32% regressions); Condition B did *worse* here, with Q2.1 regressing from 3,376ms to 12,035ms (a >250% slowdown) and Q4.3 regressing similarly.
- **DSB:** Condition A's worst single-query regression was -81.71%; Condition B's worst was dramatically larger at -589.27%, despite Condition B's *average* being lower overall (39.24% vs. 69.51%) — meaning Condition B traded fewer wins for a few much larger losses.
- **TPC-C:** A single query (Q12, the only one with non-trivial absolute cost) regressed by 15.6% under Condition B, and because it dominated total runtime, this one regression outweighed clear wins on three other queries (Q6, Q7, Q11 all improved 18-94%).

### 4.3 Cost estimates for individual candidates don't guarantee whole-workload improvement

This is the most important nuance the team surfaced, articulated clearly in both Ikenna's SSB analysis and Alan's TPC-C analysis independently: Condition B's tool verifies the estimated cost of *one candidate index against one query at a time*. It has no visibility into how that index interacts with the rest of the workload, or how PostgreSQL's planner will actually behave once several new indexes exist simultaneously.

- Ikenna's SSB findings state this explicitly: "lower estimated cost for isolated candidates does not guarantee lower measured runtime for the complete workload." Condition A outperformed Condition B on most of the Q3/Q4 workload in SSB — for example, Q3.4 improved 99.85% under Condition A but became 2.58% *slower* under Condition B, despite Condition B having supposedly "verified" its candidates.
- Alan's TPC-C analysis reaches the same conclusion from a different angle: Condition B's tool correctly rejected an over-broad 9-column covering index earlier in its search, but the index it *did* finalize on `order_line` still changed the query planner's chosen plan shape for Q12 into something that measured worse in practice than the plan estimated, even though the per-candidate cost estimate looked favorable.

This suggests tool access reduces some categories of error (wildly redundant or clearly-useless indexes) but does not eliminate the risk of a worse real-world outcome, because plan-shape interactions across a whole workload are not something a per-candidate cost check can see.

### 4.4 Effect size scales with schema/query complexity

Sylfhen's JOB data shows a clean trend: Condition A's improvement *increased* and its regression rate *decreased* as query complexity increased (Simple: 1.0% avg / 34% regressed; Medium: 24.6% avg / 26% regressed; Complex: 50.2% avg / 16% regressed). This is consistent with the DSB and SSB findings in spirit: blanket indexing tends to help more, and hurt less proportionally, on queries with many joins, where almost any relevant index reduces some intermediate result size — versus simple queries, where an unnecessary index is more likely to be pure overhead with no compensating benefit.

---

## 5. Limitations and Threats to Validity

- **JOB's Condition B performance comparison is invalid.** The baseline used for comparison was captured in a separate session, days before the Condition B measurement run, during which the Postgres container was restarted (following an interrupted overnight run) and its buffer cache cleared. Re-measuring under stale, cold-cache-vs-warm-cache conditions produced implausible multi-thousand-percent regressions unrelated to the actual indexes. This was caught before being reported as a real finding and is documented as a limitation rather than a result.
- **STATS's Condition B performance remeasurement did not complete** in the time available. Three of the 146 STATS-CEB queries are documented in the academic literature as taking 15+ minutes each regardless of indexing, due to extreme intermediate join cardinalities — a property of the benchmark, not the pipeline. The recommendation itself (5 indexes, full reasoning, 79-call tool log) is genuine and complete; only the before/after timing comparison is missing.
- **TPC-C's micro scale factor produces measurement noise.** At Alan's reduced scale (1 warehouse), most queries execute in tens of microseconds — below reliable timer resolution — so roughly half the workload's ±10-30% deltas are noise, not real effects. Only 4 of 12 queries carried a measurable signal.
- **Shared component robustness gaps were discovered mid-project**, only surfacing at full production scale rather than in the smaller toy/test cases used during initial Phase 1 development: the baseline module's schema-creation step didn't support pre-populated large datasets, and the Condition B module initially crashed on oversized index candidates and on a missing optional field from the LLM's finalize call. Both were identified and patched by the team before being used to produce the numbers in this report.
- **Louis's two schema analyses are not yet incorporated** into this report and should be added for the final submission.

---

## 6. Conclusion

Across five schemas spanning OLTP, star-schema analytical, and complex real-world join workloads, the team's evidence does **not** support a simple "tool access always helps" conclusion. Condition B consistently produces a smaller, more deliberately-justified set of index recommendations than Condition A — a real and measurable behavioral difference — but this selectivity does not translate into consistently better real-world performance. In two of the three schemas with complete side-by-side comparisons (SSB and DSB), Condition A's broader, unverified approach actually achieved a *higher* average improvement than Condition B, driven by a small number of large Condition B regressions that its own per-candidate cost verification failed to anticipate. The team's shared conclusion is that tool-augmented cost estimation is a genuine improvement in *how the LLM reasons* — it tests before committing, and it can articulate why it rejected specific candidates — but it is not yet a reliable improvement in *outcome*, because a single-candidate cost estimate cannot see whole-workload plan interactions.
