import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

import {
  baselineModuleDir,
  loadHarnessConfig,
  measurementModuleDir,
} from "./config";
import {
  parseCsvContent,
  readTextFile,
  shellQuote,
  toCsvContent,
  writeTextFile,
} from "./csv";
import type {
  HarnessConfig,
  HarnessRunResult,
  MeasuredOutputRow,
  RecommendationArtifact,
  SchemaWorkloadInput,
  StageResult,
} from "./types";

interface CommandExecutionResult {
  command: string;
  cwd: string;
  exitCode: number;
  durationMs: number;
  stdout: string;
  stderr: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

function elapsedMs(startTime: bigint): number {
  return Math.max(
    0,
    Number((process.hrtime.bigint() - startTime) / BigInt(1_000_000)),
  );
}

function renderCommand(
  template: string,
  substitutions: Record<string, string>,
): string {
  let rendered = template;

  for (const [placeholder, value] of Object.entries(substitutions)) {
    rendered = rendered.replaceAll(`{${placeholder}}`, shellQuote(value));
  }

  return rendered;
}

async function ensureDirectory(directoryPath: string): Promise<void> {
  await fs.mkdir(directoryPath, { recursive: true });
}

async function runShellCommand(
  command: string,
  cwd: string,
): Promise<CommandExecutionResult> {
  const start = process.hrtime.bigint();

  return await new Promise<CommandExecutionResult>((resolve) => {
    const child = spawn(command, {
      cwd,
      shell: true,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";

    child.stdout?.on("data", (chunk: Buffer) => {
      const text = chunk.toString();
      stdout += text;
      process.stdout.write(text);
    });

    child.stderr?.on("data", (chunk: Buffer) => {
      const text = chunk.toString();
      stderr += text;
      process.stderr.write(text);
    });

    child.on("close", (exitCode) => {
      resolve({
        command,
        cwd,
        exitCode: exitCode ?? 1,
        durationMs: elapsedMs(start),
        stdout,
        stderr,
      });
    });
  });
}

async function runPluggableStage(args: {
  name: string;
  cwd: string;
  commandTemplate: string;
  substitutions: Record<string, string>;
}): Promise<StageResult> {
  const stageStart = process.hrtime.bigint();

  if (!args.commandTemplate.trim()) {
    const message = `No command configured for ${args.name}. Update src/config.ts or set the matching INTEGRATION_TEST_*_COMMAND environment variable.`;

    return {
      name: args.name,
      status: "failed",
      durationMs: elapsedMs(stageStart),
      command: "",
      cwd: args.cwd,
      stdout: "",
      stderr: "",
      validationErrors: [message],
      errorMessage: message,
    };
  }

  const command = renderCommand(args.commandTemplate, args.substitutions);
  console.log(`\n[${nowIso()}] Starting ${args.name}`);
  console.log(`[${args.name}] cwd: ${args.cwd}`);
  console.log(`[${args.name}] command: ${command}`);

  const execution = await runShellCommand(command, args.cwd);

  const status: StageResult["status"] =
    execution.exitCode === 0 ? "passed" : "failed";

  return {
    name: args.name,
    status,
    durationMs: execution.durationMs,
    command,
    cwd: args.cwd,
    stdout: execution.stdout,
    stderr: execution.stderr,
    validationErrors: [],
    errorMessage:
      execution.exitCode === 0
        ? undefined
        : `Command exited with code ${execution.exitCode}.`,
  };
}

function headerError(
  actual: string[],
  expected: string[],
  filePath: string,
): string {
  return `Expected columns ${expected.join(", ")} in ${path.basename(filePath)}, but received ${actual.join(", ")}.`;
}

function isNumericText(value: string): boolean {
  return value.trim().length > 0 && Number.isFinite(Number(value));
}

async function loadJson<T>(filePath: string): Promise<T> {
  const content = await readTextFile(filePath);
  return JSON.parse(content) as T;
}

async function validateBaselineOutput(
  filePath: string,
  expectedQueryIds: string[],
): Promise<string[]> {
  const validationErrors: string[] = [];
  const content = await readTextFile(filePath);
  const rows = parseCsvContent(content);

  if (rows.length === 0) {
    return ["baseline_results.csv is empty."];
  }

  const header = rows[0];
  const expectedHeader = ["query_id", "execution_time_ms", "query_plan_text"];

  if (
    header.length !== expectedHeader.length ||
    header.some((column, index) => column !== expectedHeader[index])
  ) {
    validationErrors.push(headerError(header, expectedHeader, filePath));
  }

  const seenQueryIds = new Set<string>();
  const receivedQueryIds: string[] = [];

  for (const [rowIndex, row] of rows.slice(1).entries()) {
    if (row.length !== expectedHeader.length) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} expected ${expectedHeader.length} columns but received ${row.length}.`,
      );
      continue;
    }

    const [queryId, executionTime, planText] = row;

    if (!queryId.trim()) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} is missing query_id.`,
      );
    }

    if (seenQueryIds.has(queryId)) {
      validationErrors.push(
        `Duplicate query_id '${queryId}' in ${path.basename(filePath)}.`,
      );
    }

    seenQueryIds.add(queryId);
    receivedQueryIds.push(queryId);

    if (!isNumericText(executionTime)) {
      validationErrors.push(
        `Row ${rowIndex + 2} column execution_time_ms expected numeric text but received '${executionTime}'.`,
      );
    }

    if (typeof planText !== "string") {
      validationErrors.push(
        `Row ${rowIndex + 2} column query_plan_text expected string text but received a different type.`,
      );
    }
  }

  if (receivedQueryIds.length !== expectedQueryIds.length) {
    validationErrors.push(
      `Expected ${expectedQueryIds.length} rows in ${path.basename(filePath)} but received ${receivedQueryIds.length}.`,
    );
  }

  const missingQueryIds = expectedQueryIds.filter(
    (queryId) => !seenQueryIds.has(queryId),
  );
  const unexpectedQueryIds = receivedQueryIds.filter(
    (queryId) => !expectedQueryIds.includes(queryId),
  );

  if (missingQueryIds.length > 0) {
    validationErrors.push(
      `Missing query_id values in ${path.basename(filePath)}: ${missingQueryIds.join(", ")}.`,
    );
  }

  if (unexpectedQueryIds.length > 0) {
    validationErrors.push(
      `Unexpected query_id values in ${path.basename(filePath)}: ${unexpectedQueryIds.join(", ")}.`,
    );
  }

  return validationErrors;
}

function validateRecommendationArtifactObject(
  artifact: RecommendationArtifact,
  requireToolCallLog: boolean,
  filePath: string,
): string[] {
  const validationErrors: string[] = [];

  if (!Array.isArray(artifact.recommended_indexes)) {
    validationErrors.push(
      `Expected recommended_indexes to be an array in ${path.basename(filePath)}.`,
    );
  }

  if (typeof artifact.llm_reasoning_text !== "string") {
    validationErrors.push(
      `Expected llm_reasoning_text to be a string in ${path.basename(filePath)}.`,
    );
  }

  if (requireToolCallLog) {
    if (!Array.isArray(artifact.tool_call_log)) {
      validationErrors.push(
        `Expected tool_call_log to be present as an array in ${path.basename(filePath)}.`,
      );
    }
  } else if (
    artifact.tool_call_log !== undefined &&
    !Array.isArray(artifact.tool_call_log)
  ) {
    validationErrors.push(
      `tool_call_log must be an array when present in ${path.basename(filePath)}.`,
    );
  }

  return validationErrors;
}

async function validateRecommendationJson(
  filePath: string,
  requireToolCallLog: boolean,
): Promise<string[]> {
  const validationErrors: string[] = [];

  try {
    const artifact = await loadJson<RecommendationArtifact>(filePath);
    validationErrors.push(
      ...validateRecommendationArtifactObject(
        artifact,
        requireToolCallLog,
        filePath,
      ),
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    validationErrors.push(
      `Failed to parse ${path.basename(filePath)} as JSON: ${message}`,
    );
  }

  return validationErrors;
}

async function validateResultsCsv(
  filePath: string,
  expectedQueryIds: string[],
  requireToolCallLog: boolean,
): Promise<string[]> {
  const validationErrors: string[] = [];
  const content = await readTextFile(filePath);
  const rows = parseCsvContent(content);

  if (rows.length === 0) {
    return [`${path.basename(filePath)} is empty.`];
  }

  const header = rows[0];
  const expectedHeader = [
    "query_id",
    "recommended_indexes",
    "llm_reasoning_text",
    "execution_time_ms_after",
    "improvement_vs_baseline",
  ];

  const hasToolCallLogColumn = header.includes("tool_call_log");

  if (
    header.length !== expectedHeader.length &&
    !(
      requireToolCallLog &&
      header.length === expectedHeader.length + 1 &&
      hasToolCallLogColumn
    )
  ) {
    validationErrors.push(
      `Expected columns ${expectedHeader.join(", ")}${requireToolCallLog ? ", tool_call_log" : ""} in ${path.basename(filePath)}, but received ${header.join(", ")}.`,
    );
  }

  const requiredColumns = [...expectedHeader];
  if (requireToolCallLog) {
    requiredColumns.push("tool_call_log");
  }

  for (const column of requiredColumns) {
    if (!header.includes(column)) {
      validationErrors.push(
        `Expected column '${column}' in ${path.basename(filePath)}.`,
      );
    }
  }

  const queryIdColumnIndex = header.indexOf("query_id");
  const indexesColumnIndex = header.indexOf("recommended_indexes");
  const reasoningColumnIndex = header.indexOf("llm_reasoning_text");
  const executionColumnIndex = header.indexOf("execution_time_ms_after");
  const improvementColumnIndex = header.indexOf("improvement_vs_baseline");
  const toolLogColumnIndex = header.indexOf("tool_call_log");

  const seenQueryIds = new Set<string>();

  for (const [rowIndex, row] of rows.slice(1).entries()) {
    if (row.length < expectedHeader.length) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} expected at least ${expectedHeader.length} columns but received ${row.length}.`,
      );
      continue;
    }

    const queryId = row[queryIdColumnIndex];
    const recommendedIndexes = row[indexesColumnIndex];
    const reasoning = row[reasoningColumnIndex];
    const executionTime = row[executionColumnIndex];
    const improvement = row[improvementColumnIndex];

    if (!queryId.trim()) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} is missing query_id.`,
      );
    }

    if (seenQueryIds.has(queryId)) {
      validationErrors.push(
        `Duplicate query_id '${queryId}' in ${path.basename(filePath)}.`,
      );
    }

    seenQueryIds.add(queryId);

    if (!recommendedIndexes.trim()) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} is missing recommended_indexes.`,
      );
    }

    if (!reasoning.trim()) {
      validationErrors.push(
        `Row ${rowIndex + 2} in ${path.basename(filePath)} is missing llm_reasoning_text.`,
      );
    }

    if (!isNumericText(executionTime)) {
      validationErrors.push(
        `Row ${rowIndex + 2} column execution_time_ms_after expected numeric text but received '${executionTime}'.`,
      );
    }

    if (improvement.trim().length > 0 && !isNumericText(improvement)) {
      validationErrors.push(
        `Row ${rowIndex + 2} column improvement_vs_baseline expected numeric text or blank but received '${improvement}'.`,
      );
    }

    if (requireToolCallLog && toolLogColumnIndex >= 0) {
      if (!row[toolLogColumnIndex].trim()) {
        validationErrors.push(
          `Row ${rowIndex + 2} in ${path.basename(filePath)} is missing tool_call_log.`,
        );
      }
    }
  }

  const missingQueryIds = expectedQueryIds.filter(
    (queryId) => !seenQueryIds.has(queryId),
  );
  const unexpectedQueryIds = Array.from(seenQueryIds).filter(
    (queryId) => !expectedQueryIds.includes(queryId),
  );

  if (missingQueryIds.length > 0) {
    validationErrors.push(
      `Missing query_id values in ${path.basename(filePath)}: ${missingQueryIds.join(", ")}.`,
    );
  }

  if (unexpectedQueryIds.length > 0) {
    validationErrors.push(
      `Unexpected query_id values in ${path.basename(filePath)}: ${unexpectedQueryIds.join(", ")}.`,
    );
  }

  return validationErrors;
}

async function validateToolCallLogIfPresent(
  filePath: string,
  expectedToExist: boolean,
): Promise<string[]> {
  const validationErrors: string[] = [];

  try {
    const rawContent = await readTextFile(filePath);
    const parsed = JSON.parse(rawContent) as unknown;

    if (!Array.isArray(parsed)) {
      validationErrors.push(
        `Expected tool call log at ${path.basename(filePath)} to be a JSON array.`,
      );
    }
  } catch (error) {
    if (expectedToExist) {
      const message = error instanceof Error ? error.message : String(error);
      validationErrors.push(
        `Expected ${path.basename(filePath)} but could not read it: ${message}`,
      );
    }
  }

  if (!expectedToExist) {
    try {
      await fs.access(filePath);
      validationErrors.push(
        `Unexpected tool call log found at ${path.basename(filePath)}.`,
      );
    } catch {
      // Expected path absent.
    }
  }

  return validationErrors;
}

async function validateConditionArtifact(
  artifactPath: string,
  artifactKind: "recommendation-json" | "results-csv",
  expectedQueryIds: string[],
  requireToolCallLog: boolean,
): Promise<string[]> {
  if (artifactKind === "results-csv") {
    return validateResultsCsv(
      artifactPath,
      expectedQueryIds,
      requireToolCallLog,
    );
  }

  return validateRecommendationJson(artifactPath, requireToolCallLog);
}

async function validateMeasurementOutputs(args: {
  resultsCsvPath: string;
  toolCallLogPath: string;
  expectedQueryIds: string[];
  requireToolCallLog: boolean;
}): Promise<string[]> {
  const validationErrors = await validateResultsCsv(
    args.resultsCsvPath,
    args.expectedQueryIds,
    args.requireToolCallLog,
  );

  if (args.requireToolCallLog) {
    validationErrors.push(
      ...(await validateToolCallLogIfPresent(args.toolCallLogPath, true)),
    );
  } else {
    validationErrors.push(
      ...(await validateToolCallLogIfPresent(args.toolCallLogPath, false)),
    );
  }

  return validationErrors;
}

async function validateAndPersistStage(
  stage: StageResult,
  validationErrors: string[],
): Promise<StageResult> {
  return {
    ...stage,
    validationErrors,
    status:
      stage.status === "passed" && validationErrors.length === 0
        ? "passed"
        : "failed",
    errorMessage:
      stage.status === "passed" && validationErrors.length === 0
        ? stage.errorMessage
        : (stage.errorMessage ?? validationErrors[0] ?? "Validation failed."),
  };
}

async function runMeasurementStage(args: {
  name: string;
  config: HarnessConfig;
  schemaPath: string;
  recommendationPath: string;
  baselinePath: string;
  outputCsvPath: string;
  requireToolCallLog: boolean;
}): Promise<StageResult> {
  const command = renderCommand(args.config.measurementCommandTemplate, {
    python: args.config.pythonCommand,
    schema: args.schemaPath,
    recommendation: args.recommendationPath,
    baseline: args.baselinePath,
    output: args.outputCsvPath,
  });

  const execution = await runPluggableStage({
    name: args.name,
    cwd: args.config.measurementCwd,
    commandTemplate: command,
    substitutions: {},
  });

  if (execution.status !== "passed") {
    return execution;
  }

  const schema = await loadJson<SchemaWorkloadInput>(args.schemaPath);
  const expectedQueryIds = schema.workload.map((query) => query.query_id);
  const toolCallLogPath = path.join(
    path.dirname(args.outputCsvPath),
    "tool_call_log.json",
  );
  const validationErrors = await validateMeasurementOutputs({
    resultsCsvPath: args.outputCsvPath,
    toolCallLogPath,
    expectedQueryIds,
    requireToolCallLog: args.requireToolCallLog,
  });

  return validateAndPersistStage(execution, validationErrors);
}

async function runConditionStage(args: {
  name: string;
  config: HarnessConfig;
  commandTemplate: string;
  cwd: string;
  inputPath: string;
  outputPath: string;
  artifactKind: "recommendation-json" | "results-csv";
  requireToolCallLog: boolean;
}): Promise<StageResult> {
  const execution = await runPluggableStage({
    name: args.name,
    cwd: args.cwd,
    commandTemplate: args.commandTemplate,
    substitutions: {
      input: args.inputPath,
      output: args.outputPath,
    },
  });

  if (execution.status !== "passed") {
    return execution;
  }

  const schema = await loadJson<SchemaWorkloadInput>(args.inputPath);
  const expectedQueryIds = schema.workload.map((query) => query.query_id);
  const validationErrors = await validateConditionArtifact(
    args.outputPath,
    args.artifactKind,
    expectedQueryIds,
    args.requireToolCallLog,
  );

  return validateAndPersistStage(execution, validationErrors);
}

async function runBaselineStage(args: {
  config: HarnessConfig;
  inputPath: string;
  outputPath: string;
}): Promise<StageResult> {
  const execution = await runPluggableStage({
    name: "Baseline",
    cwd: args.config.baselineCwd,
    commandTemplate: args.config.baselineCommandTemplate,
    substitutions: {
      input: args.inputPath,
      output: args.outputPath,
    },
  });

  if (execution.status !== "passed") {
    return execution;
  }

  const schema = await loadJson<SchemaWorkloadInput>(args.inputPath);
  const expectedQueryIds = schema.workload.map((query) => query.query_id);
  const validationErrors = await validateBaselineOutput(
    args.outputPath,
    expectedQueryIds,
  );

  return validateAndPersistStage(execution, validationErrors);
}

export async function runIntegrationHarness(
  configInput: Partial<HarnessConfig> = {},
): Promise<HarnessRunResult> {
  const config = loadHarnessConfig(configInput);

  await ensureDirectory(config.outputDir);

  const schema = await loadJson<SchemaWorkloadInput>(config.inputPath);
  const baselineResultsPath = path.join(
    config.outputDir,
    "baseline_results.csv",
  );
  const conditionARecommendationPath = path.join(
    config.outputDir,
    "condition_a_recommendation.json",
  );
  const conditionAResultsPath = path.join(
    config.outputDir,
    "condition_a_results.csv",
  );
  const conditionBRecommendationPath = path.join(
    config.outputDir,
    "condition_b_recommendation.json",
  );
  const conditionBResultsPath = path.join(
    config.outputDir,
    "condition_b_results.csv",
  );
  const reportPath = path.join(config.outputDir, "integration_report.md");

  const stageResults: StageResult[] = [];

  const baselineStage = await runBaselineStage({
    config,
    inputPath: config.inputPath,
    outputPath: baselineResultsPath,
  });
  stageResults.push(baselineStage);

  const conditionAStage = await runConditionStage({
    name: "Condition A recommendation",
    config,
    commandTemplate: config.conditionACommandTemplate,
    cwd: config.conditionACwd,
    inputPath: config.inputPath,
    outputPath:
      config.conditionAArtifactKind === "results-csv"
        ? conditionAResultsPath
        : conditionARecommendationPath,
    artifactKind: config.conditionAArtifactKind,
    requireToolCallLog: false,
  });
  stageResults.push(conditionAStage);

  if (
    conditionAStage.status === "passed" &&
    config.conditionAArtifactKind === "recommendation-json"
  ) {
    const measurementAStage = await runMeasurementStage({
      name: "Condition A measurement",
      config,
      schemaPath: config.inputPath,
      recommendationPath: conditionARecommendationPath,
      baselinePath: baselineResultsPath,
      outputCsvPath: conditionAResultsPath,
      requireToolCallLog: false,
    });
    stageResults.push(measurementAStage);
  } else if (config.conditionAArtifactKind === "recommendation-json") {
    stageResults.push({
      name: "Condition A measurement",
      status: "skipped",
      durationMs: 0,
      command: "",
      cwd: config.measurementCwd,
      outputPath: conditionAResultsPath,
      stdout: "",
      stderr: "",
      validationErrors: [
        "Skipped because Condition A recommendation stage did not pass.",
      ],
      errorMessage:
        "Skipped because Condition A recommendation stage did not pass.",
    });
  }

  const conditionBStage = await runConditionStage({
    name: "Condition B recommendation",
    config,
    commandTemplate: config.conditionBCommandTemplate,
    cwd: config.conditionBCwd,
    inputPath: config.inputPath,
    outputPath:
      config.conditionBArtifactKind === "results-csv"
        ? conditionBResultsPath
        : conditionBRecommendationPath,
    artifactKind: config.conditionBArtifactKind,
    requireToolCallLog: true,
  });
  stageResults.push(conditionBStage);

  if (
    conditionBStage.status === "passed" &&
    config.conditionBArtifactKind === "recommendation-json"
  ) {
    const measurementBStage = await runMeasurementStage({
      name: "Condition B measurement",
      config,
      schemaPath: config.inputPath,
      recommendationPath: conditionBRecommendationPath,
      baselinePath: baselineResultsPath,
      outputCsvPath: conditionBResultsPath,
      requireToolCallLog: true,
    });
    stageResults.push(measurementBStage);
  } else if (config.conditionBArtifactKind === "recommendation-json") {
    stageResults.push({
      name: "Condition B measurement",
      status: "skipped",
      durationMs: 0,
      command: "",
      cwd: config.measurementCwd,
      outputPath: conditionBResultsPath,
      stdout: "",
      stderr: "",
      validationErrors: [
        "Skipped because Condition B recommendation stage did not pass.",
      ],
      errorMessage:
        "Skipped because Condition B recommendation stage did not pass.",
    });
  }

  await writeReport({
    outputPath: reportPath,
    schema,
    stageResults,
    config,
    artifacts: {
      baselineResultsPath,
      conditionARecommendationPath,
      conditionAResultsPath,
      conditionBRecommendationPath,
      conditionBResultsPath,
    },
  });

  return {
    inputPath: config.inputPath,
    outputDir: config.outputDir,
    schema,
    stageResults,
    reportPath,
  };
}

function markdownTableRow(values: string[]): string {
  return `| ${values.join(" | ")} |`;
}

function escapeMarkdown(value: string): string {
  return value.replace(/\|/g, "\\|").replace(/\n/g, "<br>");
}

async function writeReport(args: {
  outputPath: string;
  schema: SchemaWorkloadInput;
  stageResults: StageResult[];
  config: HarnessConfig;
  artifacts: Record<string, string>;
}): Promise<void> {
  const lines: string[] = [];
  const passedCount = args.stageResults.filter(
    (stage) => stage.status === "passed",
  ).length;
  const failedCount = args.stageResults.filter(
    (stage) => stage.status === "failed",
  ).length;
  const skippedCount = args.stageResults.filter(
    (stage) => stage.status === "skipped",
  ).length;
  const mismatches = args.stageResults.flatMap((stage) =>
    stage.validationErrors.map((error) => `${stage.name}: ${error}`),
  );

  lines.push("# Integration Test Report");
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Input schema: ${args.schema.schema_name}`);
  lines.push(`Workload queries: ${args.schema.workload.length}`);
  lines.push("");
  lines.push("## Stage Summary");
  lines.push("");
  lines.push(
    markdownTableRow(["Stage", "Status", "Duration (ms)", "Output", "Notes"]),
  );
  lines.push(markdownTableRow(["---", "---", "---:", "---", "---"]));

  for (const stage of args.stageResults) {
    lines.push(
      markdownTableRow([
        escapeMarkdown(stage.name),
        stage.status,
        stage.durationMs.toString(),
        escapeMarkdown(stage.outputPath ?? ""),
        escapeMarkdown(
          stage.errorMessage ?? stage.validationErrors.join("; ") ?? "",
        ),
      ]),
    );
  }

  lines.push("");
  lines.push("## Artifact Paths");
  lines.push("");
  for (const [label, filePath] of Object.entries(args.artifacts)) {
    lines.push(`- ${label}: ${filePath}`);
  }
  lines.push("");
  lines.push("## Validation Mismatches");
  lines.push("");

  if (mismatches.length === 0) {
    lines.push("None.");
  } else {
    mismatches.forEach((mismatch, index) => {
      lines.push(`${index + 1}. ${mismatch}`);
    });
  }

  lines.push("");
  lines.push("## Run Totals");
  lines.push("");
  lines.push(`- Passed: ${passedCount}`);
  lines.push(`- Failed: ${failedCount}`);
  lines.push(`- Skipped: ${skippedCount}`);
  lines.push("");
  lines.push("## Notes");
  lines.push("");
  lines.push(
    "- Condition A and Condition B are configured independently so the teammates can wire in their real command lines later.",
  );
  lines.push(
    "- The default path assumes those condition modules emit recommendation JSON, which is then handed to the measurement module.",
  );
  lines.push(
    "- If a condition module already emits the final CSV directly, change its artifact kind in src/config.ts to results-csv.",
  );

  await writeTextFile(args.outputPath, `${lines.join("\n")}\n`);
}

export function createSummaryCsv(rows: MeasuredOutputRow[]): string {
  const header = [
    "query_id",
    "recommended_indexes",
    "llm_reasoning_text",
    "execution_time_ms_after",
    "improvement_vs_baseline",
    "tool_call_log",
  ];

  const csvRows = [header];

  for (const row of rows) {
    csvRows.push([
      row.query_id,
      row.recommended_indexes,
      row.llm_reasoning_text,
      row.execution_time_ms_after.toString(),
      row.improvement_vs_baseline === null
        ? ""
        : row.improvement_vs_baseline.toString(),
      row.tool_call_log ?? "",
    ]);
  }

  return toCsvContent(csvRows);
}
