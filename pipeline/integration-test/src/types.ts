export type ComplexityTier = "Simple" | "Medium" | "Complex";

export interface WorkloadQuery {
  query_id: string;
  query_text: string;
  complexity_tier: ComplexityTier;
}

export interface SchemaWorkloadInput {
  schema_name: string;
  schema_ddl: string;
  workload: WorkloadQuery[];
}

export interface BaselineOutputRow {
  query_id: string;
  execution_time_ms: number;
  query_plan_text: string;
}

export interface RecommendationToolCallLogEntry {
  [key: string]: unknown;
}

export interface RecommendationArtifact {
  schema_name?: string;
  condition?: string;
  query_id?: string;
  recommended_indexes: unknown[];
  llm_reasoning_text: string;
  tool_call_log?: RecommendationToolCallLogEntry[];
}

export interface MeasuredOutputRow {
  query_id: string;
  recommended_indexes: string;
  llm_reasoning_text: string;
  execution_time_ms_after: number;
  improvement_vs_baseline: number | null;
  tool_call_log?: string;
}

export type StageStatus = "passed" | "failed" | "skipped";

export interface StageResult {
  name: string;
  status: StageStatus;
  durationMs: number;
  command?: string;
  cwd?: string;
  outputPath?: string;
  stdout: string;
  stderr: string;
  validationErrors: string[];
  errorMessage?: string;
}

export interface HarnessRunResult {
  inputPath: string;
  outputDir: string;
  schema: SchemaWorkloadInput;
  stageResults: StageResult[];
  reportPath: string;
}

export type ConditionArtifactKind = "recommendation-json" | "results-csv";

export interface HarnessConfig {
  inputPath: string;
  outputDir: string;
  pythonCommand: string;
  baselineCommandTemplate: string;
  baselineCwd: string;
  conditionACommandTemplate: string;
  conditionACwd: string;
  conditionAArtifactKind: ConditionArtifactKind;
  conditionBCommandTemplate: string;
  conditionBCwd: string;
  conditionBArtifactKind: ConditionArtifactKind;
  measurementCommandTemplate: string;
  measurementCwd: string;
}
