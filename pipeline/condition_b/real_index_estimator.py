"""
Windows-friendly alternative to hypopg_estimator.py.

HypoPG requires compiling a C extension, which is painful on Windows without
a build toolchain. This version gets the same job done by creating a REAL
index, running EXPLAIN against it, then dropping it immediately. Slower per
call than HypoPG (real DDL cost), but on TPC-C's small scale factor this is
seconds, not minutes -- and it works with zero extra setup.

Same interface as HypoPGCostEstimator, so it's a drop-in replacement in
run.py: just swap the import.
"""

import json
import hashlib


class RealIndexCostEstimator:
    def __init__(self, conn):
        self.conn = conn
        self.conn.autocommit = True

    def estimate_cost(self, candidate_index: dict, query_text: str) -> dict:
        """
        candidate_index: {"table": str, "columns": [str, ...]}
        Returns: {"estimated_cost": float, "plan_text": str}
        """
        table = candidate_index["table"]
        cols = candidate_index["columns"]
        cols_sql = ", ".join(cols)

        # short deterministic name so repeated calls don't collide / pile up
        name_hash = hashlib.md5(f"{table}_{cols_sql}".encode()).hexdigest()[:8]
        index_name = f"tmp_idx_{table}_{name_hash}"

        cur = self.conn.cursor()

        try:
            cur.execute(f"DROP INDEX IF EXISTS {index_name};")
            cur.execute(f"CREATE INDEX {index_name} ON {table} ({cols_sql});")
            cur.execute(f"ANALYZE {table};")

            cur.execute(f"EXPLAIN (FORMAT JSON) {query_text}")
            plan_json = cur.fetchone()[0]
            estimated_cost = plan_json[0]["Plan"]["Total Cost"]
            plan_text = json.dumps(plan_json, indent=2)
        finally:
            cur.execute(f"DROP INDEX IF EXISTS {index_name};")

        return {"estimated_cost": estimated_cost, "plan_text": plan_text}
