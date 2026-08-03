import csv
from dotenv import load_dotenv
load_dotenv()

from prompt_builder import build_prompt
from condition_a import call_llm_no_tool

BATCH_SIZE = 15  # queries per LLM call -- small enough to avoid truncation


def load_workload(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def load_schema(path: str) -> str:
    with open(path) as f:
        return f.read()


def chunk(rows: list, size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def run(schema_path: str, workload_path: str, output_path: str):
    schema_ddl = load_schema(schema_path)
    workload_rows = load_workload(workload_path)

    all_overall_indexes = set()
    reasoning_by_qid = {}
    all_rejected = []

    batches = list(chunk(workload_rows, BATCH_SIZE))
    print(f"Processing {len(workload_rows)} queries in {len(batches)} batch(es) "
          f"of up to {BATCH_SIZE} queries each...")

    for batch_num, batch_rows in enumerate(batches, start=1):
        print(f"\n[Batch {batch_num}/{len(batches)}] "
              f"queries: {[r['query_id'] for r in batch_rows]}")

        prompt = build_prompt(schema_ddl, batch_rows)
        result = call_llm_no_tool(prompt, schema_ddl)

        all_overall_indexes.update(result.get("recommended_indexes", []))
        all_rejected.extend(result.get("rejected_indexes", []))

        for entry in result["per_query_reasoning"]:
            reasoning_by_qid[entry["query_id"]] = entry
            all_rejected.extend(entry.get("rejected_indexes", []))

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "query_id", "recommended_indexes", "llm_reasoning_text",
            "execution_time_ms_after", "improvement_vs_baseline"
        ])
        for row in workload_rows:
            qid = row["query_id"]
            rec = reasoning_by_qid.get(qid, {})
            writer.writerow([
                qid,
                "; ".join(rec.get("recommended_indexes", [])),
                rec.get("reasoning", ""),
                "",
                "",
            ])

    with open(output_path.replace(".csv", "_overall_indexes.txt"), "w") as f:
        f.write("\n".join(sorted(all_overall_indexes)))

    if all_rejected:
        with open(output_path.replace(".csv", "_rejected_indexes.txt"), "w") as f:
            f.write("\n".join(all_rejected))
        print(f"\n{len(all_rejected)} index(es) were rejected as hallucinated "
              f"-- see {output_path.replace('.csv', '_rejected_indexes.txt')}")

    print(f"\nWrote {output_path}")
    print(f"Total unique recommended indexes: {len(all_overall_indexes)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python run_condition_a.py <schema.sql> <workload.csv> <output.csv>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3])