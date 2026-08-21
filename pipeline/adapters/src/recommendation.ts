import path from "node:path";
import { promises as fs } from "node:fs";

import { parseCsv, toCsv } from "./csv";
import type {
  CanonicalRecommendationBundle,
  CanonicalRecommendationRow,
  IndexRecommendation,
} from "./types";

function warn(message: string): void {
  console.warn(`[adapters][recommendation] ${message}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseIndexStatement(statement: string): IndexRecommendation | null {
  const trimmed = statement.trim().replace(/;\s*$/, "");

  const match = trimmed.match(/CREATE\s+INDEX\s+\S+\s+ON\s+([A-Za-z0-9_]+)\s*\((.*)\)$/i);
  if (!match) {
    return null;
  }

  const table = match[1];
  const columns = match[2]
    .split(",")
    .map((entry) => entry.trim().split(/\s+/)[0])
    .filter((entry) => entry.length > 0);

  return {
    table,
    columns,
    raw_sql: trimmed,
  };
}

function parseRecommendedIndexesCell(value: string): IndexRecommendation[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }

  if ((trimmed.startsWith("[") || trimmed.startsWith("{")) && trimmed.endsWith(trimmed.startsWith("[") ? "]" : "}")) {
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return normalizeRecommendedIndexes(parsed);
    } catch {
      // Fall through to SQL parsing.
    }
  }

  const chunks = trimmed.includes(";;")
    ? trimmed.split(/;{2,}/)
    : trimmed.split(/\n+/);

  const indexes: IndexRecommendation[] = [];
  for (const chunk of chunks) {
    const parsed = parseIndexStatement(chunk);
    if (parsed !== null) {
      indexes.push(parsed);
    } else if (chunk.trim().length > 0) {
      warn(`Could not parse recommended index statement: ${chunk.trim()}`);
    }
  }

  return indexes;
}

function normalizeRecommendedIndexes(value: unknown): IndexRecommendation[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const indexes: IndexRecommendation[] = [];
  for (const entry of value) {
    if (typeof entry === "string") {
      const parsed = parseIndexStatement(entry);
      if (parsed !== null) {
        indexes.push(parsed);
      }
      continue;
    }

    if (isRecord(entry) && typeof entry.table === "string" && Array.isArray(entry.columns)) {
      indexes.push({
        table: entry.table,
        columns: entry.columns.filter((column): column is string => typeof column === "string"),
        raw_sql: typeof entry.raw_sql === "string" ? entry.raw_sql : undefined,
      });
    }
  }

  return indexes;
}

function normalizeToolCallLog(value: unknown): unknown[] | null {
  if (Array.isArray(value)) {
    return value;
  }

  return null;
}

async function loadSiblingToolCallLog(filePath: string): Promise<unknown[] | null> {
  const siblingPath = path.join(path.dirname(filePath), "tool_call_log.json");

  try {
    const content = await fs.readFile(siblingPath, "utf8");
    const parsed = JSON.parse(content) as unknown;

    if (Array.isArray(parsed)) {
      return parsed;
    }

    warn(`tool_call_log.json next to ${path.basename(filePath)} was not a JSON array.`);
  } catch {
    // It is valid for the log to be absent.
  }

  return null;
}

function uniqueIndexes(indexes: IndexRecommendation[]): IndexRecommendation[] {
  const seen = new Set<string>();
  const unique: IndexRecommendation[] = [];

  for (const index of indexes) {
    const key = `${index.table}::${index.columns.join(",")}`;
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    unique.push(index);
  }

  return unique;
}

function defaultRow(): CanonicalRecommendationRow {
  return {
    query_id: "",
    recommended_indexes: [],
    llm_reasoning_text: "",
    execution_time_ms_after: "",
    improvement_vs_baseline: "",
    tool_call_log: "",
  };
}

async function readJsonOrCsv(filePath: string): Promise<{ variant: string; rows: CanonicalRecommendationRow[]; recommendation?: CanonicalRecommendationBundle["recommendation"]; warnings: string[] }> {
  const warnings: string[] = [];
  const text = await fs.readFile(filePath, "utf8");

  try {
    const parsed = JSON.parse(text) as unknown;

    if (Array.isArray(parsed)) {
      const rows = parsed.flatMap((entry) => normalizeJsonEntry(entry, warnings));
      return { variant: "json-array", rows, warnings };
    }

    if (isRecord(parsed) && Array.isArray(parsed.recommended_indexes) && typeof parsed.llm_reasoning_text === "string") {
      const indexes = normalizeRecommendedIndexes(parsed.recommended_indexes);
      const toolCallLog = normalizeToolCallLog(parsed.tool_call_log) ?? await loadSiblingToolCallLog(filePath);
      const condition = parsed.condition === "A" || parsed.condition === "B" ? parsed.condition : undefined;
      const recommendation: CanonicalRecommendationBundle["recommendation"] = {
        schema_name: typeof parsed.schema_name === "string" ? parsed.schema_name : undefined,
        condition,
        recommended_indexes: indexes,
        llm_reasoning_text: parsed.llm_reasoning_text,
        tool_call_log: toolCallLog,
      };

      return {
        variant: "json-object",
        rows: [
          {
            ...defaultRow(),
            recommended_indexes: indexes,
            llm_reasoning_text: parsed.llm_reasoning_text,
            tool_call_log: toolCallLog ? JSON.stringify(toolCallLog, null, 2) : "",
          },
        ],
        recommendation,
        warnings,
      };
    }
  } catch {
    // Continue to CSV parsing.
  }

  const rows = parseCsv(text);
  if (rows.length === 0) {
    return { variant: "csv-empty", rows: [], warnings };
  }

  const header = rows[0];
  const queryIdIndex = header.indexOf("query_id");
  const recommendedIndexesIndex = header.indexOf("recommended_indexes");
  const reasoningIndex = header.indexOf("llm_reasoning_text");
  const executionIndex = header.indexOf("execution_time_ms_after");
  const improvementIndex = header.indexOf("improvement_vs_baseline");
  const toolCallIndex = header.indexOf("tool_call_log");

  if (queryIdIndex < 0 || recommendedIndexesIndex < 0 || reasoningIndex < 0) {
    throw new Error(`Unrecognized recommendation CSV shape in ${path.basename(filePath)}.`);
  }

  const normalizedRows: CanonicalRecommendationRow[] = [];
  for (const [index, row] of rows.slice(1).entries()) {
    if (row.every((cell) => cell.trim().length === 0)) {
      continue;
    }

    const queryId = row[queryIdIndex]?.trim();
    const recommendedIndexes = parseRecommendedIndexesCell(row[recommendedIndexesIndex] ?? "");
    const reasoning = row[reasoningIndex]?.trim();
    const execution = executionIndex >= 0 ? row[executionIndex]?.trim() ?? "" : "";
    const improvement = improvementIndex >= 0 ? row[improvementIndex]?.trim() ?? "" : "";
    const toolCall = toolCallIndex >= 0 ? row[toolCallIndex]?.trim() ?? "" : "";

    if (!queryId) {
      warnings.push(`Row ${index + 2} in ${path.basename(filePath)} is missing query_id; leaving it blank.`);
    }

    if (!reasoning) {
      warnings.push(`Row ${index + 2} in ${path.basename(filePath)} is missing llm_reasoning_text; leaving it blank.`);
    }

    normalizedRows.push({
      query_id: queryId ?? "",
      recommended_indexes: recommendedIndexes,
      llm_reasoning_text: reasoning ?? "",
      execution_time_ms_after: execution,
      improvement_vs_baseline: improvement,
      tool_call_log: toolCall,
    });
  }

  const recommendation = {
    recommended_indexes: uniqueIndexes(normalizedRows.flatMap((row) => row.recommended_indexes)),
    llm_reasoning_text: normalizedRows.find((row) => row.llm_reasoning_text.trim().length > 0)?.llm_reasoning_text ?? "",
    tool_call_log: await loadSiblingToolCallLog(filePath),
  };

  return {
    variant: "csv",
    rows: normalizedRows,
    recommendation,
    warnings,
  };
}

function normalizeJsonEntry(entry: unknown, warnings: string[]): CanonicalRecommendationRow[] {
  if (!isRecord(entry)) {
    return [];
  }

  const indexes = normalizeRecommendedIndexes(entry.recommended_indexes);
  const row: CanonicalRecommendationRow = {
    query_id: typeof entry.query_id === "string" ? entry.query_id : "",
    recommended_indexes: indexes,
    llm_reasoning_text: typeof entry.llm_reasoning_text === "string" ? entry.llm_reasoning_text : "",
    execution_time_ms_after: typeof entry.execution_time_ms_after === "string" || typeof entry.execution_time_ms_after === "number"
      ? String(entry.execution_time_ms_after)
      : "",
    improvement_vs_baseline: typeof entry.improvement_vs_baseline === "string" || typeof entry.improvement_vs_baseline === "number"
      ? String(entry.improvement_vs_baseline)
      : "",
    tool_call_log: Array.isArray(entry.tool_call_log) ? JSON.stringify(entry.tool_call_log, null, 2) : "",
  };

  if (!row.query_id) {
    warnings.push("A JSON recommendation entry is missing query_id; leaving it blank.");
  }

  return [row];
}

function rowsToCsv(rows: CanonicalRecommendationRow[]): string {
  const table = [
    [
      "query_id",
      "recommended_indexes",
      "llm_reasoning_text",
      "execution_time_ms_after",
      "improvement_vs_baseline",
      "tool_call_log",
    ],
    ...rows.map((row) => [
      row.query_id,
      JSON.stringify(row.recommended_indexes),
      row.llm_reasoning_text,
      row.execution_time_ms_after,
      row.improvement_vs_baseline,
      row.tool_call_log,
    ]),
  ];

  return toCsv(table);
}

async function writeRecommendationOutputs(
  bundle: CanonicalRecommendationBundle,
  sourceModule: "condition_a" | "condition_b",
  outputPath: string,
): Promise<void> {
  const isDirectory = await pathIsDirectory(outputPath);
  const baseName = sourceModule === "condition_a" ? "condition_a" : "condition_b";
  const csvPath = isDirectory ? path.join(outputPath, `${baseName}_results.csv`) : outputPath.endsWith(".csv") ? outputPath : `${outputPath}.csv`;
  const jsonPath = isDirectory ? path.join(outputPath, `${baseName}_recommendation.json`) : outputPath.endsWith(".json") ? outputPath : `${outputPath}.json`;

  await fs.mkdir(path.dirname(csvPath), { recursive: true });
  await fs.writeFile(csvPath, rowsToCsv(bundle.rows), "utf8");

  await fs.mkdir(path.dirname(jsonPath), { recursive: true });
  await fs.writeFile(jsonPath, `${JSON.stringify(bundle.recommendation, null, 2)}\n`, "utf8");
}

async function pathIsDirectory(filePath: string): Promise<boolean> {
  try {
    const stat = await fs.stat(filePath);
    return stat.isDirectory();
  } catch {
    return filePath.endsWith(path.sep) || path.extname(filePath).length === 0;
  }
}

export async function normalizeRecommendationOutput(
  inputFilePath: string,
  sourceModule: "condition_a" | "condition_b",
  outputPath?: string,
): Promise<CanonicalRecommendationBundle> {
  const { variant, rows, recommendation, warnings } = await readJsonOrCsv(inputFilePath);
  const bundle: CanonicalRecommendationBundle = {
    sourceModule,
    detectedVariant: variant,
    rows,
    recommendation: recommendation ?? {
      recommended_indexes: uniqueIndexes(rows.flatMap((row) => row.recommended_indexes)),
      llm_reasoning_text: rows.find((row) => row.llm_reasoning_text.trim().length > 0)?.llm_reasoning_text ?? "",
      tool_call_log: null,
    },
    warnings,
  };

  if (!bundle.recommendation.recommended_indexes.length && rows.length > 0) {
    bundle.recommendation.recommended_indexes = uniqueIndexes(rows.flatMap((row) => row.recommended_indexes));
  }

  if (outputPath) {
    await writeRecommendationOutputs(bundle, sourceModule, outputPath);
  }

  return bundle;
}