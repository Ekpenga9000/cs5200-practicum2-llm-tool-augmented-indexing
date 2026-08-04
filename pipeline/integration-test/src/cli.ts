import process from "node:process";

import { loadHarnessConfig } from "./config";
import { runIntegrationHarness } from "./orchestrator";

interface CliArgs {
  input?: string;
  outputDir?: string;
  pythonCommand?: string;
  baselineCommand?: string;
  baselineCwd?: string;
  conditionACommand?: string;
  conditionACwd?: string;
  conditionAArtifactKind?: "recommendation-json" | "results-csv";
  conditionBCommand?: string;
  conditionBCwd?: string;
  conditionBArtifactKind?: "recommendation-json" | "results-csv";
  measurementCommand?: string;
  measurementCwd?: string;
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

    if (token === "--input") {
      args.input = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--output-dir") {
      args.outputDir = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--python-command") {
      args.pythonCommand = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--baseline-command") {
      args.baselineCommand = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--baseline-cwd") {
      args.baselineCwd = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--condition-a-command") {
      args.conditionACommand = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--condition-a-cwd") {
      args.conditionACwd = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--condition-a-kind") {
      const value = argv[index + 1];
      if (value !== "recommendation-json" && value !== "results-csv") {
        throw new Error(
          "--condition-a-kind must be 'recommendation-json' or 'results-csv'.",
        );
      }

      args.conditionAArtifactKind = value;
      index += 1;
      continue;
    }

    if (token === "--condition-b-command") {
      args.conditionBCommand = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--condition-b-cwd") {
      args.conditionBCwd = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--condition-b-kind") {
      const value = argv[index + 1];
      if (value !== "recommendation-json" && value !== "results-csv") {
        throw new Error(
          "--condition-b-kind must be 'recommendation-json' or 'results-csv'.",
        );
      }

      args.conditionBArtifactKind = value;
      index += 1;
      continue;
    }

    if (token === "--measurement-command") {
      args.measurementCommand = argv[index + 1];
      index += 1;
      continue;
    }

    if (token === "--measurement-cwd") {
      args.measurementCwd = argv[index + 1];
      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${token}`);
  }

  return args;
}

function printUsage(): void {
  console.log("Usage: npm run integration-test -- [options]");
  console.log("");
  console.log("Options:");
  console.log("  --input <path>");
  console.log("  --output-dir <path>");
  console.log("  --baseline-command <template>");
  console.log("  --condition-a-command <template>");
  console.log("  --condition-a-kind recommendation-json|results-csv");
  console.log("  --condition-b-command <template>");
  console.log("  --condition-b-kind recommendation-json|results-csv");
  console.log("  --measurement-command <template>");
  console.log("  --python-command <path>");
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  const config = loadHarnessConfig({
    inputPath: args.input,
    outputDir: args.outputDir,
    pythonCommand: args.pythonCommand,
    baselineCommandTemplate: args.baselineCommand,
    baselineCwd: args.baselineCwd,
    conditionACommandTemplate: args.conditionACommand,
    conditionACwd: args.conditionACwd,
    conditionAArtifactKind: args.conditionAArtifactKind,
    conditionBCommandTemplate: args.conditionBCommand,
    conditionBCwd: args.conditionBCwd,
    conditionBArtifactKind: args.conditionBArtifactKind,
    measurementCommandTemplate: args.measurementCommand,
    measurementCwd: args.measurementCwd,
  });

  const result = await runIntegrationHarness(config);

  console.log("\nIntegration test finished.");
  console.log(`Report written to: ${result.reportPath}`);

  const failedStages = result.stageResults.filter(
    (stage) => stage.status === "failed",
  );

  if (failedStages.length > 0) {
    console.error(
      "One or more stages failed. See the report for exact mismatch details.",
    );
    process.exitCode = 1;
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Integration harness failed: ${message}`);
  process.exit(1);
});
