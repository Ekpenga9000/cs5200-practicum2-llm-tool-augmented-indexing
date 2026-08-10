import path from 'node:path';

import dotenv from 'dotenv';
import { Client } from 'pg';

dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

async function main(): Promise<void> {
  const client = new Client({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT),
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_DATABASE,
  });

  await client.connect();

  try {
    const schemas = await client.query(`
      select table_schema, count(*)::int as table_count
      from information_schema.tables
      where table_schema in ('tpch', 'tpc-h')
      group by table_schema
      order by table_schema;
    `);
    console.log(JSON.stringify({ schemas: schemas.rows }, null, 2));

    const counts = await client.query(`
      select 'tpch' as schema_name, count(*)::bigint as lineitem_rows from tpch.lineitem
      union all
      select 'tpc-h' as schema_name, count(*)::bigint as lineitem_rows from "tpc-h".lineitem;
    `);
    console.log(JSON.stringify({ counts: counts.rows }, null, 2));
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
});