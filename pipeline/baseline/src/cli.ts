import path from 'node:path';

import { runBaselineModule } from './pipeline';

interface CliArgs {
  input?: string;
  output?: string;
  schemaMode?: 'fresh' | 'existing';
  help?: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];

    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }

    if (token === '--input') {
      args.input = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === '--output') {
      args.output = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === '--schema-mode') {
      const value = argv[index + 1];
      if (value !== 'fresh' && value !== 'existing') {
        throw new Error("--schema-mode must be 'fresh' or 'existing'.");
      }

      args.schemaMode = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${token}`);
  }

  return args;
}

function printUsage(): void {
  console.log('Usage: npm run baseline -- --input ./path/to/schema-workload.json --output ./path/to/baseline_results.csv [--schema-mode fresh|existing]');
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  if (args.input === undefined || args.output === undefined) {
    printUsage();
    throw new Error('Both --input and --output are required.');
  }

  const inputPath = path.resolve(process.cwd(), args.input);
  const outputPath = path.resolve(process.cwd(), args.output);
  const summary = await runBaselineModule(inputPath, outputPath, args.schemaMode ?? 'fresh');

  console.log(`Baseline complete for ${summary.schemaName}: wrote ${summary.rowCount} rows to ${summary.outputPath}`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Baseline module failed: ${message}`);
  process.exit(1);
});