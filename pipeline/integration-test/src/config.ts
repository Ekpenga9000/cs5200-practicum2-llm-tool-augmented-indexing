import fs from "node:fs";
import path from "node:path";

import type { ConditionArtifactKind, HarnessConfig } from "./types";

export const integrationTestRoot = path.resolve(__dirname, "..");
export const pipelineRoot = path.resolve(integrationTestRoot, "..");
export const workspaceRoot = path.resolve(pipelineRoot, "..");
export const adaptersModuleDir = path.resolve(pipelineRoot, "adapters");
export const adapterCliPath = path.resolve(adaptersModuleDir, "src", "cli.ts");
export const integrationTsNodeBinary = path.resolve(
  integrationTestRoot,
  "node_modules",
  ".bin",
  "ts-node",
);

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

export const conditionARunScriptPath = path.resolve(
  conditionAModuleDir,
  "run_condition_a.py",
);
export const conditionBRunScriptPath = path.resolve(
  conditionBModuleDir,
  "run.py",
);
export const defaultSchemaWorkloadAdapterCommandTemplate =
  `${integrationTsNodeBinary} ${adapterCliPath} --mode schema-workload --input {input} --to {to} --output {output}`;
export const defaultRecommendationAdapterCommandTemplate =
  `${integrationTsNodeBinary} ${adapterCliPath} --mode recommendation --input {input} --source {source} --output {output}`;
export const defaultConditionACommandTemplate =
  `python3 ${conditionARunScriptPath} {schema} {workload} {output}`;
export const defaultConditionBCommandTemplate =
  `python3 ${conditionBRunScriptPath} {input} {output}`;

function readConditionArtifactKind(
  envName: string,
  defaultKind: ConditionArtifactKind,
): ConditionArtifactKind {
  const value = process.env[envName];

  if (value === "results-csv") {
    return "results-csv";
  }

  if (value === "recommendation-json") {
    return "recommendation-json";
  }

  return defaultKind;
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
    baselineCommandTemplate:
      overrides.baselineCommandTemplate ??
      process.env.INTEGRATION_TEST_BASELINE_COMMAND ??
      "npm run baseline -- --input {input} --output {output}",
    baselineCwd:
      overrides.baselineCwd ??
      process.env.INTEGRATION_TEST_BASELINE_CWD ??
      baselineModuleDir,
    conditionACommandTemplate:
      overrides.conditionACommandTemplate ??
      process.env.INTEGRATION_TEST_CONDITION_A_COMMAND ??
      defaultConditionACommandTemplate,
    conditionACwd:
      overrides.conditionACwd ??
      process.env.INTEGRATION_TEST_CONDITION_A_CWD ??
      conditionAModuleDir,
    conditionAArtifactKind:
      overrides.conditionAArtifactKind ??
      readConditionArtifactKind(
        "INTEGRATION_TEST_CONDITION_A_ARTIFACT_KIND",
        "results-csv",
      ),
    conditionBCommandTemplate:
      overrides.conditionBCommandTemplate ??
      process.env.INTEGRATION_TEST_CONDITION_B_COMMAND ??
      defaultConditionBCommandTemplate,
    conditionBCwd:
      overrides.conditionBCwd ??
      process.env.INTEGRATION_TEST_CONDITION_B_CWD ??
      conditionBModuleDir,
    conditionBArtifactKind:
      overrides.conditionBArtifactKind ??
      readConditionArtifactKind(
        "INTEGRATION_TEST_CONDITION_B_ARTIFACT_KIND",
        "recommendation-json",
      ),
    measurementCommandTemplate:
      overrides.measurementCommandTemplate ??
      process.env.INTEGRATION_TEST_MEASUREMENT_COMMAND ??
      "{python} measurement.py {schema} {recommendation} {baseline} {output}",
    measurementCwd:
      overrides.measurementCwd ??
      process.env.INTEGRATION_TEST_MEASUREMENT_CWD ??
      measurementModuleDir,
  };
}
