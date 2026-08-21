import path from 'node:path';
import { createReadStream } from 'node:fs';
import { promises as fs } from 'node:fs';
import { Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';

import dotenv from 'dotenv';
import { Client } from 'pg';

const copyFrom = require('pg-copy-streams/copy-from');

dotenv.config({ path: path.resolve(__dirname, '..', '..', '.env') });

function readArg(index: number, fallback: string): string {
  return process.argv[index] ?? fallback;
}

function quoteIdentifier(identifier: string): string {
  return `"${identifier.replace(/"/g, '""')}"`;
}

class TpcdsPipeNormalizer extends Transform {
  private buffer = '';

  public rowCount = 0;

  _transform(chunk: Buffer | string, _encoding: BufferEncoding, callback: (error?: Error | null) => void): void {
    try {
      this.buffer += typeof chunk === 'string' ? chunk : chunk.toString('utf8');
      const lines = this.buffer.split(/\r?\n/);
      this.buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.length === 0) {
          continue;
        }

        const normalizedLine = line.endsWith('|') ? line.slice(0, -1) : line;
        this.push(`${normalizedLine}\n`);
        this.rowCount += 1;
      }

      callback();
    } catch (error) {
      callback(error as Error);
    }
  }

  _flush(callback: (error?: Error | null) => void): void {
    try {
      if (this.buffer.length > 0) {
        const normalizedLine = this.buffer.endsWith('|') ? this.buffer.slice(0, -1) : this.buffer;
        this.push(`${normalizedLine}\n`);
        this.rowCount += 1;
      }

      callback();
    } catch (error) {
      callback(error as Error);
    }
  }
}

async function loadTable(client: Client, schemaName: string, tableName: string, sourcePath: string): Promise<number> {
  console.log(`Loading ${tableName} from ${sourcePath}...`);

  const copySql = `COPY ${quoteIdentifier(schemaName)}.${quoteIdentifier(tableName)} FROM STDIN WITH (FORMAT csv, DELIMITER '|', NULL '')`;
  const copyStream = client.query(copyFrom(copySql));
  const normalizer = new TpcdsPipeNormalizer();

  await pipeline(createReadStream(sourcePath), normalizer, copyStream);

  return normalizer.rowCount;
}

async function main(): Promise<void> {
  const dbName = readArg(2, process.env.DB_DATABASE ?? process.env.PGDATABASE ?? 'postgres');
  const schemaName = readArg(5, 'dsb');
  const schemaSqlPath = path.resolve(
    readArg(3, path.join(__dirname, '..', '..', '..', '..', 'results', 'Ikenna', 'dsb', 'schema.sql')),
  );
  const dataDir = path.resolve(
    readArg(4, path.join(__dirname, '..', '..', '..', '..', 'pipeline', 'baseline', 'scripts', 'tpcds-data', 'generated')),
  );

  const dbHost = process.env.DB_HOST ?? process.env.PGHOST ?? 'localhost';
  const dbPort = Number.parseInt(process.env.DB_PORT ?? process.env.PGPORT ?? '5432', 10);
  const dbUser = process.env.DB_USER ?? process.env.PGUSER ?? 'postgres';
  const dbPassword = process.env.DB_PASSWORD ?? process.env.PGPASSWORD ?? 'postgres';

  const client = new Client({
    host: dbHost,
    port: dbPort,
    user: dbUser,
    password: dbPassword,
    database: dbName,
  });

  await client.connect();

  const tableFiles: Array<[string, string]> = [
    ['dbgen_version', 'dbgen_version.dat'],
    ['call_center', 'call_center.dat'],
    ['catalog_page', 'catalog_page.dat'],
    ['customer', 'customer.dat'],
    ['customer_address', 'customer_address.dat'],
    ['customer_demographics', 'customer_demographics.dat'],
    ['date_dim', 'date_dim.dat'],
    ['household_demographics', 'household_demographics.dat'],
    ['income_band', 'income_band.dat'],
    ['item', 'item.dat'],
    ['promotion', 'promotion.dat'],
    ['reason', 'reason.dat'],
    ['ship_mode', 'ship_mode.dat'],
    ['store', 'store.dat'],
    ['time_dim', 'time_dim.dat'],
    ['warehouse', 'warehouse.dat'],
    ['web_page', 'web_page.dat'],
    ['web_site', 'web_site.dat'],
    ['catalog_sales', 'catalog_sales.dat'],
    ['catalog_returns', 'catalog_returns.dat'],
    ['inventory', 'inventory.dat'],
    ['store_sales', 'store_sales.dat'],
    ['store_returns', 'store_returns.dat'],
    ['web_sales', 'web_sales.dat'],
    ['web_returns', 'web_returns.dat'],
  ];

  try {
    const schemaSql = await fs.readFile(schemaSqlPath, 'utf8');

    await client.query(`DROP SCHEMA IF EXISTS ${quoteIdentifier(schemaName)} CASCADE;`);
    await client.query(`CREATE SCHEMA ${quoteIdentifier(schemaName)};`);
    await client.query(`SET search_path TO ${quoteIdentifier(schemaName)}, public;`);
    await client.query(schemaSql);

    let totalRows = 0;

    for (const [tableName, fileName] of tableFiles) {
      const sourcePath = path.join(dataDir, fileName);
      const rowCount = await loadTable(client, schemaName, tableName, sourcePath);
      totalRows += rowCount;
      console.log(`Loaded ${tableName}: ${rowCount.toLocaleString()} rows`);
    }

    await client.query(`SET search_path TO ${quoteIdentifier(schemaName)}, public;`);
    await client.query('ANALYZE;');

    console.log(`TPC-DS data loaded into schema ${schemaName}.`);
    console.log(`Total rows loaded: ${totalRows.toLocaleString()}`);
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`TPC-DS loader failed: ${message}`);
  process.exit(1);
});