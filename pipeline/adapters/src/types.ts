import type { promises as fsPromises } from "node:fs";

export type SchemaWorkloadTarget = "baseline" | "condition_a" | "condition_b";

export interface WorkloadQuery {
  query_id: string;
  query_text: string;
  complexity_tier: "Simple" | "Medium" | "Complex";
}

export interface CanonicalSchemaWorkload {
  schema_name: string;
  schema_ddl: string;
  workload: WorkloadQuery[];
}

export interface IndexRecommendation {
  table: string;
  columns: string[];
  raw_sql?: string;
}

export interface CanonicalRecommendationRow {
  query_id: string;
  recommended_indexes: IndexRecommendation[];
  llm_reasoning_text: string;
  execution_time_ms_after: string;
  improvement_vs_baseline: string;
  tool_call_log: string;
}

export interface CanonicalRecommendationBundle {
  sourceModule: "condition_a" | "condition_b";
  detectedVariant: string;
  rows: CanonicalRecommendationRow[];
  recommendation: {
    schema_name?: string;
    condition?: "A" | "B";
    recommended_indexes: IndexRecommendation[];
    llm_reasoning_text: string;
    tool_call_log?: unknown[] | null;
  };
  warnings: string[];
}

export interface DetectionResult {
  kind: string;
  warnings: string[];
}

export interface FileSystemAdapter {
  readFile: typeof fsPromises.readFile;
  writeFile: typeof fsPromises.writeFile;
  mkdir: typeof fsPromises.mkdir;
  access: typeof fsPromises.access;
}