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

function splitStatements(queryText: string): string[] {
  return queryText
    .split(';')
    .map((statement) => statement.trim())
    .filter((statement) => statement.length > 0);
}

function isExplainableStatement(statement: string): boolean {
  return /^(select|with|values)\b/i.test(statement);
}

function isStatementTimeoutError(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) {
    return false;
  }

  const record = error as Record<string, unknown>;
  return record.code === '57014' || String(record.message ?? '').includes('canceling statement due to statement timeout');
}

export async function explainAnalyzeQuery(client: Client, queryId: string, queryText: string, statementTimeoutMs: number): Promise<BaselineOutputRow> {
  const cleanedQueryText = normalizeQueryText(queryText);

  const statements = splitStatements(cleanedQueryText);
  let explainableStatement = cleanedQueryText;
  const postStatements: string[] = [];

  if (statements.length > 1) {
    const explainableIndex = statements.findIndex((statement) => isExplainableStatement(statement));

    if (explainableIndex >= 0) {
      for (let index = 0; index < explainableIndex; index += 1) {
        await client.query(statements[index]);
      }

      explainableStatement = statements[explainableIndex];

      for (let index = explainableIndex + 1; index < statements.length; index += 1) {
        postStatements.push(statements[index]);
      }
    }
  }

  await client.query(`SET statement_timeout = ${statementTimeoutMs}`);

  try {
    const result = await client.query(`EXPLAIN ANALYZE ${explainableStatement}`);
    const planLines = result.rows.map((row) => {
      const planLine = row['QUERY PLAN'];
      return typeof planLine === 'string' ? planLine : String(planLine ?? '');
    });
    const queryPlanText = planLines.join('\n');
    const executionTimeMs = parseExecutionTime(queryPlanText);

    for (const statement of postStatements) {
      await client.query(statement);
    }

    return {
      query_id: queryId,
      execution_time_ms: executionTimeMs,
      query_plan_text: queryPlanText
    };
  } catch (error) {
    if (isStatementTimeoutError(error)) {
      console.warn(`Query ${queryId} timed out after ${statementTimeoutMs}ms.`);

      for (const statement of postStatements) {
        try {
          await client.query(statement);
        } catch {
          // Ignore cleanup failures after timeout.
        }
      }

      return {
        query_id: queryId,
        execution_time_ms: statementTimeoutMs,
        query_plan_text: `TIMEOUT - query exceeded ${statementTimeoutMs}ms limit`
      };
    }

    throw error;
  }
}