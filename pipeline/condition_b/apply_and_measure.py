"""
Applies Condition B's final recommended indexes for real, re-runs EXPLAIN
ANALYZE on the full workload, and combines with baseline_results.csv to
produce condition_b_results.csv in the exact deliverable format:

    query_id, recommended_indexes, llm_reasoning_text,
    execution_time_ms_after, improvement_vs_baseline

tool_call_log is written separately as tool_call_log.json (per team's
decision that a linked file is cleaner than cramming it into the CSV).

This is standing in for Ikenna's measurement module until it's merged --
same output format either way.

Usage:
    py apply_and_measure.py "F:\\个人资料\\files (2)\\tpcc_schema_workload.json" ^
        condition_b_recommendation.json baseline_results.csv condition_b_results.csv
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
    return statistics.median(times)


def load_baseline(baseline_csv_path):
    baseline = {}
    with open(baseline_csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            baseline[row["query_id"]] = float(row["execution_time_ms"])
    return baseline


def apply_indexes(cur, recommended_indexes):
    tables_touched = set()
    for idx in recommended_indexes:
        table = idx["table"]
        cols = ", ".join(idx["columns"])
        name = f"idx_{table}_{'_'.join(idx['columns'])}"
        print(f"Creating index {name} ON {table} ({cols})...")
        cur.execute(f"DROP INDEX IF EXISTS {name};")
        cur.execute(f"CREATE INDEX {name} ON {table} ({cols});")
        tables_touched.add(table)

    for table in tables_touched:
        print(f"Running ANALYZE {table} (refresh planner statistics)...")
        cur.execute(f"ANALYZE {table};")


def run(schema_workload_path, recommendation_path, baseline_csv_path, out_csv_path):
    with open(schema_workload_path, encoding="utf-8") as f:
        schema_workload = json.load(f)
    with open(recommendation_path, encoding="utf-8") as f:
        recommendation = json.load(f)

    baseline_times = load_baseline(baseline_csv_path)

    pw = getpass.getpass("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(
        dbname=schema_workload["schema_name"], user="postgres",
        password=pw, host="localhost", port=5432,
    )
    conn.autocommit = True
    cur = conn.cursor()

    apply_indexes(cur, recommendation["recommended_indexes"])

    rows = []
    for q in schema_workload["queries"]:
        query_id = q["query_id"]
        query_text = q["query_text"]
        print(f"Re-running {query_id} with new indexes...")

        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query_text}")  # warm-up run
        exec_time_after = measure_query(cur, query_text)

        before = baseline_times.get(query_id)
        improvement_pct = None
        if before and before > 0:
            improvement_pct = round((before - exec_time_after) / before * 100, 2)

        rows.append({
            "query_id": query_id,
            "recommended_indexes": json.dumps(recommendation["recommended_indexes"]),
            "llm_reasoning_text": recommendation["llm_reasoning_text"],
            "execution_time_ms_after": exec_time_after,
            "improvement_vs_baseline": improvement_pct,
        })

    cur.close()
    conn.close()

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "query_id", "recommended_indexes", "llm_reasoning_text",
            "execution_time_ms_after", "improvement_vs_baseline",
        ])
        writer.writeheader()
        writer.writerows(rows)

    # tool_call_log as its own linked file, per team's format decision
    with open("tool_call_log.json", "w", encoding="utf-8") as f:
        json.dump(recommendation["tool_call_log"], f, indent=2)

    print(f"\nWrote {len(rows)} rows to {out_csv_path}")
    print("Wrote tool_call_log.json")
    print("\nBefore -> After (ms):")
    for r in rows:
        before = baseline_times.get(r["query_id"])
        print(f"  {r['query_id']}: {before:.3f} -> {r['execution_time_ms_after']:.3f}  "
              f"({r['improvement_vs_baseline']}% change)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print('Usage: py apply_and_measure.py "<schema_workload.json>" <recommendation.json> <baseline.csv> <out.csv>')
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
