import dotenv from 'dotenv';

import type { DatabaseConfig, RuntimeConfig } from './types';

dotenv.config();

function readEnvValue(names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value !== undefined && value.trim().length > 0) {
      return value.trim();
    }
  }

  return undefined;
}

function requireEnvValue(names: string[], label: string): string {
  const value = readEnvValue(names);
  if (value === undefined) {
    throw new Error(`Missing required database config for ${label}. Set one of: ${names.join(', ')}`);
  }

  return value;
}

function readOptionalIntegerEnv(names: string[], fallback: number): number {
  for (const name of names) {
    const value = process.env[name];
    if (value !== undefined && value.trim().length > 0) {
      const parsedValue = Number.parseInt(value.trim(), 10);
      if (Number.isInteger(parsedValue) && parsedValue > 0) {
        return parsedValue;
      }

      throw new Error(`Invalid integer for ${name}: ${value}`);
    }
  }

  return fallback;
}

export function loadDatabaseConfig(): DatabaseConfig {
  const portText = requireEnvValue(['DB_PORT', 'PGPORT'], 'port');
  const parsedPort = Number.parseInt(portText, 10);

  if (!Number.isInteger(parsedPort) || parsedPort <= 0) {
    throw new Error(`Invalid database port: ${portText}`);
  }

  return {
    host: requireEnvValue(['DB_HOST', 'PGHOST'], 'host'),
    port: parsedPort,
    user: requireEnvValue(['DB_USER', 'PGUSER'], 'user'),
    password: requireEnvValue(['DB_PASSWORD', 'PGPASSWORD'], 'password'),
    database: requireEnvValue(['DB_DATABASE', 'PGDATABASE'], 'database')
  };
}

export function loadRuntimeConfig(): RuntimeConfig {
  return {
    statementTimeoutMs: readOptionalIntegerEnv(
      ['STATEMENT_TIMEOUT_MS', 'DB_STATEMENT_TIMEOUT_MS', 'PGSTATEMENT_TIMEOUT_MS'],
      120000,
    ),
  };
}