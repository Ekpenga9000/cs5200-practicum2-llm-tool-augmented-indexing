import { promises as fs } from 'node:fs';
import path from 'node:path';

import { createObjectCsvWriter } from 'csv-writer';

import type { BaselineOutputRow } from './types';

export async function writeBaselineResultsCsv(outputPath: string, rows: BaselineOutputRow[]): Promise<void> {
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  const writer = createObjectCsvWriter({
    path: outputPath,
    header: [
      { id: 'query_id', title: 'query_id' },
      { id: 'execution_time_ms', title: 'execution_time_ms' },
      { id: 'query_plan_text', title: 'query_plan_text' }
    ]
  });

  await writer.writeRecords(rows);
}