import csv
from pathlib import Path

from pipeline.measurement.utils import (
    build_index_name,
    calculate_improvement,
    load_baseline,
)


def test_calculate_improvement():
    result = calculate_improvement(100.0, 60.0)
    assert result == 40.0


def test_calculate_improvement_when_slower():
    result = calculate_improvement(100.0, 120.0)
    assert result == -20.0


def test_build_index_name_is_deterministic():
    table = "customer"
    columns = ["c_last"]

    first = build_index_name(table, columns)
    second = build_index_name(table, columns)

    assert first == second
    assert first == "idx_customer_c_last"

def test_load_baseline(tmp_path: Path):
    csv_path = tmp_path / "baseline.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "query_id",
                "execution_time_ms",
                "query_plan_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "Q1",
                "execution_time_ms": "25.5",
                "query_plan_text": "Seq Scan",
            }
        )

    baseline = load_baseline(csv_path)

    assert "Q1" in baseline
    assert baseline["Q1"] == 25.5