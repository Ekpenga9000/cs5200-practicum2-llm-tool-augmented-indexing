"""
Step 1 baseline runner. Runs EXPLAIN ANALYZE on every query in the workload
against the schema as-is (PK/FK indexes only, nothing extra), and writes
baseline_results.csv in the exact format agreed with the team:

    query_id, execution_time_ms, query_plan_text

Usage:
    py baseline_runner.py "F:\\个人资料\\files (2)\\tpcc_schema_workload.json" baseline_results.csv
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
        cleanup_statements = [
            statement for statement in statements[explainable_index + 1:]
            if not statement.lower().startswith(("select", "with", "values"))
        ]

    for statement in setup_statements:
        cur.execute(statement)

    times = []
    try:
        cur.execute("SET statement_timeout = 120000")
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {explainable_statement}")
        plan_json = cur.fetchone()[0]
        for _ in range(RUNS_PER_QUERY):
            cur.execute("SET statement_timeout = 120000")
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {explainable_statement}")
            plan_json = cur.fetchone()[0]
            times.append(plan_json[0]["Execution Time"])
        return statistics.median(times), plan_json
    finally:
        for statement in cleanup_statements:
            try:
                cur.execute(statement)
            except Exception:
                cur.connection.rollback()


def run_baseline(schema_workload_path, out_csv_path):
    with open(schema_workload_path, encoding="utf-8") as f:
        schema_workload = json.load(f)

    pw = os.environ.get("PGPASSWORD") or getpass.getpass("Postgres password for user 'postgres': ")
    db_name = resolve_database_name(schema_workload["schema_name"])
    conn = psycopg2.connect(
        dbname=db_name, user=os.getenv("PGUSER", "postgres"),
        password=pw, host=os.getenv("PGHOST", "localhost"), port=int(os.getenv("PGPORT", "5432")),
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Running ANALYZE on all tables (fresh planner statistics for baseline)...")
    cur.execute(f'SET search_path TO "{schema_workload["schema_name"]}", public')
    cur.execute("SET statement_timeout = 120000")
    cur.execute("ANALYZE;")

    rows = []
    for q in schema_workload["queries"]:
        query_id = q["query_id"]
        query_text = q["query_text"]
        print(f"Running {query_id}...")

        try:
            execution_time_ms, plan_json = measure_query(cur, query_text)
            plan_text = json.dumps(plan_json, indent=2)
        except Exception as e:
            conn.rollback()
            if getattr(e, "pgcode", None) == "57014" or "statement timeout" in str(e).lower():
                print(f"  {query_id}: TIMEOUT - 120000 ms")
                execution_time_ms = 120000.0
                plan_text = "TIMEOUT - query exceeded 120000 ms limit"
            else:
                raise

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
