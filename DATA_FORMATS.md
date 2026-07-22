# Data Format Agreement (Draft — Confirm as a Team on Day 1)

This document explains, in plain English, the exact shape of data that passes between our four pipeline components. Everyone builds against this agreement so the pieces fit together without rework.

There are three things we need to agree on:

1. The **Schema/Workload Object** — what goes IN to every component
2. The **Recommendation Object** — what the LLM modules (Condition A and B) produce
3. The **Baseline Output Format** — what the Baseline module produces

---

## 1. Schema/Workload Object

**What it is, in one sentence:** a package containing the database's table definitions, plus the list of queries we're going to test.

**Why we need it:** all four components need to read the same schema and the same queries. If everyone reads them differently, the pipeline breaks when we merge.

**It has two parts:**

### Part A — The Schema
The raw `CREATE TABLE` statements that build the database. Nothing fancy — just the DDL.

### Part B — The Workload
The list of queries we'll run, where each query has:
- **query_id** — a short label, like `Q1`, `Q2`
- **query_text** — the actual SQL query
- **complexity_tier** — one of `Simple`, `Medium`, or `Complex` (based on how many tables it joins and whether it has aggregation/subqueries)

### Example

```json
{
  "schema_name": "toy_library",
  "schema_ddl": "CREATE TABLE books (id INT PRIMARY KEY, title TEXT, author_id INT); CREATE TABLE authors (id INT PRIMARY KEY, name TEXT);",
  "workload": [
    {
      "query_id": "Q1",
      "query_text": "SELECT * FROM books WHERE author_id = 5;",
      "complexity_tier": "Simple"
    },
    {
      "query_id": "Q2",
      "query_text": "SELECT authors.name, COUNT(*) FROM books JOIN authors ON books.author_id = authors.id GROUP BY authors.name;",
      "complexity_tier": "Medium"
    }
  ]
}
```

**Decisions we need to make as a team:**
- [ ] Do we store this as one JSON file, or as two separate files (`schema.sql` + `workload.csv`)?
- [ ] Is `query_text` always plain SQL, or do we need placeholders?
- [ ] Do complexity tiers get labeled here upfront, or added later?
- [ ] For schemas with many tables (like TPC-H's 8 tables), is `schema_ddl` one long string, or a list of per-table strings?

---

## 2. Recommendation Object

**What it is, in one sentence:** what the LLM gives back after looking at the schema and queries — which indexes it thinks we should create, and why.

**Who produces it:** Sylfhen's Condition A module and Alan's Condition B module both produce this — same shape, same fields, for either condition.

**It needs to include:**
- **query_id** or overall recommendation scope — which query/queries this recommendation relates to
- **recommended_indexes** — a list of the indexes the LLM suggests (e.g., `["CREATE INDEX idx_books_author ON books(author_id);"]`)
- **llm_reasoning_text** — the LLM's explanation for why it picked these indexes
- **(Condition B only) tool_call_log** — every candidate index it tried, the cost estimate it got back, and whether it kept or dropped that candidate

### Example (Condition A)

```json
{
  "recommended_indexes": ["CREATE INDEX idx_books_author ON books(author_id);"],
  "llm_reasoning_text": "This index speeds up the WHERE clause filtering on author_id in Q1."
}
```

### Example (Condition B, with tool log)

```json
{
  "recommended_indexes": ["CREATE INDEX idx_books_author ON books(author_id);"],
  "llm_reasoning_text": "Tested two candidate indexes; this one had the lowest estimated cost.",
  "tool_call_log": [
    {"candidate": "CREATE INDEX idx_books_title ON books(title);", "estimated_cost": 450, "accepted": false},
    {"candidate": "CREATE INDEX idx_books_author ON books(author_id);", "estimated_cost": 120, "accepted": true}
  ]
}
```

**Decisions we need to make as a team:**
- [ ] Is this one recommendation per query, or one recommendation covering the whole workload?
- [ ] What exact field name do we use for the index list — `recommended_indexes` or something else?
- [ ] How is `tool_call_log` stored — inside the same file, or as a separate linked file?

---

## 3. Baseline Output Format

**What it is, in one sentence:** what my (Louis's) Baseline module produces after running every query with `EXPLAIN ANALYZE` and no extra indexes.

**Who consumes it:** Ikenna's measurement module reads this to compare against the results after indexes are added.

**It has one row per query, with these columns:**
- **query_id** — matches the query_id from the workload
- **execution_time_ms** — how long the query actually took to run
- **query_plan_text** — the query plan `EXPLAIN ANALYZE` returned

### Example (as a table)

| query_id | execution_time_ms | query_plan_text |
|---|---|---|
| Q1 | 42 | Seq Scan on books (cost=0.00..15.00 rows=1) |
| Q2 | 310 | Hash Join (cost=1.15..22.35 rows=10) |

**Decisions we need to make as a team:**
- [ ] Do we store `query_plan_text` as raw text, or a cleaned-up/summarized version?
- [ ] CSV or JSON for this file?
- [ ] Does this match exactly what Condition A/B results files need (same column names), so Ikenna doesn't have to translate between formats?

---

## Why This Matters

If everyone builds to a different shape, we won't be able to merge our four components on Days 5–7, and later we won't be able to combine all eight schema results into one table in Week 4. Locking these three formats down now, on Day 1, saves us from painful rework later.

**Action for Day 1 meeting:** go through each checklist above as a group, tick every box, and update this file with the final decision. Once agreed, this becomes the source of truth — everyone builds against it.
