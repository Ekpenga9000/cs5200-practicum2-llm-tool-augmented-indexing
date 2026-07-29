# Baseline Module

This folder contains the standalone Baseline module for the practicum pipeline. It connects to PostgreSQL, loads a schema/workload JSON file, creates the schema fresh, runs `EXPLAIN ANALYZE` for each workload query, and writes one CSV row per query.

## Input Format

The module expects a JSON file with this shape:

```json
{
  "schema_name": "string",
  "schema_ddl": "string containing one or more CREATE TABLE statements",
  "workload": [
    {
      "query_id": "string",
      "query_text": "string",
      "complexity_tier": "Simple | Medium | Complex"
    }
  ]
}
```

## Output Format

The module writes a CSV file named `baseline_results.csv` with exactly these columns:

`query_id`, `execution_time_ms`, `query_plan_text`

Each row corresponds to one query in the workload.

## Environment Variables

Create a `.env` file in this folder with your PostgreSQL connection settings:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_DATABASE=postgres
```

The code also accepts the standard `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE` variables if you already use those.

## Install

From this directory:

```bash
npm install
```

## Run Standalone

```bash
npm run baseline -- --input ./test-data/toy-library.json --output ./results/baseline_results.csv
```

## Sample Smoke Test

To run both bundled toy schemas and generate CSVs for each one:

```bash
npm run run:samples
```

This writes outputs into `./sample-output/` and confirms the module works against two different schemas without code changes.

If you want a quick comparison, verify that both CSVs have the same header and that each contains one row per workload query.

## Project Layout

- `src/` contains the TypeScript implementation
- `test-data/` contains the sample schema/workload inputs
- `sample-output/` is created by the smoke-test script
- `results/` is a convenient place to store actual run outputs