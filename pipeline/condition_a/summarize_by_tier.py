#!/usr/bin/env python3
"""
Summarizes condition_a_results.csv (or condition_b_results.csv) by
complexity tier: average improvement, count of regressions vs
improvements, and the biggest wins/losses. Prints a table and writes
a markdown snippet suitable for pasting into analysis_summary.md.

Usage:
    python summarize_by_tier.py --workload workload.csv --results condition_a_results.csv
"""

import argparse
import csv


def parse_pct(s: str):
    if not s:
        return None
    return float(s.rstrip("%"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--label", default="Condition")
    args = parser.parse_args()

    with open(args.workload) as f:
        tier_by_qid = {r["query_id"]: r["complexity_tier"] for r in csv.DictReader(f)}

    with open(args.results) as f:
        rows = list(csv.DictReader(f))

    by_tier = {"Simple": [], "Medium": [], "Complex": []}
    for row in rows:
        qid = row["query_id"]
        tier = tier_by_qid.get(qid, "Unknown")
        pct = parse_pct(row.get("improvement_vs_baseline", ""))
        if tier in by_tier and pct is not None:
            by_tier[tier].append((qid, pct))

    print(f"\n=== {args.label} — Improvement vs. Baseline, by Tier ===\n")
    md_lines = [f"### {args.label} — Results by Complexity Tier\n",
                "| Tier | Queries | Avg Improvement | Regressions (worse) | Improved |",
                "|---|---|---|---|---|"]

    for tier in ["Simple", "Medium", "Complex"]:
        entries = by_tier[tier]
        if not entries:
            continue
        pcts = [p for _, p in entries]
        avg = sum(pcts) / len(pcts)
        regressions = [(q, p) for q, p in entries if p < 0]
        improved = [(q, p) for q, p in entries if p > 0]

        print(f"{tier}: {len(entries)} queries, avg improvement {avg:.1f}%, "
              f"{len(regressions)} regressed, {len(improved)} improved")

        md_lines.append(
            f"| {tier} | {len(entries)} | {avg:.1f}% | {len(regressions)} | {len(improved)} |"
        )

        if regressions:
            worst = sorted(regressions, key=lambda x: x[1])[:3]
            print(f"  Worst regressions: {worst}")

        if improved:
            best = sorted(improved, key=lambda x: -x[1])[:3]
            print(f"  Best improvements: {best}")
        print()

    md_lines.append("")
    md_path = args.results.replace(".csv", "_tier_summary.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"Wrote markdown summary to {md_path}")


if __name__ == "__main__":
    main()