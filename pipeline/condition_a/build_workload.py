#!/usr/bin/env python3
"""
Build workload.csv from Join Order Benchmark (JOB) .sql query files.

Usage:
    python build_workload.py <job_benchmark_dir> <output_csv_path>
"""

import csv
import glob
import os
import re
import sys

SKIP_FILES = {"schema.sql", "fkindexes.sql", "schematext.sql"}


def classify_complexity(sql_text: str) -> str:
    sql_lower = sql_text.lower()

    from_match = re.search(r"from\s+(.*?)\s+where", sql_lower, re.S)
    if from_match:
        from_clause = from_match.group(1)
        table_refs = [t.strip() for t in from_clause.split(",") if t.strip()]
        num_tables = len(table_refs)
    else:
        num_tables = 0

    num_tables += len(re.findall(r"\bjoin\b", sql_lower))

    has_aggregation = bool(
        re.search(r"\bgroup\s+by\b", sql_lower)
        or re.search(r"\b(count|sum|avg|min|max)\s*\(", sql_lower)
    )
    has_subquery = sql_text.count("(select") > 0

    if num_tables <= 3 and not has_aggregation and not has_subquery:
        return "Simple"
    elif num_tables > 6 or ((has_aggregation or has_subquery) and num_tables >= 4):
        return "Complex"
    else:
        return "Medium"


def build_workload(job_dir: str, output_path: str) -> None:
    sql_files = sorted(glob.glob(os.path.join(job_dir, "*.sql")))
    rows = []

    for filepath in sql_files:
        filename = os.path.basename(filepath)
        if filename in SKIP_FILES:
            continue

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            sql_text = f.read().strip()

        if not sql_text:
            continue

        query_id = os.path.splitext(filename)[0]
        query_text = " ".join(sql_text.split())
        complexity_tier = classify_complexity(sql_text)

        rows.append({
            "query_id": query_id,
            "query_text": query_text,
            "complexity_tier": complexity_tier,
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query_id", "query_text", "complexity_tier"]
        )
        writer.writeheader()
        writer.writerows(rows)

    tier_counts = {"Simple": 0, "Medium": 0, "Complex": 0}
    for row in rows:
        tier_counts[row["complexity_tier"]] += 1

    print(f"Wrote {len(rows)} queries to {output_path}")
    print(f"  Simple:  {tier_counts['Simple']}")
    print(f"  Medium:  {tier_counts['Medium']}")
    print(f"  Complex: {tier_counts['Complex']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    job_dir = os.path.expanduser(sys.argv[1])
    output_path = os.path.expanduser(sys.argv[2])
    build_workload(job_dir, output_path)
