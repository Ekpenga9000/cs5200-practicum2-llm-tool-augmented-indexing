import type { Client } from 'pg';

import type { BaselineOutputRow } from './types';

function normalizeQueryText(queryText: string): string {
  return queryText.trim().replace(/;\s*$/, '');
}

function parseExecutionTime(planText: string): number {
  const match = planText.match(/Execution Time:\s*([0-9]+(?:\.[0-9]+)?) ms/i);
  if (!match) {
    throw new Error('Could not find Execution Time in EXPLAIN ANALYZE output.');
  }

  return Number.parseFloat(match[1]);
}

export async function explainAnalyzeQuery(client: Client, queryId: string, queryText: string): Promise<BaselineOutputRow> {
  const cleanedQueryText = normalizeQueryText(queryText);
  const result = await client.query(`EXPLAIN ANALYZE ${cleanedQueryText}`);
  const planLines = result.rows.map((row) => {
    const planLine = row['QUERY PLAN'];
    return typeof planLine === 'string' ? planLine : String(planLine ?? '');
  });
  const queryPlanText = planLines.join('\n');
  const executionTimeMs = parseExecutionTime(queryPlanText);

  return {
    query_id: queryId,
    execution_time_ms: executionTimeMs,
    query_plan_text: queryPlanText
  };
}