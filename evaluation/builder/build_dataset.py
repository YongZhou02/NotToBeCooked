"""Build one-row-per-question JSONL from the original split golden files.

This is a deterministic migration tool. It does not generate questions or labels.
"""

import argparse
import json
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge(questions: list[dict], answers: dict, evidence: dict) -> list[dict]:
    ids = [question["id"] for question in questions]
    if (
        len(ids) != len(set(ids))
        or set(ids) != set(answers)
        or set(ids) != set(evidence)
    ):
        raise ValueError("Question, answer, and evidence IDs must match exactly")
    return [
        {
            **question,
            "reference_answer": answers[question["id"]]["reference_answer"],
            "required_facts": answers[question["id"]]["required_facts"],
            "evidence_groups": evidence[question["id"]]["groups"],
        }
        for question in questions
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = merge(
        read(args.questions),
        read(args.answers)["answers"],
        read(args.evidence)["questions"],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
