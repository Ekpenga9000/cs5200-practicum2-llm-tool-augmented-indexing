import type { PoolConfig } from 'pg';

export type ComplexityTier = 'Simple' | 'Medium' | 'Complex';

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

export interface DatabaseConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
}

export interface LoadedDatabaseConfig extends PoolConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
}

export interface BaselineRunSummary {
  schemaName: string;
  outputPath: string;
  rowCount: number;
}

export type SchemaMode = 'fresh' | 'existing';