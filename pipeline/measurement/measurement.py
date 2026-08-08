"""
Measurement and Aggregation Module

This module:
1. Loads a schema/workload JSON file.
2. Loads baseline execution times.
3. Loads Condition A or Condition B index recommendations.
4. Applies the recommended indexes to PostgreSQL.
5. Runs EXPLAIN ANALYZE on every workload query.
6. Compares the new execution times against baseline.
7. Writes the standardized results CSV.
"""
import os
import argparse
import csv
import json
from pathlib import Path
from typing import Any

import psycopg2

from utils import (
    apply_indexes,
    calculate_improvement,
    drop_indexes,
    load_baseline,
    measure_query,
)


RESULT_FIELDS = [
    "query_id",
    "recommended_indexes",
    "llm_reasoning_text",
    "execution_time_ms_after",
    "improvement_vs_baseline",
]


def load_json(path: str) -> dict[str, Any]:
    """Load and return a JSON object from a file."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def get_workload(schema_workload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return the workload query list.

    Supports both field names used in project drafts:
    - queries
    - workload
    """
    queries = schema_workload.get("queries")

    if queries is None:
        queries = schema_workload.get("workload")

    if not isinstance(queries, list):
        raise ValueError(
            "Schema/workload JSON must contain a 'queries' or 'workload' list."
        )

    return queries


def write_results(output_csv_path: str, rows: list[dict[str, Any]]) -> None:
    """Write measurement results to CSV."""
    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_tool_call_log(
    recommendation: dict[str, Any],
    output_csv_path: str,
) -> None:
    """
    Write Condition B's tool-call log beside the results CSV.

    Condition A does not include a tool_call_log, so nothing is written.
    """
    tool_call_log = recommendation.get("tool_call_log")

    if tool_call_log is None:
        return

    output_directory = Path(output_csv_path).parent
    tool_log_path = output_directory / "tool_call_log.json"

    with tool_log_path.open("w", encoding="utf-8") as file:
        json.dump(tool_call_log, file, indent=2)

    print(f"Wrote tool-call log to {tool_log_path}")


def measure(
    schema_workload_path: str,
    recommendation_path: str,
    baseline_csv_path: str,
    output_csv_path: str,
    password: str | None = None,
) -> None:
    """Run the complete measurement and aggregation pipeline."""
    schema_workload = load_json(schema_workload_path)
    recommendation = load_json(recommendation_path)
    baseline_times = load_baseline(baseline_csv_path)
    workload = get_workload(schema_workload)

    recommended_indexes = recommendation.get("recommended_indexes", [])
    reasoning_text = recommendation.get("llm_reasoning_text", "")

    if not isinstance(recommended_indexes, list):
        raise ValueError("'recommended_indexes' must be a list.")

    database_name = schema_workload.get("schema_name")

    if not database_name:
        raise ValueError("Schema/workload JSON is missing 'schema_name'.")

    connection = psycopg2.connect(
        dbname=database_name,
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
)
    connection.autocommit = True

    cursor = connection.cursor()
    created_indexes: list[str] = []

    try:
        created_indexes = apply_indexes(cursor, recommended_indexes)

        rows: list[dict[str, Any]] = []

        for query in workload:
            query_id = query["query_id"]
            query_text = query["query_text"]

            print(f"Measuring {query_id}...")

            # Warm-up run.
            cursor.execute(
                f"EXPLAIN (ANALYZE, FORMAT JSON) {query_text}"
            )
            cursor.fetchone()

            execution_time_after, _ = measure_query(cursor, query_text)
            baseline_time = baseline_times.get(query_id)

            improvement = None
            if baseline_time is not None:
                improvement = calculate_improvement(
                    baseline_time,
                    execution_time_after,
                )

            rows.append(
                {
                    "query_id": query_id,
                    "recommended_indexes": json.dumps(
                        recommended_indexes
                    ),
                    "llm_reasoning_text": reasoning_text,
                    "execution_time_ms_after": execution_time_after,
                    "improvement_vs_baseline": improvement,
                }
            )

        write_results(output_csv_path, rows)
        write_tool_call_log(recommendation, output_csv_path)

        print(f"Wrote {len(rows)} rows to {output_csv_path}")

        print("\nBaseline -> After:")
        for row in rows:
            baseline_time = baseline_times.get(row["query_id"])
            after_time = row["execution_time_ms_after"]
            improvement = row["improvement_vs_baseline"]

            print(
                f"  {row['query_id']}: "
                f"{baseline_time} ms -> {after_time:.3f} ms "
                f"({improvement}% improvement)"
            )

    finally:
        if created_indexes:
            drop_indexes(cursor, created_indexes)

        cursor.close()
        connection.close()


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Apply recommended indexes and measure workload performance."
    )

    parser.add_argument(
        "schema_workload",
        help="Path to schema/workload JSON.",
    )
    parser.add_argument(
        "recommendation",
        help="Path to Condition A or Condition B recommendation JSON.",
    )
    parser.add_argument(
        "baseline",
        help="Path to baseline_results.csv.",
    )
    parser.add_argument(
        "output",
        help="Path for condition_a_results.csv or condition_b_results.csv.",
    )

    return parser.parse_args()


def main() -> None:
    """Command-line entry point."""
    args = parse_arguments()

    measure(
        schema_workload_path=args.schema_workload,
        recommendation_path=args.recommendation,
        baseline_csv_path=args.baseline,
        output_csv_path=args.output,
    )


if __name__ == "__main__":
    main()