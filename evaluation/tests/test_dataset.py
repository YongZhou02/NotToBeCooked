import json
from pathlib import Path

from builder.build_dataset import merge


def test_one_row_contains_question_answer_and_evidence():
    rows = merge(
        [{"id": "q1", "question": "Q?", "split": "test"}],
        {"q1": {"reference_answer": "A", "required_facts": ["A"]}},
        {"q1": {"groups": [{"id": "e1", "alternatives": []}]}},
    )
    assert rows[0]["question"] == "Q?"
    assert rows[0]["reference_answer"] == "A"
    assert rows[0]["evidence_groups"][0]["id"] == "e1"


def test_committed_topic1_dataset_has_fifty_complete_rows():
    path = (
        Path(__file__).resolve().parents[1] / "datasets/cpt316/topic1/questions.jsonl"
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 50
    assert len({row["id"] for row in rows}) == 50
    assert all(row["reference_answer"] and row["evidence_groups"] for row in rows)
    assert all(row["verified"] for row in rows)
    assert sum(
        row["label_review"]["strict_retrieval_eligible"] for row in rows
    ) == 49
    assert next(row for row in rows if row["id"] == "t1-027")["label_review"][
        "status"
    ] == "verified_excluded_from_strict"


def test_topic1_revisions_remove_unsupported_gold_claims():
    path = (
        Path(__file__).resolve().parents[1] / "datasets/cpt316/topic1/questions.jsonl"
    )
    rows = {
        row["id"]: row
        for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())
    }
    assert "universal" not in rows["t1-023"]["reference_answer"].lower()
    assert len(rows["t1-048"]["evidence_groups"]) == 1
    assert rows["t1-025"]["evidence_groups"][0]["alternatives"][0][
        "pdf_page"
    ] == 23
