def build_prompt(schema_ddl: str, workload_rows: list[dict]) -> str:
    queries_block = "\n".join(
        f"- query_id: {row['query_id']} (complexity: {row['complexity_tier']})\n"
        f"  SQL: {row['query_text']}"
        for row in workload_rows
    )

    prompt = f"""You are a database performance tuning expert.

Below is a database schema (DDL) and a workload of SQL queries that will run
against it. Recommend a set of indexes that would improve overall query
performance across this workload. You do NOT have access to any tools,
EXPLAIN output, or execution statistics — base your recommendations purely on
reading the schema and query text.

SCHEMA:
{schema_ddl}

WORKLOAD:
{queries_block}

Respond with ONLY valid JSON, no other text, no markdown fences, in this exact
format:

{{
  "recommended_indexes": ["CREATE INDEX ... ON ...(...);", "..."],
  "per_query_reasoning": [
    {{
      "query_id": "q1",
      "recommended_indexes": ["CREATE INDEX ... ON ...(...);"],
      "reasoning": "one concise sentence (under 20 words) explaining why these indexes help this query"
    }}
  ]
}}
"""
    return prompt