"""
Production entry point. Run this once the shared repo/interfaces are merged
(Phase 1 Days 5-7), and again standalone in Phase 2 against TPC-C / TATP.

Usage:
    pip install anthropic psycopg2-binary
    export ANTHROPIC_API_KEY=...
    python run.py path/to/schema_workload.json path/to/recommendation_out.json

No DB extension needed -- uses real temporary indexes (see real_index_estimator.py).
"""

import sys
import json
import getpass

import psycopg2
import anthropic

from condition_b import run_condition_b
# Using the real-index estimator by default (Windows-friendly, no HypoPG
# compile needed). Swap to `from hypopg_estimator import HypoPGCostEstimator`
# later if you set up HypoPG (e.g. via Docker/WSL) for faster iteration.
from real_index_estimator import RealIndexCostEstimator


def main():
    if len(sys.argv) != 3:
        print("Usage: python run.py <schema_workload.json> <recommendation_out.json>")
        sys.exit(1)

    schema_workload_path, out_path = sys.argv[1], sys.argv[2]

    with open(schema_workload_path) as f:
        schema_workload = json.load(f)

    pw = getpass.getpass("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname=schema_workload["schema_name"], user="postgres",
                             password=pw, host="localhost", port=5432)
    estimator = RealIndexCostEstimator(conn)
    client = anthropic.Anthropic()

    recommendation = run_condition_b(schema_workload, estimator, client)

    with open(out_path, "w") as f:
        json.dump(recommendation, f, indent=2)

    print(f"Wrote recommendation to {out_path}")
    print(f"{len(recommendation['recommended_indexes'])} indexes recommended, "
          f"{len(recommendation['tool_call_log'])} tool calls logged.")


if __name__ == "__main__":
    main()
