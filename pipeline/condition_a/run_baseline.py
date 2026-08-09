#!/usr/bin/env python3
"""
Run every query in workload.csv against a Postgres database with
EXPLAIN ANALYZE, no additional indexes, and record baseline timing.

Usage:
    python run_baseline.py --workload workload.csv --output baseline_results.csv \
        [--host localhost] [--port 5432] [--db postgres] [--user postgres] [--password postgres]
"""

import argparse
import csv

import psycopg2


def run_baseline(conn, workload_rows):
    results = []
    with conn.cursor() as cur:
        for row in workload_rows:
            query_id = row["query_id"]
            query_text = row["query_text"]

            clean_sql = query_text.strip().rstrip(";")

            try:
                cur.execute(f"EXPLAIN (ANALYZE, FORMAT TEXT) {clean_sql}")
                plan_lines = [r[0] for r in cur.fetchall()]
                plan_text = " | ".join(plan_lines)

                exec_time_ms = None
                for line in plan_lines:
                    if "Execution Time:" in line:
                        exec_time_ms = float(
                            line.split("Execution Time:")[1].strip().split(" ")[0]
                        )
                        break

                results.append({
                    "query_id": query_id,
                    "execution_time_ms": exec_time_ms if exec_time_ms is not None else "",
                    "query_plan_text": plan_text,
                })
                print(f"{query_id}: {exec_time_ms} ms")

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
    parser.add_argument("--password", default="postgres")
    args = parser.parse_args()

    with open(args.workload) as f:
        workload_rows = list(csv.DictReader(f))

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.db,
        user=args.user, password=args.password,
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
