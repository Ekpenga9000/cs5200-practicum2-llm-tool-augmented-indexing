import path from 'node:path';
import dotenv from 'dotenv';
import { promises as fs } from 'node:fs';
import { Client } from 'pg';

import { readSchemaWorkloadInput } from '../src/input';

dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let field = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (inQuotes) {
      if (character === '"') {
        if (line[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += character;
      }
      continue;
    }

    if (character === '"') {
      inQuotes = true;
      continue;
    }

    if (character === ',') {
      fields.push(field);
      field = '';
      continue;
    }

    field += character;
  }

  fields.push(field);
  return fields;
}

async function loadCsvMap(csvPath: string): Promise<Map<string, { execution_time_ms: string; query_plan_text: string }>> {
  const content = await fs.readFile(csvPath, 'utf8');
  const lines = content.trimEnd().split(/\r?\n/);
  const header = parseCsvLine(lines[0]);
  const qidIndex = header.indexOf('query_id');
  const execIndex = header.indexOf('execution_time_ms');
  const planIndex = header.indexOf('query_plan_text');
  const map = new Map<string, { execution_time_ms: string; query_plan_text: string }>();

  for (const line of lines.slice(1)) {
    const row = parseCsvLine(line);
    map.set(row[qidIndex], {
      execution_time_ms: row[execIndex],
      query_plan_text: row[planIndex],
    });
  }

  return map;
}

function topRows(planText: string): string | null {
  const match = planText.match(/rows=(\d+)/);
  return match ? match[1] : null;
}

async function main(): Promise<void> {
  const baselineInputPath = path.resolve(__dirname, '..', '..', '..', 'results', 'louis', 'tpc-h', 'baseline_input.json');
  const baselineCsvPath = path.resolve(__dirname, '..', '..', '..', 'results', 'louis', 'tpc-h', 'baseline_results.csv');

  const input = await readSchemaWorkloadInput(baselineInputPath);
  const csvMap = await loadCsvMap(baselineCsvPath);

  const client = new Client({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT),
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_DATABASE,
  });

  await client.connect();
  try {
    await client.query('SET search_path TO tpch, public');

    const qids = ['Q1', 'Q6', 'Q9', 'Q14'];
    for (const qid of qids) {
      const query = input.workload.find((item) => item.query_id === qid);
      if (!query) {
        throw new Error(`Missing ${qid}`);
      }

      const explainResult = await client.query(`EXPLAIN ANALYZE ${query.query_text.trim().replace(/;\s*$/, '')}`);
      const planText = explainResult.rows.map((row) => row['QUERY PLAN']).join('\n');
      const csvRow = csvMap.get(qid);

      console.log(`=== ${qid} ===`);
      console.log(JSON.stringify({
        csvExecutionMs: csvRow?.execution_time_ms,
        csvTopRows: csvRow ? topRows(csvRow.query_plan_text) : null,
        explainExecutionMs: planText.match(/Execution Time:\s*([0-9]+(?:\.[0-9]+)?) ms/)?.[1] ?? null,
        explainTopRows: topRows(planText),
        tier: query.complexity_tier,
      }, null, 2));
    }
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
});