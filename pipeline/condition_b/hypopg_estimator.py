"""
Real cost estimator for production use, backed by Postgres's HypoPG extension.

Setup once per target database:
    CREATE EXTENSION IF NOT EXISTS hypopg;

HypoPG lets EXPLAIN reason about an index that doesn't physically exist yet,
so candidate indexes can be tried and discarded instantly with zero DDL cost
-- important since Condition B may try many candidates per query.
"""

import json

from psycopg2 import sql


class HypoPGCostEstimator:
    def __init__(self, conn, schema=None):
        self.conn = conn
        self.conn.autocommit = True
        # See RealIndexCostEstimator: resolve tables in a non-public schema.
        if schema:
            with self.conn.cursor() as cur:
                cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))

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
