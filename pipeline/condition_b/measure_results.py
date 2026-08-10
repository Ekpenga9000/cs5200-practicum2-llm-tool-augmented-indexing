"""
Rigorous, apples-to-apples measurement for a condition's results CSV.

Resets the DB to a PK/FK-only state, applies the condition's recommended
indexes, then re-runs every query with EXPLAIN ANALYZE using the SAME timing
method as baseline_runner.py / condition_b's apply_and_measure.py (one warm-up
run + median of N runs). Fills execution_time_ms_after and
improvement_vs_baseline in place, preserving all other columns (e.g. the LLM
reasoning already in the CSV).

Works for Condition A OR B: it reads the CREATE INDEX statements from an
--indexes-file, so it is independent of the recommended_indexes column format.

Non-interactive (password via --password), so it can be scripted.

Usage:
    py measure_results.py \
        --results   results/Alan/tpcc/condition_a_results.csv \
        --indexes-file results/Alan/tpcc/condition_a_results_overall_indexes.txt \
        --workload  results/Alan/tpcc/tpcc_workload.csv \
        --baseline  results/Alan/tpcc/baseline_results.csv \
        --db tpcc --user postgres --password YOURPW [--runs 7]
"""

import argparse
import csv
import os
import statistics

import psycopg2


def reset_secondary_indexes(conn):
    """Drop every non-PK/FK ('idx_%') index so we measure from a clean base."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname LIKE 'idx_%';"
        )
        names = [r[0] for r in cur.fetchall()]
        for name in names:
            cur.execute(f"DROP INDEX IF EXISTS {name};")
    if names:
        print(f"Reset: dropped {len(names)} secondary index(es): {', '.join(names)}")
    else:
        print("Reset: no secondary indexes to drop (already clean).")


def apply_indexes(conn, index_statements):
    with conn.cursor() as cur:
        for stmt in index_statements:
            stmt = stmt.strip().rstrip(";")
            if not stmt:
                continue
            try:
                cur.execute(stmt + ";")
                print(f"  Applied: {stmt}")
            except Exception as e:
                conn.rollback()
                print(f"  FAILED to apply: {stmt}\n    {e}")
    # refresh planner statistics on everything we just indexed
    with conn.cursor() as cur:
        cur.execute("ANALYZE;")


def measure_query(cur, query_text, runs):
    clean_sql = query_text.strip().rstrip(";")
    cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {clean_sql}")  # warm-up
    cur.fetchone()
    times = []
    for _ in range(runs):
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {clean_sql}")
        plan_json = cur.fetchone()[0]
        times.append(plan_json[0]["Execution Time"])
    return statistics.median(times)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--indexes-file", required=True)
    p.add_argument("--workload", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", default="5432")
    p.add_argument("--db", default="tpcc")
    p.add_argument("--user", default="postgres")
    p.add_argument("--password", default=os.environ.get("PGPASSWORD"))
    p.add_argument("--runs", type=int, default=7)
    args = p.parse_args()

    with open(args.workload, encoding="utf-8") as f:
        workload = {r["query_id"]: r["query_text"] for r in csv.DictReader(f)}
    with open(args.baseline, encoding="utf-8") as f:
        baseline = {r["query_id"]: float(r["execution_time_ms"])
                    for r in csv.DictReader(f) if r["execution_time_ms"]}
    with open(args.indexes_file, encoding="utf-8") as f:
        index_statements = [line.strip() for line in f if line.strip()]
    with open(args.results, encoding="utf-8") as f:
        results_rows = list(csv.DictReader(f))
        fieldnames = results_rows[0].keys() if results_rows else []

    conn = psycopg2.connect(host=args.host, port=args.port, dbname=args.db,
                            user=args.user, password=args.password)
    conn.autocommit = True

    reset_secondary_indexes(conn)
    print(f"Applying {len(index_statements)} recommended index(es)...")
    apply_indexes(conn, index_statements)

    print(f"\nRe-running {len(workload)} queries (warm-up + median of {args.runs})...")
    cur = conn.cursor()
    for row in results_rows:
        qid = row["query_id"]
        after = measure_query(cur, workload[qid], args.runs)
        before = baseline.get(qid)
        row["execution_time_ms_after"] = round(after, 3)
        row["improvement_vs_baseline"] = (
            round((before - after) / before * 100, 2)
            if before and before > 0 else ""
        )
        print(f"  {qid}: {before} -> {after:.3f} ms "
              f"({row['improvement_vs_baseline']}% change)")
    cur.close()
    conn.close()

    with open(args.results, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(results_rows)
    print(f"\nUpdated {args.results} (median-of-{args.runs} timing).")


if __name__ == "__main__":
    main()
