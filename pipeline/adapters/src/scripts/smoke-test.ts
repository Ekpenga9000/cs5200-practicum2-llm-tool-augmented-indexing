import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { promises as fs } from "node:fs";

import { normalizeRecommendationOutput } from "../recommendation";
import { readSchemaWorkloadInput, writeSchemaWorkloadOutput } from "../schema";

async function main(): Promise<void> {
  const workspaceRoot = path.resolve(__dirname, "../../../..");
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "pipeline-adapters-"));

  const toyLibrary = path.join(workspaceRoot, "pipeline", "baseline", "test-data", "toy-library.json");
  const dsbConditionA = path.join(workspaceRoot, "results", "Ikenna", "dsb", "condition_a_recommendation.csv");
  const tpccConditionB = path.join(workspaceRoot, "results", "Alan", "tpcc", "condition_b_recommendation.json");

  const schemaResult = await readSchemaWorkloadInput(toyLibrary);
  assert.equal(schemaResult.canonical.schema_name, "toy_library");

  const schemaOutDir = path.join(tempRoot, "schema-out");
  await writeSchemaWorkloadOutput(schemaResult.canonical, "condition_a", schemaOutDir);
  await fs.access(path.join(schemaOutDir, "schema.sql"));
  await fs.access(path.join(schemaOutDir, "workload.csv"));

  const conditionA = await normalizeRecommendationOutput(dsbConditionA, "condition_a", path.join(tempRoot, "condition-a-out"));
  assert.equal(conditionA.sourceModule, "condition_a");
  assert.ok(conditionA.recommendation.recommended_indexes.length > 0);

  const conditionB = await normalizeRecommendationOutput(tpccConditionB, "condition_b", path.join(tempRoot, "condition-b-out"));
  assert.equal(conditionB.sourceModule, "condition_b");
  assert.ok(conditionB.recommendation.recommended_indexes.length > 0);

  console.log("Adapter smoke test passed.");
  console.log(`Temporary output written to ${tempRoot}`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Adapter smoke test failed: ${message}`);
  process.exit(1);
});