#!/usr/bin/env python3
"""
Run every query in workload.csv against a Postgres database with
EXPLAIN ANALYZE, no additional indexes, and record baseline timing as
the median of RUNS_PER_QUERY runs -- same methodology used for
TPC-C/TATP, so all schemas are measured consistently.

Usage:
    python run_baseline.py --workload workload.csv --output baseline_results.csv \
        [--host localhost] [--port 5432] [--db postgres] [--user postgres] [--password postgres]
"""

import argparse
import csv
import os
import statistics

import psycopg2

RUNS_PER_QUERY = 7  # median of 7, matching Condition A/B remeasurement methodology


def run_baseline(conn, workload_rows):
    results = []
    with conn.cursor() as cur:
        for row in workload_rows:
            query_id = row["query_id"]
            clean_sql = row["query_text"].strip().rstrip(";")

            times = []
            plan_text = ""
            try:
                for _ in range(RUNS_PER_QUERY):
                    cur.execute(f"EXPLAIN (ANALYZE, FORMAT TEXT) {clean_sql}")
                    plan_lines = [r[0] for r in cur.fetchall()]
                    plan_text = " | ".join(plan_lines)
                    for line in plan_lines:
                        if "Execution Time:" in line:
                            times.append(
                                float(line.split("Execution Time:")[1].strip().split(" ")[0])
                            )
                            break

                median_time = statistics.median(times) if times else None
                results.append({
                    "query_id": query_id,
                    "execution_time_ms": median_time if median_time is not None else "",
                    "query_plan_text": plan_text,
                })
                print(f"{query_id}: median {median_time} ms over {len(times)} runs")

            except Exception as e:
                conn.rollback()
                print(f"{query_id}: ERROR - {e}")
                results.append({
                    "query_id": query_id,
                    "execution_time_ms": "",
                    "query_plan_text": f"ERROR: {e}",
                })

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="5432")
    parser.add_argument("--db", default="postgres")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = args.password or os.getenv("PGPASSWORD", "postgres")

    with open(args.workload) as f:
        workload_rows = list(csv.DictReader(f))

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.db,
        user=args.user, password=password,
    )
    conn.autocommit = True

    results = run_baseline(conn, workload_rows)
    conn.close()

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query_id", "execution_time_ms", "query_plan_text"]
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} rows to {args.output}")


if __name__ == "__main__":
    main()
