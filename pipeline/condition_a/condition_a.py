import time
import json
import re
import anthropic

client = anthropic.Anthropic()


def extract_schema_columns(schema_ddl: str) -> dict[str, set[str]]:
    """
    Parses CREATE TABLE statements out of the schema DDL and returns
    a mapping of table_name -> set of column_names, so recommended
    indexes can be checked against what actually exists.
    """
    tables = {}
    for match in re.finditer(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)\s*;',
        schema_ddl,
        re.S | re.I,
    ):
        table, cols_block = match.groups()
        cols = {c.strip().split()[0].lower() for c in cols_block.split(",") if c.strip()}
        tables[table.lower()] = cols
    return tables


def validate_index_stmt(stmt: str, schema_cols: dict[str, set[str]]) -> bool:
    """
    Returns True only if the CREATE INDEX statement references a real
    table and real columns from the schema. Handles optional Postgres
    operator classes (e.g. "note text_pattern_ops") by validating just
    the column name portion of each column entry.
    """
    m = re.match(
        r'CREATE\s+INDEX\s+\w+\s+ON\s+(\w+)\s*\((.*?)\)',
        stmt.strip(),
        re.I,
    )
    if not m:
        return False
    table, cols = m.groups()
    table_key = table.lower()
    if table_key not in schema_cols:
        return False

    for entry in cols.split(","):
        entry = entry.strip()
        # First whitespace-separated token is the column name;
        # anything after it (e.g. "text_pattern_ops") is an operator class.
        col_name = (entry.split()[0] if entry.split() else entry).lower()
        if col_name not in schema_cols[table_key]:
            return False

    return True


def filter_hallucinated_indexes(indexes: list[str], schema_cols: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """
    Splits a list of CREATE INDEX statements into (valid, rejected).
    Rejected statements are logged by the caller, not silently dropped.
    """
    valid, rejected = [], []
    for stmt in indexes:
        if validate_index_stmt(stmt, schema_cols):
            valid.append(stmt)
        else:
            rejected.append(stmt)
    return valid, rejected


def call_llm_no_tool(prompt: str, schema_ddl: str, model: str = "claude-sonnet-4-6", max_retries: int = 3) -> dict:
    """
    Calls the LLM with no tool access (Condition A), parses its JSON
    recommendation, and validates every recommended index against the
    real schema before returning. Retries on transient API errors or
    malformed JSON responses.
    """
    last_err = None
    schema_cols = extract_schema_columns(schema_ddl)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
                # Deliberately: no `tools` parameter passed at all.
                # This is what makes this Condition A, not Condition B.
            )

            raw_text = response.content[0].text.strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            result = json.loads(raw_text)

            if "recommended_indexes" not in result or "per_query_reasoning" not in result:
                raise ValueError(
                    f"LLM response missing required keys. Got: {list(result.keys())}"
                )

            # Validate top-level recommendations
            valid, rejected = filter_hallucinated_indexes(
                result["recommended_indexes"], schema_cols
            )
            if rejected:
                print(f"[validation] Rejected {len(rejected)} hallucinated index(es): {rejected}")
            result["recommended_indexes"] = valid
            result["rejected_indexes"] = rejected

            # Validate per-query recommendations too
            for entry in result["per_query_reasoning"]:
                q_valid, q_rejected = filter_hallucinated_indexes(
                    entry.get("recommended_indexes", []), schema_cols
                )
                if q_rejected:
                    print(f"[validation] Query {entry.get('query_id')}: "
                          f"rejected {q_rejected}")
                entry["recommended_indexes"] = q_valid
                entry["rejected_indexes"] = q_rejected

            return result

        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            print(f"[attempt {attempt + 1}/{max_retries}] Bad LLM response: {e}")
        except anthropic.APIError as e:
            last_err = e
            print(f"[attempt {attempt + 1}/{max_retries}] API error: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    raise ValueError(
        f"LLM call failed after {max_retries} attempts"
    ) from last_err