# Integration Test Harness

This folder contains a shared end-to-end harness for the four pipeline components:

- Baseline module
- Condition A module
- Condition B module
- Measurement / aggregation module

The harness is intentionally configurable so you can plug in the teammates' real CLI commands or replace the command runner with direct imports later.

## What it does

The default flow is:

1. Run the Baseline module against one shared schema/workload JSON file.
2. Run Condition A to produce its recommendation artifact.
3. Validate the Condition A artifact.
4. Run the Measurement module to turn the Condition A recommendation into `condition_a_results.csv`.
5. Repeat steps 2–4 for Condition B, including `tool_call_log.json` when present.
6. Write a final summary report to `results/integration_report.md`.

The harness also checks that each artifact matches the expected format at that stage and records clear mismatch messages when something is off.

## Install

From this directory:

```bash
npm install
```

## Run

The default input is the bundled schema/workload file at `test-schema/order_customer_product.json`.

```bash
npm run integration-test -- --input ./test-schema/order_customer_product.json
```

You can override the module commands with flags or environment variables. The most important ones are:

- `INTEGRATION_TEST_CONDITION_A_COMMAND`
- `INTEGRATION_TEST_CONDITION_B_COMMAND`
- `INTEGRATION_TEST_MEASUREMENT_COMMAND`

The command strings support placeholders like `{input}`, `{output}`, `{schema}`, `{recommendation}`, and `{baseline}`.

Examples:

```bash
export INTEGRATION_TEST_CONDITION_A_COMMAND='python3 /path/to/condition_a.py {input} {output}'
export INTEGRATION_TEST_CONDITION_B_COMMAND='python3 /path/to/condition_b.py {input} {output}'
export INTEGRATION_TEST_MEASUREMENT_COMMAND='python3 measurement.py {schema} {recommendation} {baseline} {output}'
npm run integration-test -- --input ./test-schema/order_customer_product.json
```

If a teammate's module already emits the final CSV directly, switch that stage's artifact kind in `src/config.ts` to `results-csv` and the harness will validate the CSV shape instead of expecting a recommendation JSON.

## Outputs

The harness writes all artifacts to `results/` inside this folder:

- `baseline_results.csv`
- `condition_a_recommendation.json`
- `condition_a_results.csv`
- `condition_b_recommendation.json`
- `condition_b_results.csv`
- `tool_call_log.json` for Condition B when the recommendation includes it
- `integration_report.md`

Open `results/integration_report.md` first if you want the pass/fail summary and any format mismatches.

## How to read the report

The report lists each stage with:

- pass / fail / skipped status
- elapsed time
- output file path
- any format mismatches or missing fields

If a validation fails, the error text is written in the report and in the console log with the exact expected vs. received detail.

## TODOs for teammates

- Replace the placeholder condition module command strings with the real invocation once those modules are finalized.
- If a teammate exposes an exported function instead of a CLI, swap the command runner in `src/orchestrator.ts` for a direct import.
- If the condition modules are merged into a different folder name than `condition-a` / `condition-b`, update the candidate paths in `src/config.ts`.
