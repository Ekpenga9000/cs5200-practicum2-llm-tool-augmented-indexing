import { Client } from 'pg';

import type { DatabaseConfig } from './types';

export async function connectToPostgres(config: DatabaseConfig): Promise<Client> {
  const client = new Client(config);
  await client.connect();
  return client;
}

export async function closePostgresConnection(client: Client): Promise<void> {
  await client.end();
}