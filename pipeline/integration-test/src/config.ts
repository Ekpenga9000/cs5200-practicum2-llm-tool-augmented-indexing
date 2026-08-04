import fs from "node:fs";
import path from "node:path";

import type { ConditionArtifactKind, HarnessConfig } from "./types";

export const integrationTestRoot = path.resolve(__dirname, "..");
export const pipelineRoot = path.resolve(integrationTestRoot, "..");
export const workspaceRoot = path.resolve(pipelineRoot, "..");

export const defaultInputPath = path.resolve(
  integrationTestRoot,
  "test-schema",
  "order_customer_product.json",
);

export const defaultOutputDir = path.resolve(integrationTestRoot, "results");

export const baselineModuleDir = path.resolve(pipelineRoot, "baseline");
export const measurementModuleDir = path.resolve(pipelineRoot, "measurement");

export function resolveExistingDirectory(
  candidates: string[],
  fallback: string,
): string {
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isDirectory()) {
      return candidate;
    }
  }

  return fallback;
}

export const conditionAModuleDir = resolveExistingDirectory(
  [
    path.resolve(pipelineRoot, "condition-a"),
    path.resolve(pipelineRoot, "condition_a"),
  ],
  workspaceRoot,
);

export const conditionBModuleDir = resolveExistingDirectory(
  [
    path.resolve(pipelineRoot, "condition-b"),
    path.resolve(pipelineRoot, "condition_b"),
  ],
  workspaceRoot,
);

function readConditionArtifactKind(envName: string): ConditionArtifactKind {
  const value = process.env[envName];

  if (value === "results-csv") {
    return "results-csv";
  }

  return "recommendation-json";
}

export function loadHarnessConfig(
  overrides: Partial<HarnessConfig> = {},
): HarnessConfig {
  return {
    inputPath:
      overrides.inputPath ??
      process.env.INTEGRATION_TEST_INPUT ??
      defaultInputPath,
    outputDir:
      overrides.outputDir ??
      process.env.INTEGRATION_TEST_OUTPUT_DIR ??
      defaultOutputDir,
    pythonCommand:
      overrides.pythonCommand ??
      process.env.INTEGRATION_TEST_PYTHON_COMMAND ??
      "python3",
    // TODO: replace the default baseline command with the team's final CLI or direct function wrapper.
    baselineCommandTemplate:
      overrides.baselineCommandTemplate ??
      process.env.INTEGRATION_TEST_BASELINE_COMMAND ??
      "npm run baseline -- --input {input} --output {output}",
    baselineCwd:
      overrides.baselineCwd ??
      process.env.INTEGRATION_TEST_BASELINE_CWD ??
      baselineModuleDir,
    // TODO: wire this to the actual Condition A invocation once the teammate's module interface is final.
    conditionACommandTemplate:
      overrides.conditionACommandTemplate ??
      process.env.INTEGRATION_TEST_CONDITION_A_COMMAND ??
      "",
    conditionACwd:
      overrides.conditionACwd ??
      process.env.INTEGRATION_TEST_CONDITION_A_CWD ??
      conditionAModuleDir,
    conditionAArtifactKind:
      overrides.conditionAArtifactKind ??
      readConditionArtifactKind("INTEGRATION_TEST_CONDITION_A_ARTIFACT_KIND"),
    conditionBCommandTemplate:
      overrides.conditionBCommandTemplate ??
      process.env.INTEGRATION_TEST_CONDITION_B_COMMAND ??
      "",
    conditionBCwd:
      overrides.conditionBCwd ??
      process.env.INTEGRATION_TEST_CONDITION_B_CWD ??
      conditionBModuleDir,
    conditionBArtifactKind:
      overrides.conditionBArtifactKind ??
      readConditionArtifactKind("INTEGRATION_TEST_CONDITION_B_ARTIFACT_KIND"),
    measurementCommandTemplate:
      // TODO: replace the default Python adapter once the shared measurement module exports a stable CLI or function.
      overrides.measurementCommandTemplate ??
      process.env.INTEGRATION_TEST_MEASUREMENT_COMMAND ??
      "{python} measurement.py {schema} {recommendation} {baseline} {output}",
    measurementCwd:
      overrides.measurementCwd ??
      process.env.INTEGRATION_TEST_MEASUREMENT_CWD ??
      measurementModuleDir,
  };
}
