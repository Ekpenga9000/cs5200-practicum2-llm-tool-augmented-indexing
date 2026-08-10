# DSB Benchmark Analysis Summary

## Benchmark Overview

- **Benchmark:** DSB (Decision Support Benchmark)
- **Database:** PostgreSQL
- **Scale Factor:** 1 GB
- **Queries Evaluated:** 53
- **Conditions Evaluated:**
  - Condition A (No-Tool LLM)
  - Condition B (Tool-Augmented LLM)

---

## Baseline

The baseline benchmark was executed on the DSB database without any additional indexes beyond the primary keys created by the schema. Execution times for all 53 workload queries were recorded and used as the reference for evaluating the effectiveness of the recommended indexes.

---

## Condition A Results

### Summary

- Queries evaluated: **53**
- Recommended indexes: **139**
- Average improvement: **69.51%**
- Best improvement: **99.94%**
- Worst improvement: **-81.71%**

### Observations

Condition A generated a large number of index recommendations across the workload. After applying the recommended indexes and rerunning the benchmark, most queries experienced significant reductions in execution time. Several queries achieved improvements greater than 95%.

A small number of queries became slower after indexing, demonstrating that indexes do not always benefit every workload. Overall, however, the recommendations produced substantial performance gains across the benchmark.

---

## Condition B Results

### Summary

- Queries evaluated: **53**
- Recommended indexes: **21**
- Tool calls made: **68**
- Average improvement: **39.24%**
- Best improvement: **99.63%**
- Worst improvement: **-589.27%**

### Observations

Condition B used the tool-augmented workflow, allowing the language model to estimate candidate indexes before producing the final recommendation. The model produced a much smaller set of indexes than Condition A.

Although many queries still achieved large performance improvements, several experienced significant regressions, which reduced the overall average improvement. These regressions indicate that the smaller index set did not adequately optimize every query in the workload.

---

## Comparison

| Metric | Condition A | Condition B |
|---------|------------:|------------:|
| Queries | 53 | 53 |
| Recommended Indexes | 139 | 21 |
| Average Improvement | 69.51% | 39.24% |
| Best Improvement | 99.94% | 99.63% |
| Worst Improvement | -81.71% | -589.27% |

Condition A generated significantly more index recommendations and achieved a higher average performance improvement across the DSB workload. Condition B produced a more conservative set of recommendations and required 68 tool interactions during the recommendation process. While Condition B successfully improved many queries, its overall performance was lower due to several large regressions.

---

## Conclusion

The DSB benchmark was successfully generated, loaded into PostgreSQL, and evaluated under both Condition A and Condition B.

For this workload, the no-tool approach (Condition A) produced better overall performance than the tool-augmented approach (Condition B). Condition A recommended more indexes, resulting in higher average query performance improvements across the workload.

These results provide a complete comparison of both approaches on the DSB benchmark and can serve as a baseline for future experimentation and refinement of the recommendation strategy.
