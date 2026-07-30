#!/usr/bin/env python3
"""
Build workload.csv from Join Order Benchmark (JOB) .sql query files.

Usage:
    python build_workload.py <job_benchmark_dir> <output_csv_path>
"""

import csv
import glob
import math
import os
import re
import sys

SKIP_FILES = {"schema.sql", "fkindexes.sql", "schematext.sql"}


def extract_query_features(sql_text: str) -> dict:
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
    has_subquery = "(select" in sql_lower  # case-insensitive via sql_lower

    return {
        "num_tables": num_tables,
        "has_aggregation": has_aggregation,
        "has_subquery": has_subquery,
    }


def complexity_score(features: dict) -> int:
    # Deterministic weighted score
    return (
        features["num_tables"]
        + int(features["has_aggregation"])
        + int(features["has_subquery"])
    )


def percentile_nearest_rank(values: list[int], p: float) -> int:
    # Deterministic percentile: nearest-rank method
    if not values:
        return 0
    sorted_vals = sorted(values)
    rank = max(1, math.ceil(p * len(sorted_vals)))
    return sorted_vals[rank - 1]


def derive_complexity_cutoffs(scores: list[int]) -> tuple[int, int]:
    simple_max = percentile_nearest_rank(scores, 0.33)
    complex_min = percentile_nearest_rank(scores, 0.66)
    # Keep a valid middle bucket if percentiles collapse
    if complex_min <= simple_max:
        complex_min = simple_max + 1
    return simple_max, complex_min


def classify_complexity(score: int, simple_max: int, complex_min: int) -> str:
    if score <= simple_max:
        return "Simple"
    if score >= complex_min:
        return "Complex"
    return "Medium"


def build_workload(job_dir: str, output_path: str) -> None:
    sql_files = sorted(glob.glob(os.path.join(job_dir, "*.sql")))
    staged = []

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
        features = extract_query_features(sql_text)
        score = complexity_score(features)

        staged.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "score": score,
            }
        )

    scores = [r["score"] for r in staged]

    # Sanity check: verify the score distribution has actual spread
    # before trusting the derived cutoffs.
    if scores:
        print(
            f"Score distribution: min={min(scores)}, max={max(scores)}, "
            f"median={sorted(scores)[len(scores)//2]}"
        )
    else:
        print("Score distribution: no queries found")

    simple_max, complex_min = derive_complexity_cutoffs(scores)

    rows = []
    for r in staged:
        rows.append(
            {
                "query_id": r["query_id"],
                "query_text": r["query_text"],
                "complexity_tier": classify_complexity(
                    r["score"], simple_max, complex_min
                ),
            }
        )

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
    print(f"Cutoffs (score): Simple <= {simple_max}, Complex >= {complex_min}")
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