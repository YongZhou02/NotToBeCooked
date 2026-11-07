"""Compile existing evaluation artifacts into one offline, auditable HTML file.

No database connections, model calls, or changes to golden labels are made.
Run from the repository root with `uv run --project apps/api python evaluation/reports/build_review.py`.
"""

import argparse
import json
import sys
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION))
from scorers.retrieval import covered_groups, retrieval_metrics


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_run(path):
    names = (
        "config",
        "checks",
        "reference_pages",
        "extracted_items",
        "chunks",
        "generation_answers",
        "assistant_reviews",
    )
    data = {
        name: read_json(path / f"{name}.json")
        for name in names
        if (path / f"{name}.json").exists()
    }
    data["id"] = path.name
    data["path"] = str(path.resolve())
    result_file = path / "results.jsonl"
    if not result_file.exists():
        result_file = path / "retrieval.jsonl"
    data["retrieval"] = (
        [
            json.loads(line)
            for line in result_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if result_file.exists()
        else []
    )
    return data


def assemble(dataset, run_path, comparison=None):
    rows = [
        json.loads(line)
        for line in (dataset / "questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    questions = [
        {
            key: row[key]
            for key in ("id", "category", "split", "generation_review", "question")
        }
        for row in rows
    ]
    answers = {
        "annotation_status": read_json(dataset / "dataset.json")["annotation_status"],
        "answers": {
            row["id"]: {
                "reference_answer": row["reference_answer"],
                "required_facts": row["required_facts"],
            }
            for row in rows
        },
    }
    evidence = {
        "annotation_status": read_json(dataset / "dataset.json")["annotation_status"],
        "questions": {row["id"]: {"groups": row["evidence_groups"]} for row in rows},
    }
    run = load_run(run_path)
    recorded_hashes = run["config"]["dataset_hashes"]
    current_names = {"dataset.json", "sources.json", "questions.jsonl"}
    if set(recorded_hashes) == current_names:
        import hashlib

        for name, expected in recorded_hashes.items():
            actual = hashlib.sha256((dataset / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"Dataset changed since run: {name}")
    else:
        legacy = read_json(dataset / "sources.json").get("legacy_dataset_hashes")
        if legacy != recorded_hashes:
            raise ValueError(
                "Run hashes match neither this dataset nor its recorded legacy migration"
            )
    seen = set()
    for row in run["retrieval"]:
        key = (row["question_id"], row["method"])
        if key in seen:
            raise ValueError(f"Duplicate retrieval record: {key}")
        seen.add(key)
        groups = evidence["questions"][row["question_id"]]["groups"]
        recomputed = retrieval_metrics(row["sources"], groups)
        if any(
            abs(value - row["metrics"][name]) > 1e-9
            for name, value in recomputed.items()
        ):
            raise ValueError(f"Saved metric disagrees with recomputation: {key}")
        row["recomputed_metrics"] = recomputed
        row["rank_evidence"] = [
            sorted(covered_groups([source], groups)) for source in row["sources"]
        ]
    runs = [run]
    if comparison:
        other = load_run(comparison)
        if other["config"]["dataset_hashes"] != run["config"]["dataset_hashes"]:
            raise ValueError("Comparison uses different golden labels")
        if other["config"]["corpus"] != run["config"]["corpus"]:
            raise ValueError("Comparison uses a different corpus/configuration")
        runs.append(other)
    for item in runs:
        item["evidence_audit"] = {}
        for question in questions:
            groups = evidence["questions"][question["id"]]["groups"]
            item["evidence_audit"][question["id"]] = {
                stage: {
                    group["id"]: [
                        i
                        for i, block in enumerate(item.get(stage, []))
                        if group["id"] in covered_groups([block], [group])
                    ]
                    for group in groups
                }
                for stage in ("reference_pages", "extracted_items", "chunks")
            }
    return {
        "questions": questions,
        "answers": answers,
        "evidence": evidence,
        "runs": runs,
        "metrics_source": "\n\n".join(
            (EVALUATION / path).read_text(encoding="utf-8")
            for path in (
                "scorers/retrieval.py",
                "scorers/pipeline.py",
                "scorers/answer_quality.py",
            )
        ),
    }


def render(data):
    # Prevent passages containing HTML/script syntax from escaping the data block.
    payload = (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    template = (Path(__file__).resolve().parent / "review_template.html").read_text(
        encoding="utf-8"
    )
    return template.replace("__EVALUATION_DATA__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=EVALUATION / "datasets/cpt316/topic1"
    )
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--compare-extraction", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = assemble(args.dataset, args.run, args.compare_extraction)
    output = (
        args.output or EVALUATION / "reports/generated" / f"{args.run.name}-review.html"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data), encoding="utf-8")
    print(f"Saved {output.resolve()}")
    print(
        f"Verified {len(data['runs'][0]['retrieval'])} saved retrieval metric records."
    )


if __name__ == "__main__":
    main()
