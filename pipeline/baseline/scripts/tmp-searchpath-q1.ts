import path from 'node:path';
import dotenv from 'dotenv';
import { Client } from 'pg';
import { readSchemaWorkloadInput } from '../src/input';

dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

async function main(): Promise<void> {
  const input = await readSchemaWorkloadInput(path.resolve(__dirname, '..', '..', '..', 'results', 'louis', 'tpc-h', 'baseline_input.json'));
  const client = new Client({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT),
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_DATABASE,
  });
  await client.connect();
  try {
    await client.query(`SET search_path TO ${input.schema_name}, public`);
    const searchPath = await client.query('SHOW search_path');
    const q1 = input.workload.find((query) => query.query_id === 'Q1');
    if (!q1) throw new Error('Missing Q1');
    const result = await client.query(q1.query_text.trim().replace(/;\s*$/, ''));
    console.log(JSON.stringify({ search_path: searchPath.rows[0].search_path, rowCount: result.rowCount, rows: result.rows }, null, 2));
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
