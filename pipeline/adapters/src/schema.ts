import path from "node:path";
import { promises as fs } from "node:fs";

import { parseCsv, toCsv } from "./csv";
import type {
  CanonicalSchemaWorkload,
  SchemaWorkloadTarget,
  WorkloadQuery,
} from "./types";

function warn(message: string): void {
  console.warn(`[adapters][schema-workload] ${message}`);
}

function isCanonicalSchemaWorkload(value: unknown): value is CanonicalSchemaWorkload {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const record = value as Record<string, unknown>;
  return typeof record.schema_name === "string" && typeof record.schema_ddl === "string" && Array.isArray(record.workload);
}

function isConditionBShape(value: unknown): value is { schema_name: string; ddl: string; queries: WorkloadQuery[] } {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const record = value as Record<string, unknown>;
  return typeof record.schema_name === "string" && typeof record.ddl === "string" && Array.isArray(record.queries);
}

function parseWorkloadCsv(csvText: string): WorkloadQuery[] {
  const rows = parseCsv(csvText);
  if (rows.length === 0) {
    return [];
  }

  const header = rows[0];
  const queryIdIndex = header.indexOf("query_id");
  const queryTextIndex = header.indexOf("query_text");
  const tierIndex = header.indexOf("complexity_tier");

  if (queryIdIndex < 0 || queryTextIndex < 0 || tierIndex < 0) {
    throw new Error(`workload.csv is missing one of the required columns: query_id, query_text, complexity_tier`);
  }

  return rows.slice(1).filter((row) => row.some((cell) => cell.trim().length > 0)).map((row, index) => {
    const query_id = row[queryIdIndex]?.trim();
    const query_text = row[queryTextIndex]?.trim();
    const complexity_tier = row[tierIndex]?.trim() as WorkloadQuery["complexity_tier"];

    if (!query_id) {
      warn(`workload row ${index + 2} is missing query_id; defaulting to an empty string.`);
    }

    if (!query_text) {
      warn(`workload row ${index + 2} is missing query_text; defaulting to an empty string.`);
    }

    if (complexity_tier !== "Simple" && complexity_tier !== "Medium" && complexity_tier !== "Complex") {
      warn(`workload row ${index + 2} has an unexpected complexity_tier '${row[tierIndex] ?? ""}'; leaving it as-is.`);
    }

    return {
      query_id: query_id ?? "",
      query_text: query_text ?? "",
      complexity_tier: complexity_tier || "Simple",
    };
  });
}

function writeWorkloadCsv(filePath: string, workload: WorkloadQuery[]): Promise<void> {
  const rows = [["query_id", "query_text", "complexity_tier"], ...workload.map((query) => [query.query_id, query.query_text, query.complexity_tier])];
  return fs.writeFile(filePath, toCsv(rows), "utf8");
}

function withDefaultFileName(outputPath: string, fileName: string): string {
  if (path.extname(outputPath).length > 0) {
    return outputPath;
  }

  return path.join(outputPath, fileName);
}

export async function readSchemaWorkloadInput(inputPath: string): Promise<{ format: string; canonical: CanonicalSchemaWorkload; warnings: string[] }> {
  const warnings: string[] = [];
  const stat = await fs.stat(inputPath);

  if (stat.isDirectory()) {
    const schemaPath = path.join(inputPath, "schema.sql");
    const workloadPath = path.join(inputPath, "workload.csv");
    const [schemaDdl, workloadCsv] = await Promise.all([
      fs.readFile(schemaPath, "utf8"),
      fs.readFile(workloadPath, "utf8"),
    ]);

    return {
      format: "condition_a",
      canonical: {
        schema_name: path.basename(inputPath),
        schema_ddl: schemaDdl,
        workload: parseWorkloadCsv(workloadCsv),
      },
      warnings,
    };
  }

  const text = await fs.readFile(inputPath, "utf8");

  if (inputPath.endsWith(".csv")) {
    const workload = parseWorkloadCsv(text);
    const schemaSqlPath = inputPath.replace(/\.csv$/i, ".sql");

    if (await fileExists(schemaSqlPath)) {
      warnings.push(`Detected paired schema.sql next to ${path.basename(inputPath)}.`);
      return {
        format: "condition_a",
        canonical: {
          schema_name: path.basename(path.dirname(inputPath)),
          schema_ddl: await fs.readFile(schemaSqlPath, "utf8"),
          workload,
        },
        warnings,
      };
    }
  }

  try {
    const parsed = JSON.parse(text) as unknown;

    if (isCanonicalSchemaWorkload(parsed)) {
      return {
        format: "baseline",
        canonical: parsed,
        warnings,
      };
    }

    if (isConditionBShape(parsed)) {
      return {
        format: "condition_b",
        canonical: {
          schema_name: parsed.schema_name,
          schema_ddl: parsed.ddl,
          workload: parsed.queries,
        },
        warnings,
      };
    }
  } catch (error) {
    warnings.push(`Unable to parse ${path.basename(inputPath)} as JSON: ${(error as Error).message}`);
  }

  throw new Error(`Unrecognized schema/workload input shape at ${inputPath}`);
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function writeSchemaWorkloadOutput(
  canonical: CanonicalSchemaWorkload,
  targetFormat: SchemaWorkloadTarget,
  outputPath: string,
): Promise<string[]> {
  const warnings: string[] = [];
  const resolvedOutput = outputPath.endsWith(path.sep) || (await pathLikeDirectory(outputPath))
    ? outputPath
    : outputPath;

  if (targetFormat === "baseline") {
    const filePath = withDefaultFileName(resolvedOutput, "schema_workload.json");
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, `${JSON.stringify(canonical, null, 2)}\n`, "utf8");
    return warnings;
  }

  if (targetFormat === "condition_b") {
    const filePath = withDefaultFileName(resolvedOutput, "schema_workload.json");
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(
      filePath,
      `${JSON.stringify(
        {
          schema_name: canonical.schema_name,
          ddl: canonical.schema_ddl,
          queries: canonical.workload,
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
    return warnings;
  }

  const directoryPath = resolvedOutput;
  await fs.mkdir(directoryPath, { recursive: true });
  await fs.writeFile(path.join(directoryPath, "schema.sql"), `${canonical.schema_ddl.trim()}\n`, "utf8");
  await writeWorkloadCsv(path.join(directoryPath, "workload.csv"), canonical.workload);

  if (!canonical.schema_name) {
    warnings.push("schema_name was blank; generated files without a schema-specific label.");
  }

  return warnings;
}

async function pathLikeDirectory(outputPath: string): Promise<boolean> {
  if (outputPath.endsWith(path.sep)) {
    return true;
  }

  try {
    const stat = await fs.stat(outputPath);
    return stat.isDirectory();
  } catch {
    return false;
  }
}