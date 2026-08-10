"""
Real cost estimator for production use, backed by Postgres's HypoPG extension.

Setup once per target database:
    CREATE EXTENSION IF NOT EXISTS hypopg;

HypoPG lets EXPLAIN reason about an index that doesn't physically exist yet,
so candidate indexes can be tried and discarded instantly with zero DDL cost
-- important since Condition B may try many candidates per query.
"""

import json


def quote_identifier(identifier: str) -> str:
    return '"{}"'.format(identifier.replace('"', '""'))


class HypoPGCostEstimator:
    def __init__(self, conn, schema_name: str):
        self.conn = conn
        self.conn.autocommit = True
        self.schema_name = schema_name
        with self.conn.cursor() as cur:
            cur.execute(f"SET search_path TO {quote_identifier(self.schema_name)}, public")

    def estimate_cost(self, candidate_index: dict, query_text: str) -> dict:
        """
        candidate_index: {"table": str, "columns": [str, ...]}
        Returns: {"estimated_cost": float, "plan_text": str}
        """
        table = candidate_index["table"]
        cols = ", ".join(candidate_index["columns"])
        cur = self.conn.cursor()

        cur.execute(
            "SELECT * FROM hypopg_create_index(%s);",
            (f"CREATE INDEX ON {table} ({cols})",),
        )
        hypo_index_id = cur.fetchone()[0]

        try:
            cur.execute(f"EXPLAIN (FORMAT JSON) {query_text}")
            plan_json = cur.fetchone()[0]
            estimated_cost = plan_json[0]["Plan"]["Total Cost"]
            plan_text = json.dumps(plan_json, indent=2)
        finally:
            cur.execute("SELECT hypopg_drop_index(%s);", (hypo_index_id,))

        return {"estimated_cost": estimated_cost, "plan_text": plan_text}
