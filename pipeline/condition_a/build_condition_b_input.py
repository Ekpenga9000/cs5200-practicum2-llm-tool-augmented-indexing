#!/usr/bin/env python3
"""
Converts schema.sql + workload.csv into the SchemaWorkload JSON format
Alan's Condition B module expects: {"schema_name", "ddl", "queries": [...]}.

Note: schema_name is set to match the actual Postgres database name
("postgres" in this setup) since run.py/apply_and_measure.py connect via
dbname=schema_workload["schema_name"].
"""

import csv
import json
import sys


def main():
    if len(sys.argv) != 4:
        print("Usage: python build_condition_b_input.py <schema.sql> <workload.csv> <output.json>")
        sys.exit(1)

    schema_path, workload_path, output_path = sys.argv[1:4]

    with open(schema_path) as f:
        ddl = f.read()

    with open(workload_path) as f:
        queries = list(csv.DictReader(f))

    payload = {
        "schema_name": "postgres",  # matches actual DB name for this setup
        "ddl": ddl,
        "queries": queries,
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(queries)} queries to {output_path}")


if __name__ == "__main__":
    main()
