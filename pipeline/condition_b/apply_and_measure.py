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

import os
import sys
import json
import csv
import getpass
import statistics
import psycopg2

RUNS_PER_QUERY = 7  # take the median to smooth out timing noise on sub-ms queries


def resolve_database_name(schema_name: str) -> str:
    env_db = os.getenv("DB_DATABASE") or os.getenv("PGDATABASE")
    candidates = []
    if env_db:
        candidates.append(env_db)
    candidates.extend([f"{schema_name}_test", schema_name, "postgres"])
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate
    return "postgres"


def measure_query(cur, query_text):
    statements = [statement.strip() for statement in query_text.split(";") if statement.strip()]
    explainable_index = next(
        (index for index, statement in enumerate(statements)
         if statement.lower().startswith(("select", "with", "values"))),
        None,
    )
    explainable_statement = query_text.strip().rstrip(";")
    setup_statements = []
    cleanup_statements = []
    if explainable_index is not None and len(statements) > 1:
        setup_statements = statements[:explainable_index]
        explainable_statement = statements[explainable_index]
        cleanup_statements = statements[explainable_index + 1:]

    for statement in setup_statements:
        cur.execute(statement)

    times = []
    try:
        cur.execute("SET statement_timeout = 120000")
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {explainable_statement}")
        for _ in range(RUNS_PER_QUERY):
            cur.execute("SET statement_timeout = 120000")
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {explainable_statement}")
            plan_json = cur.fetchone()[0]
            times.append(plan_json[0]["Execution Time"])
        return statistics.median(times)
    finally:
        for statement in cleanup_statements:
            try:
                cur.execute(statement)
            except Exception:
                cur.connection.rollback()


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

    pw = os.environ.get("PGPASSWORD") or getpass.getpass("Postgres password for user 'postgres': ")
    db_name = resolve_database_name(schema_workload["schema_name"])
    conn = psycopg2.connect(
        dbname=db_name,
        user=os.getenv("PGUSER", "postgres"),
        password=pw,
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
    )
    conn.autocommit = True
    cur = conn.cursor()

    schema_name = schema_workload["schema_name"]
    cur.execute(f'SET search_path TO "{schema_name}", public')
    cur.execute("SET statement_timeout = 0")

    apply_indexes(cur, recommendation["recommended_indexes"])
    cur.execute("SET statement_timeout = 120000")

    rows = []
    for q in schema_workload["queries"]:
        query_id = q["query_id"]
        query_text = q["query_text"]
        print(f"Re-running {query_id} with new indexes...")

        try:
            exec_time_after = measure_query(cur, query_text)
        except Exception as e:
            conn.rollback()
            if getattr(e, "pgcode", None) == "57014" or "statement timeout" in str(e).lower():
                print(f"  {query_id}: TIMEOUT - 120000 ms")
                exec_time_after = 120000.0
            else:
                print(f"  {query_id}: ERROR - {e}")
                exec_time_after = None

        before = baseline_times.get(query_id)
        improvement_pct = None
        if exec_time_after is not None and before and before > 0:
            improvement_pct = round((before - exec_time_after) / before * 100, 2)

        rows.append({
            "query_id": query_id,
            "recommended_indexes": json.dumps(recommendation["recommended_indexes"]),
            "llm_reasoning_text": recommendation["llm_reasoning_text"],
            "execution_time_ms_after": exec_time_after,
            "improvement_vs_baseline": improvement_pct,
            "tool_call_log": json.dumps(recommendation.get("tool_call_log", [])),
        })

    cur.close()
    conn.close()

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "query_id", "recommended_indexes", "llm_reasoning_text",
            "execution_time_ms_after", "improvement_vs_baseline", "tool_call_log",
        ])
        writer.writeheader()
        writer.writerows(rows)

    # tool_call_log as its own linked file, per team's format decision --
    # written next to the output CSV, not the current working directory.
    log_path = os.path.join(os.path.dirname(out_csv_path) or ".", "tool_call_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(recommendation["tool_call_log"], f, indent=2)

    print(f"\nWrote {len(rows)} rows to {out_csv_path}")
    print(f"Wrote {log_path}")
    print("\nBefore -> After (ms):")
    for r in rows:
        before = baseline_times.get(r["query_id"])
        after = r["execution_time_ms_after"]
        before_str = f"{before:.3f}" if isinstance(before, (int, float)) else "NA"
        after_str = f"{after:.3f}" if isinstance(after, (int, float)) else "NA"
        print(f"  {r['query_id']}: {before_str} -> {after_str}  "
              f"({r['improvement_vs_baseline']}% change)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print('Usage: py apply_and_measure.py "<schema_workload.json>" <recommendation.json> <baseline.csv> <out.csv>')
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
