import path from "node:path";
import process from "node:process";

import { normalizeRecommendationOutput } from "./recommendation";
import { readSchemaWorkloadInput, writeSchemaWorkloadOutput } from "./schema";

interface CliArgs {
  mode?: "schema-workload" | "recommendation";
  input?: string;
  to?: "baseline" | "condition_a" | "condition_b";
  source?: "condition_a" | "condition_b";
  output?: string;
  help?: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];

    if (token === "--help" || token === "-h") {
      args.help = true;
      continue;
    }

    if (token === "--mode") {
      args.mode = argv[index + 1] as CliArgs["mode"];
      index += 1;
      continue;
    }

    if (token === "--input") {
      args.input = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--to") {
      args.to = argv[index + 1] as CliArgs["to"];
      index += 1;
      continue;
    }

    if (token === "--source") {
      args.source = argv[index + 1] as CliArgs["source"];
      index += 1;
      continue;
    }

    if (token === "--output") {
      args.output = argv[index + 1];
      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${token}`);
  }

  return args;
}

function printUsage(): void {
  console.log("Usage:");
  console.log("  npm run adapt -- --mode schema-workload --input ./input.json --to baseline --output ./out/");
  console.log("  npm run adapt -- --mode schema-workload --input ./schema.sql --to condition_a --output ./out/");
  console.log("  npm run adapt -- --mode recommendation --input ./result.csv --source condition_a --output ./out/");
}

function assertValue<T>(value: T | undefined, message: string): T {
  if (value === undefined) {
    throw new Error(message);
  }

  return value;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  const mode = assertValue(args.mode, "--mode is required.");
  const input = path.resolve(process.cwd(), assertValue(args.input, "--input is required."));
  const output = path.resolve(process.cwd(), assertValue(args.output, "--output is required."));

  if (mode === "schema-workload") {
    const target = assertValue(args.to, "--to is required when --mode schema-workload is used.");
    const result = await readSchemaWorkloadInput(input);

    console.log(`[adapters] Detected schema/workload input shape: ${result.format}`);
    for (const warning of result.warnings) {
      console.warn(`[adapters] ${warning}`);
    }

    const writeWarnings = await writeSchemaWorkloadOutput(result.canonical, target, output);
    for (const warning of writeWarnings) {
      console.warn(`[adapters] ${warning}`);
    }

    console.log(`[adapters] Wrote normalized schema/workload output for ${target} to ${output}`);
    return;
  }

  const source = assertValue(args.source, "--source is required when --mode recommendation is used.");
  const bundle = await normalizeRecommendationOutput(input, source, output);

  console.log(`[adapters] Detected recommendation input variant: ${bundle.detectedVariant}`);
  for (const warning of bundle.warnings) {
    console.warn(`[adapters] ${warning}`);
  }

  console.log(`[adapters] Wrote normalized recommendation output for ${source} to ${output}`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[adapters] Failed: ${message}`);
  process.exit(1);
});