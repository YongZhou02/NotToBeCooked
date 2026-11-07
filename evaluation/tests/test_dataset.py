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
