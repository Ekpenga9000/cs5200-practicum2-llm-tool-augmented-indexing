# TPC-H Workload Classification Notes

The CSV file uses the canonical `Q1` through `Q22` query IDs. The classifications below follow the assignment rule:
- Simple: single table or simple filter, no joins
- Medium: 2-4 table joins or single aggregation
- Complex: 5+ table joins, nested subqueries, or multiple aggregations with grouping

- Q1: Medium. Single-table aggregate over `lineitem`; no joins, but it is still an aggregation query.
- Q2: Complex. Five-table join with a correlated subquery and grouping.
- Q3: Medium. Three-table join with one aggregate and grouping.
- Q4: Medium. Two-table query with one aggregate and a date filter.
- Q5: Medium. Four-table join with grouping.
- Q6: Medium. Single-table aggregate/filter query.
- Q7: Medium. Four-table join with grouping and ordering.
- Q8: Medium. Four-table join with one aggregate and grouping.
- Q9: Complex. Multi-table join with a correlated subquery and grouping.
- Q10: Medium. Four-table join with grouping and ordering.
- Q11: Medium. Three-table join with aggregation and grouping.
- Q12: Medium. Three-table join with aggregation and grouping.
- Q13: Complex. Nested subquery pattern with grouping and counting.
- Q14: Medium. Two-table aggregate query with a filter.
- Q15: Medium. Two-table aggregate query over a derived view.
- Q16: Complex. Multi-table filter query with nested anti-join logic.
- Q17: Complex. Correlated subquery with aggregation.
- Q18: Complex. Multi-table join with a large aggregate and HAVING clause.
- Q19: Medium. Two-table join query with filter predicates.
- Q20: Complex. Nested EXISTS subquery with multiple joins and date predicates.
- Q21: Complex. Multi-table join with nested EXISTS logic.
- Q22: Complex. Nested subqueries plus anti-join logic over customer and orders.
