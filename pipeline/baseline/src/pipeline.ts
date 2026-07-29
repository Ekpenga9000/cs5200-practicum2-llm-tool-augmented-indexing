import type { Client } from 'pg';

import { loadDatabaseConfig } from './config';
import { closePostgresConnection, connectToPostgres } from './db';
import { createFreshSchema, dropRunSchema } from './ddl';
import { explainAnalyzeQuery } from './explain';
import { readSchemaWorkloadInput } from './input';
import { writeBaselineResultsCsv } from './csv';
import type { BaselineRunSummary, SchemaWorkloadInput } from './types';

async function runQueries(client: Client, input: SchemaWorkloadInput) {
  const rows = [];

  for (const query of input.workload) {
    rows.push(await explainAnalyzeQuery(client, query.query_id, query.query_text));
  }

  return rows;
}

export async function runBaselineModule(inputPath: string, outputPath: string): Promise<BaselineRunSummary> {
  const input = await readSchemaWorkloadInput(inputPath);
  const config = loadDatabaseConfig();
  const client = await connectToPostgres(config);

  let runSchemaName: string | null = null;

  try {
    runSchemaName = await createFreshSchema(client, input.schema_name, input.schema_ddl);
    const rows = await runQueries(client, input);
    await writeBaselineResultsCsv(outputPath, rows);

    return {
      schemaName: input.schema_name,
      outputPath,
      rowCount: rows.length
    };
  } finally {
    if (runSchemaName !== null) {
      try {
        await dropRunSchema(client, runSchemaName);
      } catch (error) {
        console.warn(`Warning: failed to clean up schema ${runSchemaName}: ${(error as Error).message}`);
      }
    }

    await closePostgresConnection(client);
  }
}