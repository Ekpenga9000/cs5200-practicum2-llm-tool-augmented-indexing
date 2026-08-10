import type { Client } from 'pg';

import { loadDatabaseConfig } from './config';
import { closePostgresConnection, connectToPostgres } from './db';
import { createFreshSchema, dropRunSchema, useExistingSchema } from './ddl';
import { explainAnalyzeQuery } from './explain';
import { readSchemaWorkloadInput } from './input';
import { writeBaselineResultsCsv } from './csv';
import { loadRuntimeConfig } from './config';
import type { BaselineRunSummary, SchemaMode, SchemaWorkloadInput } from './types';

async function runQueries(client: Client, input: SchemaWorkloadInput, statementTimeoutMs: number) {
  const rows = [];

  for (const query of input.workload) {
    rows.push(await explainAnalyzeQuery(client, query.query_id, query.query_text, statementTimeoutMs));
  }

  return rows;
}

export async function runBaselineModule(
  inputPath: string,
  outputPath: string,
  schemaMode: SchemaMode = 'fresh',
): Promise<BaselineRunSummary> {
  const input = await readSchemaWorkloadInput(inputPath);
  const config = loadDatabaseConfig();
  const runtimeConfig = loadRuntimeConfig();
  const client = await connectToPostgres(config);

  let runSchemaName: string | null = null;

  try {
    if (schemaMode === 'existing') {
      await useExistingSchema(client, input.schema_name);
      runSchemaName = input.schema_name;
    } else {
      runSchemaName = await createFreshSchema(client, input.schema_name, input.schema_ddl);
    }
    const rows = await runQueries(client, input, runtimeConfig.statementTimeoutMs);
    await writeBaselineResultsCsv(outputPath, rows);

    return {
      schemaName: input.schema_name,
      outputPath,
      rowCount: rows.length
    };
  } finally {
    if (runSchemaName !== null && schemaMode === 'fresh') {
      try {
        await dropRunSchema(client, runSchemaName);
      } catch (error) {
        console.warn(`Warning: failed to clean up schema ${runSchemaName}: ${(error as Error).message}`);
      }
    }

    await closePostgresConnection(client);
  }
}