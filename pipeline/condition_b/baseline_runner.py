"""
Step 1 baseline runner. Runs EXPLAIN ANALYZE on every query in the workload
against the schema as-is (PK/FK indexes only, nothing extra), and writes
baseline_results.csv in the exact format agreed with the team:

    query_id, execution_time_ms, query_plan_text

Usage:
    py baseline_runner.py "F:\\个人资料\\files (2)\\tpcc_schema_workload.json" baseline_results.csv
"""

import sys
import json
import csv
import getpass
import statistics
import psycopg2

RUNS_PER_QUERY = 7  # take the median to smooth out timing noise on sub-ms queries


def measure_query(cur, query_text):
    times = []
    for _ in range(RUNS_PER_QUERY):
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query_text}")
        plan_json = cur.fetchone()[0]
        times.append(plan_json[0]["Execution Time"])
    return statistics.median(times), plan_json


def run_baseline(schema_workload_path, out_csv_path):
    with open(schema_workload_path, encoding="utf-8") as f:
        schema_workload = json.load(f)

    pw = getpass.getpass("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(
        dbname=schema_workload["schema_name"], user="postgres",
        password=pw, host="localhost", port=5432,
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Running ANALYZE on all tables (fresh planner statistics for baseline)...")
    cur.execute("ANALYZE;")

    rows = []
    for q in schema_workload["queries"]:
        query_id = q["query_id"]
        query_text = q["query_text"]
        print(f"Running {query_id}...")

        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query_text}")  # warm-up run (fills caches)
        execution_time_ms, plan_json = measure_query(cur, query_text)
        plan_text = json.dumps(plan_json, indent=2)

        rows.append({
            "query_id": query_id,
            "execution_time_ms": execution_time_ms,
            "query_plan_text": plan_text,
        })

    cur.close()
    conn.close()

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "execution_time_ms", "query_plan_text"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {out_csv_path}")
    for r in rows:
        print(f"  {r['query_id']}: {r['execution_time_ms']:.3f} ms")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: py baseline_runner.py "<schema_workload.json>" <out_csv_path>')
        sys.exit(1)
    run_baseline(sys.argv[1], sys.argv[2])
