#!/usr/bin/env python3
"""
Applies the overall recommended indexes from a Condition A (or B) run,
re-runs every query in workload.csv with EXPLAIN ANALYZE, and fills in
execution_time_ms_after and improvement_vs_baseline in the results CSV.

Usage:
    python apply_and_measure.py \
        --workload workload.csv \
        --baseline baseline_results.csv \
        --results condition_a_results.csv \
        --indexes-file condition_a_results_overall_indexes.txt \
        [--host localhost] [--port 5432] [--db postgres] [--user postgres] [--password postgres]
"""

import argparse
import csv
import os
import re

import psycopg2


def apply_indexes(conn, index_statements):
    with conn.cursor() as cur:
        for stmt in index_statements:
            stmt = stmt.strip().rstrip(";")
            if not stmt:
                continue

            m = re.match(r"create index (\w+)", stmt, re.I)
            if m:
                idx_name = m.group(1)
                try:
                    cur.execute(f"DROP INDEX IF EXISTS {idx_name};")
                except Exception as e:
                    print(f"  (drop skipped: {e})")

            try:
                cur.execute(stmt)
                print(f"  Applied: {stmt}")
            except Exception as e:
                conn.rollback()
                print(f"  FAILED to apply: {stmt}\n    {e}")


def split_statements(query_text):
    return [statement.strip() for statement in query_text.split(";") if statement.strip()]


def is_explainable_statement(statement):
    return bool(re.match(r"^(select|with|values)\b", statement, re.I))


def run_workload(conn, workload_rows):
    results = {}
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 120000")

        for row in workload_rows:
            query_id = row["query_id"]
            clean_sql = row["query_text"].strip().rstrip(";")
            statements = split_statements(clean_sql)
            explainable_sql = clean_sql
            post_statements = []

            if len(statements) > 1:
                explainable_index = next(
                    (index for index, statement in enumerate(statements) if is_explainable_statement(statement)),
                    -1,
                )

                if explainable_index >= 0:
                    for statement in statements[:explainable_index]:
                        cur.execute(statement)

                    explainable_sql = statements[explainable_index]
                    post_statements = statements[explainable_index + 1:]

            try:
                cur.execute(f"EXPLAIN (ANALYZE, FORMAT TEXT) {explainable_sql}")
                plan_lines = [r[0] for r in cur.fetchall()]

                exec_time_ms = None
                for line in plan_lines:
                    if "Execution Time:" in line:
                        exec_time_ms = float(
                            line.split("Execution Time:")[1].strip().split(" ")[0]
                        )
                        break

                results[query_id] = exec_time_ms
                print(f"  {query_id}: {exec_time_ms} ms")

            except Exception as e:
                conn.rollback()
                if getattr(e, "pgcode", None) == "57014" or "statement timeout" in str(e).lower():
                    print(f"  {query_id}: TIMEOUT - 120000 ms")
                    results[query_id] = 120000
                else:
                    print(f"  {query_id}: ERROR - {e}")
                    results[query_id] = None

            finally:
                for statement in post_statements:
                    try:
                        cur.execute(statement)
                    except Exception:
                        conn.rollback()

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--indexes-file", required=True)
    parser.add_argument("--schema-name", default=os.getenv("SCHEMA_NAME", "tpch"))
    parser.add_argument("--database", default=os.getenv("DB_DATABASE", os.getenv("PGDATABASE", "postgres")))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="5432")
    parser.add_argument("--db", default="postgres")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgres")
    args = parser.parse_args()

    with open(args.workload) as f:
        workload_rows = list(csv.DictReader(f))

    with open(args.baseline) as f:
        baseline_rows = list(csv.DictReader(f))
    baseline_by_qid = {
        r["query_id"]: float(r["execution_time_ms"])
        for r in baseline_rows if r["execution_time_ms"]
    }

    with open(args.indexes_file) as f:
        index_statements = [line.strip() for line in f if line.strip()]

    with open(args.results) as f:
        results_rows = list(csv.DictReader(f))

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.database,
        user=args.user, password=args.password,
    )
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute(f'SET search_path TO "{args.schema_name}", public')

    print(f"Applying {len(index_statements)} recommended index(es)...")
    apply_indexes(conn, index_statements)

    print(f"\nRe-running {len(workload_rows)} queries with indexes applied...")
    after_times = run_workload(conn, workload_rows)
    conn.close()

    for row in results_rows:
        qid = row["query_id"]
        after = after_times.get(qid)
        before = baseline_by_qid.get(qid)

        row["execution_time_ms_after"] = after if after is not None else ""

        if after is not None and before is not None and before > 0:
            improvement_pct = ((before - after) / before) * 100
            row["improvement_vs_baseline"] = f"{improvement_pct:.1f}%"
        else:
            row["improvement_vs_baseline"] = ""

    fieldnames = list(results_rows[0].keys()) if results_rows else [
        "query_id", "recommended_indexes", "llm_reasoning_text",
        "execution_time_ms_after", "improvement_vs_baseline",
    ]
    with open(args.results, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_rows)

    print(f"\nUpdated {args.results} with execution_time_ms_after and improvement_vs_baseline")


if __name__ == "__main__":
    main()
