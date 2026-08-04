#!/usr/bin/env python3
"""
Build workload.csv from Join Order Benchmark (JOB) .sql query files.

Complexity tiers (Simple/Medium/Complex) are assigned based on table
count, using thresholds computed from the ACTUAL distribution of table
counts across this query set (tertiles), rather than a fixed guess.
JOB queries commonly join far more tables than typical textbook
examples, so a hardcoded cutoff collapses everything into one tier.

Usage:
    python build_workload.py <job_benchmark_dir> <output_csv_path>
    python build_workload.py <job_benchmark_dir> --diagnose
"""

import csv
import glob
import os
import re
import sys

SKIP_FILES = {"schema.sql", "fkindexes.sql", "schematext.sql"}


def count_tables(sql_text: str) -> int:
    sql_lower = sql_text.lower()

    from_match = re.search(r"from\s+(.*?)\s+where", sql_lower, re.S)
    if from_match:
        from_clause = from_match.group(1)
        table_refs = [t.strip() for t in from_clause.split(",") if t.strip()]
        num_tables = len(table_refs)
    else:
        num_tables = 0

    num_tables += len(re.findall(r"\bjoin\b", sql_lower))
    return num_tables


def load_queries(job_dir: str):
    sql_files = sorted(glob.glob(os.path.join(job_dir, "*.sql")))
    queries = []
    for filepath in sql_files:
        filename = os.path.basename(filepath)
        if filename in SKIP_FILES:
            continue
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            sql_text = f.read().strip()
        if not sql_text:
            continue
        query_id = os.path.splitext(filename)[0]
        queries.append((query_id, sql_text))
    return queries


def compute_tertile_cutoffs(table_counts):
    """
    Splits into three roughly equal-sized groups by table count.
    Returns (low_cut, high_cut): Simple <= low_cut, Medium <= high_cut,
    else Complex.
    """
    sorted_counts = sorted(table_counts)
    n = len(sorted_counts)
    low_idx = n // 3
    high_idx = (2 * n) // 3
    low_cut = sorted_counts[low_idx]
    high_cut = sorted_counts[high_idx]
    return low_cut, high_cut


def diagnose(job_dir: str) -> None:
    queries = load_queries(job_dir)
    counts = [(qid, count_tables(sql)) for qid, sql in queries]
    counts_sorted = sorted(counts, key=lambda x: x[1])

    print(f"{len(queries)} queries loaded.\n")
    print("Table count distribution (sorted):")
    for qid, n in counts_sorted:
        print(f"  {qid:>6}: {n} tables")

    table_counts = [n for _, n in counts]
    low_cut, high_cut = compute_tertile_cutoffs(table_counts)
    print(f"\nSuggested tertile cutoffs: Simple <= {low_cut}, "
          f"Medium <= {high_cut}, Complex > {high_cut}")

    tier_counts = {"Simple": 0, "Medium": 0, "Complex": 0}
    for _, n in counts:
        if n <= low_cut:
            tier_counts["Simple"] += 1
        elif n <= high_cut:
            tier_counts["Medium"] += 1
        else:
            tier_counts["Complex"] += 1
    print(f"Resulting split: Simple={tier_counts['Simple']}, "
          f"Medium={tier_counts['Medium']}, Complex={tier_counts['Complex']}")


def build_workload(job_dir: str, output_path: str) -> None:
    queries = load_queries(job_dir)
    table_counts = [count_tables(sql) for _, sql in queries]
    low_cut, high_cut = compute_tertile_cutoffs(table_counts)

    rows = []
    for query_id, sql_text in queries:
        num_tables = count_tables(sql_text)
        if num_tables <= low_cut:
            tier = "Simple"
        elif num_tables <= high_cut:
            tier = "Medium"
        else:
            tier = "Complex"

        query_text = " ".join(sql_text.split())
        rows.append({
            "query_id": query_id,
            "query_text": query_text,
            "complexity_tier": tier,
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
    print(f"Cutoffs used: Simple <= {low_cut} tables, "
          f"Medium <= {high_cut} tables, Complex > {high_cut} tables")
    print(f"  Simple:  {tier_counts['Simple']}")
    print(f"  Medium:  {tier_counts['Medium']}")
    print(f"  Complex: {tier_counts['Complex']}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] == "--diagnose":
        diagnose(os.path.expanduser(sys.argv[1]))
    elif len(sys.argv) == 3:
        job_dir = os.path.expanduser(sys.argv[1])
        output_path = os.path.expanduser(sys.argv[2])
        build_workload(job_dir, output_path)
    else:
        print(__doc__)
        sys.exit(1)