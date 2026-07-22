import csv
from dotenv import load_dotenv
load_dotenv()

from prompt_builder import build_prompt
from condition_a import call_llm_no_tool

def load_workload(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))

def load_schema(path: str) -> str:
    with open(path) as f:
        return f.read()

def run(schema_path: str, workload_path: str, output_path: str):
    schema_ddl = load_schema(schema_path)
    workload_rows = load_workload(workload_path)

    prompt = build_prompt(schema_ddl, workload_rows)
    result = call_llm_no_tool(prompt)

    reasoning_by_qid = {
        r["query_id"]: r for r in result["per_query_reasoning"]
    }

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
                "; ".join(rec.get("relevant_indexes", [])),
                rec.get("reasoning", ""),
                "",
                "",
            ])

    with open(output_path.replace(".csv", "_overall_indexes.txt"), "w") as f:
        f.write("\n".join(result["overall_recommended_indexes"]))

    print(f"Wrote {output_path}")

if __name__ == "__main__":
    run("schema.sql", "workload.csv", "condition_a_results.csv")
