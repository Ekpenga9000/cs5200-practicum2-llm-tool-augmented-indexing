import crypto from 'node:crypto';

import type { Client } from 'pg';

function quoteIdentifier(identifier: string): string {
  return `"${identifier.replace(/"/g, '""')}"`;
}

function sanitizeIdentifierPart(value: string): string {
  const cleaned = value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+/, '')
    .replace(/_+$/, '');

  return cleaned.length > 0 ? cleaned : 'baseline';
}

export function buildRunSchemaName(schemaName: string): string {
  const suffix = `${Date.now().toString(36)}_${crypto.randomBytes(3).toString('hex')}`;
  const baseName = sanitizeIdentifierPart(schemaName);
  const rawName = `baseline_${baseName}_${suffix}`;

  return rawName.length <= 63 ? rawName : rawName.slice(0, 63);
}

async function rollbackQuietly(client: Client): Promise<void> {
  try {
    await client.query('ROLLBACK');
  } catch {
    // Ignore rollback failures so the original error can surface.
  }
}

export async function createFreshSchema(client: Client, schemaName: string, schemaDdl: string): Promise<string> {
  const runSchemaName = buildRunSchemaName(schemaName);
  const quotedSchemaName = quoteIdentifier(runSchemaName);

  try {
    await client.query('BEGIN');
    await client.query(`DROP SCHEMA IF EXISTS ${quotedSchemaName} CASCADE;`);
    await client.query(`CREATE SCHEMA ${quotedSchemaName};`);
    await client.query(`SET search_path TO ${quotedSchemaName};`);
    await client.query(schemaDdl);
    await client.query('COMMIT');
    return runSchemaName;
  } catch (error) {
    await rollbackQuietly(client);
    throw new Error(`Failed to create schema ${schemaName}: ${(error as Error).message}`);
  }
}

export async function dropRunSchema(client: Client, runSchemaName: string): Promise<void> {
  const quotedSchemaName = quoteIdentifier(runSchemaName);
  await client.query(`DROP SCHEMA IF EXISTS ${quotedSchemaName} CASCADE;`);
}