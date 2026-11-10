import json

import pytest
from compare_rewrite import compare


def test_comparison_uses_adopted_sources_and_does_not_invent_correctness(tmp_path):
    before, after, dataset = [
        tmp_path / name for name in ("before", "after", "dataset")
    ]
    for folder in (before, after, dataset):
        folder.mkdir()
    label = {
        "id": "q",
        "question": "Question",
        "answerable": True,
        "reference_answer": "Gold",
        "required_facts": ["Gold"],
        "evidence_groups": [
            {
                "id": "e",
                "alternatives": [
                    {"document_id": "doc", "pdf_page": 9, "quote": "Gold"}
                ],
            }
        ],
    }
    (dataset / "questions.jsonl").write_text(json.dumps(label), encoding="utf-8")
    wrong = {"document_id": "doc", "page_start": 1, "page_end": 1, "content": "Other"}
    right = {"document_id": "doc", "page_start": 9, "page_end": 9, "content": "Gold"}
    for folder, enabled in ((before, False), (after, True)):
        (folder / "config.json").write_text(
            json.dumps({"query_rewrite_enabled": enabled}), encoding="utf-8"
        )
        row = {
            "question_id": "q",
            "generation_ms": 100,
            "sources": [wrong],
            "response": {"grounded": enabled, "answer": "Gold"},
            "scope_snapshots": [
                {"query_rewrite": {"attempted": enabled, "accepted": enabled}}
            ],
            "generation_trace": {"retry_sources": [right]},
        }
        (folder / "generation_answers.json").write_text(
            json.dumps([row]), encoding="utf-8"
        )
    result = compare(before, after, dataset)
    assert result["summary"]["before"]["answerable_evidence_recall@5"] == 0
    assert result["summary"]["after"]["answerable_evidence_recall@5"] == 1
    assert result["questions"][0]["review"]["after_correctness_0_to_2"] is None
    # Retest only transport failures; never replace an inconvenient answer.
    supplement = tmp_path / "supplement"
    supplement.mkdir()
    baseline_config = (before / "config.json").read_text(encoding="utf-8")
    (supplement / "config.json").write_text(baseline_config, encoding="utf-8")
    baseline_rows = json.loads(
        (before / "generation_answers.json").read_text(encoding="utf-8")
    )
    (supplement / "generation_answers.json").write_text(
        json.dumps(baseline_rows), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="only baseline provider failures"):
        compare(before, after, dataset, supplement)
    baseline_rows[0]["generation_trace"]["generation_error"] = "429"
    (before / "generation_answers.json").write_text(
        json.dumps(baseline_rows), encoding="utf-8"
    )
    assert (
        compare(before, after, dataset, supplement)["summary"]["before"][
            "generation_errors"
        ]
        == 0
    )
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (prefix / "config.json").write_text(
        (after / "config.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (prefix / "generation_answers.json").write_text(
        (after / "generation_answers.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="disjoint"):
        compare(before, after, dataset, supplement, prefix)
    (after / "generation_answers.json").write_text("[]", encoding="utf-8")
    assert (
        compare(before, after, dataset, supplement, prefix)["summary"]["questions"] == 1
    )
    (after / "config.json").write_text(
        json.dumps({"query_rewrite_enabled": True, "generation_model": "different"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="generation_model"):
        compare(before, after, dataset)


def test_legacy_labels_default_to_answerable(tmp_path):
    before, after, dataset = [
        tmp_path / name for name in ("before", "after", "dataset")
    ]
    for folder in (before, after, dataset):
        folder.mkdir()
    label = {
        "id": "q",
        "question": "Question",
        "reference_answer": "Gold",
        "required_facts": ["Gold"],
        "evidence_groups": [
            {
                "id": "e",
                "alternatives": [
                    {"document_id": "doc", "pdf_page": 1, "quote": "Gold"}
                ],
            }
        ],
    }
    (dataset / "questions.jsonl").write_text(json.dumps(label), encoding="utf-8")
    for folder, enabled in ((before, False), (after, True)):
        (folder / "config.json").write_text(
            json.dumps({"query_rewrite_enabled": enabled}), encoding="utf-8"
        )
        row = {
            "question_id": "q",
            "generation_ms": 100,
            "sources": [
                {
                    "document_id": "doc",
                    "page_start": 1,
                    "page_end": 1,
                    "content": "Gold",
                }
            ],
            "response": {"grounded": False, "answer": "Gold"},
            "scope_snapshots": [],
            "generation_trace": {},
        }
        (folder / "generation_answers.json").write_text(
            json.dumps([row]), encoding="utf-8"
        )
    assert compare(before, after, dataset)["summary"]["answerable"] == 1
