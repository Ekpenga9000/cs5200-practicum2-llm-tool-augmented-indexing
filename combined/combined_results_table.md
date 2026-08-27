# Combined Results

Means are computed over valid timing values in each benchmark's aligned query set. Improvement is `(baseline - condition) / baseline * 100`; Tool Benefit is Condition B improvement minus Condition A improvement, in percentage points. JOB is excluded because its Condition B result file is missing.

| Benchmark | Baseline mean (ms) | Condition A mean / improvement | A improved / regressed / tied | Condition B mean / improvement | B improved / regressed / tied | Tool Benefit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TPC-H | 21458.739 | 2465.219 / 88.512% | 11 / 11 / 0 | 703.056 / 96.724% | 19 / 3 / 0 | 8.212 pp |
| TPC-DS | 8015.225 | 6153.404 / 23.229% | 74 / 22 / 3 | 7442.458 / 7.146% | 65 / 31 / 3 | -16.083 pp |
| STATS | 27176.417 | 20428.836 / 24.829% | 57 / 89 / 0 | 27166.821 / 0.035% | 52 / 94 / 0 | -24.794 pp |
| TPC-C | 16.559 | 15.641 / 5.543% | 6 / 3 / 3 | 16.006 / 3.337% | 6 / 3 / 3 | -2.206 pp |
| TATP | 17.483 | 11.689 / 33.142% | 9 / 2 / 1 | 10.890 / 37.711% | 10 / 2 / 0 | 4.569 pp |
| SSB | 3751.628 | 2371.953 / 36.775% | 11 / 2 / 0 | 4469.543 / -19.136% | 5 / 8 / 0 | -55.911 pp |
| DSB | 9742.138 | 8438.581 / 13.381% | 49 / 4 / 0 | 10110.858 / -3.785% | 42 / 11 / 0 | -17.165 pp |
| JOB | N/A | N/A | N/A | N/A | N/A | N/A |

JOB is shown for completeness but is not included in the numeric analysis or chart.