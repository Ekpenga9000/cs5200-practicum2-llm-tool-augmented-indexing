"""Reusable helpers for the measurement and aggregation module."""

import csv
import json
import statistics
from typing import Any

RUNS_PER_QUERY = 7


def load_baseline(baseline_csv_path: str) -> dict[str, float]:
    """Load baseline execution times, keyed by query_id."""
    baseline: dict[str, float] = {}

    with open(baseline_csv_path, encoding="utf-8") as file:
        for row in csv.DictReader(file):
            baseline[row["query_id"]] = float(row["execution_time_ms"])

    return baseline


def measure_query(cursor: Any, query_text: str) -> tuple[float, str]:
    """
    Run EXPLAIN ANALYZE multiple times.

    Returns:
        median execution time in milliseconds
        JSON query plan as text
    """
    times: list[float] = []
    latest_plan = None

    for _ in range(RUNS_PER_QUERY):
        cursor.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {query_text}")
        latest_plan = cursor.fetchone()[0]
        times.append(float(latest_plan[0]["Execution Time"]))

    if latest_plan is None:
        raise RuntimeError("PostgreSQL returned no query plan.")

    median_time = statistics.median(times)
    plan_text = json.dumps(latest_plan, indent=2)

    return median_time, plan_text


def calculate_improvement(
    baseline_time_ms: float,
    execution_time_ms_after: float,
) -> float | None:
    """
    Calculate percentage improvement relative to baseline.

    Positive means faster.
    Negative means slower.
    """
    if baseline_time_ms <= 0:
        return None

    improvement = (
        (baseline_time_ms - execution_time_ms_after)
        / baseline_time_ms
        * 100
    )

    return round(improvement, 2)


def build_index_name(table: str, columns: list[str]) -> str:
    """Create a deterministic name for a recommended index."""
    column_part = "_".join(columns)
    return f"idx_{table}_{column_part}"


def apply_indexes(
    cursor: Any,
    recommended_indexes: list[dict[str, Any]],
) -> list[str]:
    """
    Create all recommended indexes and refresh PostgreSQL statistics.

    Returns the names of the indexes that were created.
    """
    created_indexes: list[str] = []
    tables_touched: set[str] = set()

    for index in recommended_indexes:
        table = index["table"]
        columns = index["columns"]

        if not isinstance(columns, list) or not columns:
            raise ValueError(
                f"Index recommendation for table {table!r} has no columns."
            )

        index_name = build_index_name(table, columns)
        columns_sql = ", ".join(columns)

        print(
            f"Creating index {index_name} "
            f"ON {table} ({columns_sql})..."
        )

        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        cursor.execute(
            f"CREATE INDEX {index_name} "
            f"ON {table} ({columns_sql});"
        )

        created_indexes.append(index_name)
        tables_touched.add(table)

    for table in tables_touched:
        print(f"Running ANALYZE {table}...")
        cursor.execute(f"ANALYZE {table};")

    return created_indexes


def drop_indexes(cursor: Any, index_names: list[str]) -> None:
    """Drop indexes created by the measurement module."""
    for index_name in index_names:
        print(f"Dropping index {index_name}...")
        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")