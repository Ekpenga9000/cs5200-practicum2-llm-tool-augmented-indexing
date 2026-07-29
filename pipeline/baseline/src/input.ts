import { promises as fs } from "node:fs";

import type {
  ComplexityTier,
  SchemaWorkloadInput,
  WorkloadQuery,
} from "./types";

const VALID_COMPLEXITY_TIERS = new Set<ComplexityTier>([
  "Simple",
  "Medium",
  "Complex",
]);

function assertNonEmptyString(
  value: unknown,
  fieldName: string,
): asserts value is string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(
      `Invalid or missing ${fieldName}; expected a non-empty string.`,
    );
  }
}

function validateWorkloadQuery(
  rawQuery: unknown,
  index: number,
): WorkloadQuery {
  if (typeof rawQuery !== "object" || rawQuery === null) {
    throw new Error(
      `Invalid workload entry at index ${index}; expected an object.`,
    );
  }

  const query = rawQuery as Record<string, unknown>;
  assertNonEmptyString(query.query_id, `workload[${index}].query_id`);
  assertNonEmptyString(query.query_text, `workload[${index}].query_text`);
  assertNonEmptyString(
    query.complexity_tier,
    `workload[${index}].complexity_tier`,
  );

  if (!VALID_COMPLEXITY_TIERS.has(query.complexity_tier as ComplexityTier)) {
    throw new Error(
      `Invalid workload[${index}].complexity_tier: ${String(query.complexity_tier)}. Expected one of: Simple, Medium, Complex.`,
    );
  }

  return {
    query_id: query.query_id,
    query_text: query.query_text,
    complexity_tier: query.complexity_tier as ComplexityTier,
  };
}

export async function readSchemaWorkloadInput(
  inputPath: string,
): Promise<SchemaWorkloadInput> {
  const fileContents = await fs.readFile(inputPath, "utf8");

  let parsed: unknown;
  try {
    parsed = JSON.parse(fileContents);
  } catch (error) {
    throw new Error(
      `Unable to parse input JSON at ${inputPath}: ${(error as Error).message}`,
    );
  }

  if (typeof parsed !== "object" || parsed === null) {
    throw new Error("Input JSON must be an object.");
  }

  const rawInput = parsed as Record<string, unknown>;
  assertNonEmptyString(rawInput.schema_name, "schema_name");
  assertNonEmptyString(rawInput.schema_ddl, "schema_ddl");

  if (!Array.isArray(rawInput.workload)) {
    throw new Error(
      "Invalid or missing workload; expected an array of queries.",
    );
  }

  const workload = rawInput.workload.map((entry, index) =>
    validateWorkloadQuery(entry, index),
  );

  return {
    schema_name: rawInput.schema_name,
    schema_ddl: rawInput.schema_ddl,
    workload,
  };
}
