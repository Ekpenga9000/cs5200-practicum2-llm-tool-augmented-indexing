export function parseCsv(content: string): string[][] {
  const source = content.replace(/^\uFEFF/, "");
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = "";
  let inQuotes = false;

  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];

    if (inQuotes) {
      if (character === '"') {
        if (source[index + 1] === '"') {
          currentField += '"';
          index += 1;
        } else {
          inQuotes = false;
        }

        continue;
      }

      currentField += character;
      continue;
    }

    if (character === '"') {
      inQuotes = true;
      continue;
    }

    if (character === ",") {
      currentRow.push(currentField);
      currentField = "";
      continue;
    }

    if (character === "\r") {
      continue;
    }

    if (character === "\n") {
      currentRow.push(currentField);
      rows.push(currentRow);
      currentRow = [];
      currentField = "";
      continue;
    }

    currentField += character;
  }

  if (inQuotes) {
    throw new Error("CSV parsing failed: unterminated quoted field.");
  }

  if (currentField.length > 0 || currentRow.length > 0) {
    currentRow.push(currentField);
    rows.push(currentRow);
  }

  return rows.filter((row) => !(row.length === 1 && row[0] === "" && rows.length === 1));
}

export function escapeCsvValue(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }

  return value;
}

export function toCsv(rows: string[][]): string {
  return `${rows.map((row) => row.map(escapeCsvValue).join(",")).join("\n")}\n`;
}