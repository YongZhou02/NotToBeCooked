"""Compile existing evaluation artifacts into one offline, auditable HTML file.

No database connections, model calls, or changes to golden labels are made.
Run from apps/api: uv run python scripts/compile_evaluation_review.py --help
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.evaluation.metrics import covered_groups, retrieval_metrics  # noqa: E402


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
        name: read_json(path / f"{name}.json") for name in names if (path / f"{name}.json").exists()
    }
    data["id"] = path.name
    data["path"] = str(path.resolve())
    data["retrieval"] = (
        [
            json.loads(line)
            for line in (path / "retrieval.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if (path / "retrieval.jsonl").exists()
        else []
    )
    return data


def assemble(dataset, run_path, comparison=None):
    questions = read_json(dataset / "golden/questions.json")
    answers = read_json(dataset / "golden/answer_key.json")
    evidence = read_json(dataset / "golden/evidence_key.json")
    run = load_run(run_path)
    for name, expected in run["config"]["dataset_hashes"].items():
        actual = hashlib.sha256((dataset / "golden" / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Golden dataset changed since run: {name}")
    seen = set()
    for row in run["retrieval"]:
        key = (row["question_id"], row["method"])
        if key in seen:
            raise ValueError(f"Duplicate retrieval record: {key}")
        seen.add(key)
        groups = evidence["questions"][row["question_id"]]["groups"]
        recomputed = retrieval_metrics(row["sources"], groups)
        if any(abs(value - row["metrics"][name]) > 1e-9 for name, value in recomputed.items()):
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
        "metrics_source": (
            Path(__file__).resolve().parents[1] / "app/evaluation/metrics.py"
        ).read_text(encoding="utf-8"),
    }


def render(data):
    # Prevent passages containing HTML/script syntax from escaping the data block.
    payload = (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    template = (
        Path(__file__).resolve().parents[1] / "app/evaluation/review_template.html"
    ).read_text(encoding="utf-8")
    return template.replace("__EVALUATION_DATA__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[3] / "evaluation"
    parser.add_argument("--dataset", type=Path, default=root)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--compare-extraction", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = assemble(args.dataset, args.run, args.compare_extraction)
    output = args.output or args.run / "review.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data), encoding="utf-8")
    print(f"Saved {output.resolve()}")
    print(f"Verified {len(data['runs'][0]['retrieval'])} saved retrieval metric records.")


if __name__ == "__main__":
    main()
