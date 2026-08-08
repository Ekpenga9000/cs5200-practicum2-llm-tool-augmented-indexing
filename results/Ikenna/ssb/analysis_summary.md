# SSB Within-Schema Analysis

The SSB experiment compared a no-index baseline against Condition A
(no-tool LLM reasoning) and Condition B (tool-augmented LLM reasoning).

Condition A recommended 18 indexes, while Condition B finalized 14 indexes
after recording 81 tool-call log entries. Both conditions produced large
improvements on the highly selective Q1.2, Q1.3, and Q2.3 queries. For
example, Q1.3 improved from 3507.301 ms to 0.307 ms under Condition A and
0.304 ms under Condition B.

However, neither condition improved every query. Condition A made Q1.1 and
Q3.1 slower, with regressions of 44.23% and 42.32%, respectively. Condition B
produced more widespread regressions. Q2.1 increased from 3376.666 ms to
12035.003 ms, and Q4.3 increased from 2766.376 ms to 10799.733 ms.

Condition A outperformed Condition B on most of the Q3 and Q4 workloads.
For example, Q3.3 improved by 94.04% under Condition A but became 8.12%
slower under Condition B. Q3.4 improved by 99.85% under Condition A but
became 2.58% slower under Condition B.

These results suggest that access to PostgreSQL planner-cost estimates did
not consistently produce better actual execution-time outcomes. Condition B
could verify estimated query costs for individual candidates, but the final
combination of indexes sometimes caused PostgreSQL to choose worse execution
plans. This demonstrates that lower estimated cost for isolated candidates
does not guarantee lower measured runtime for the complete workload.
