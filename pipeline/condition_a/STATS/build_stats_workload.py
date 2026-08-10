#!/usr/bin/env python3
"""
Converts the STATS-CEB workload file (true_cardinality||SQL per line) into
workload.csv with query_id, query_text, complexity_tier, using the same
tertile-based table-count classification as the JOB workload builder.
"""

import csv
import re
import sys


def count_tables(sql_text: str) -> int:
    sql_lower = sql_text.lower()
    from_match = re.search(r"from\s+(.*?)\s+where", sql_lower, re.S)
    if from_match:
        table_refs = [t.strip() for t in from_match.group(1).split(",") if t.strip()]
        num_tables = len(table_refs)
    else:
        num_tables = 0
    num_tables += len(re.findall(r"\bjoin\b", sql_lower))
    return num_tables


def compute_tertile_cutoffs(counts):
    s = sorted(counts)
    n = len(s)
    return s[n // 3], s[(2 * n) // 3]


def main():
    if len(sys.argv) != 3:
        print("Usage: python build_stats_workload.py <stats_CEB.sql> <output.csv>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    queries = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            _, sql_text = line.split("||", 1)
            queries.append(sql_text)

    table_counts = [count_tables(q) for q in queries]
    low_cut, high_cut = compute_tertile_cutoffs(table_counts)

    rows = []
    for i, sql_text in enumerate(queries, start=1):
        n = count_tables(sql_text)
        tier = "Simple" if n <= low_cut else "Medium" if n <= high_cut else "Complex"
        rows.append({
            "query_id": f"s{i}",
            "query_text": " ".join(sql_text.split()),
            "complexity_tier": tier,
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "query_text", "complexity_tier"])
        writer.writeheader()
        writer.writerows(rows)

    tier_counts = {"Simple": 0, "Medium": 0, "Complex": 0}
    for r in rows:
        tier_counts[r["complexity_tier"]] += 1

    print(f"Wrote {len(rows)} queries to {output_path}")
    print(f"Cutoffs: Simple <= {low_cut}, Medium <= {high_cut}, Complex > {high_cut}")
    print(f"  Simple: {tier_counts['Simple']}  Medium: {tier_counts['Medium']}  Complex: {tier_counts['Complex']}")


if __name__ == "__main__":
    main()
