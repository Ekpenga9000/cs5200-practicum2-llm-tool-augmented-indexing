import dotenv from 'dotenv';

import type { DatabaseConfig } from './types';

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