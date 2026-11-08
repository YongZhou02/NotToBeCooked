import csv
import json

import pytest
from builder import flat_results as flat

QUESTIONS = [
    {
        "id": "q1",
        "split": "test",
        "category": "definition",
        "origin": "synthetic",
        "answerable": True,
        "verified": True,
        "author": "original",
        "evidence_groups": [
            {"id": "q1-e1", "alternatives": [{"document_id": "d1", "pdf_page": 2}]}
        ],
    },
    {
        "id": "q2",
        "split": "stress",
        "category": "vague",
        "origin": "human",
        "answerable": True,
        "verified": False,
        "author": "ana",
        "evidence_groups": [
            {"id": "q2-e1", "alternatives": [{"document_id": "d1", "pdf_page": 5}]}
        ],
    },
    {
        "id": "q3",
        "split": "stress",
        "category": "unanswerable",
        "origin": "human",
        "answerable": False,
        "verified": True,
        "author": "ben",
        "evidence_groups": [],
    },
]
METRICS = {
    "hit@1": 1.0,
    "hit@3": 1.0,
    "hit@5": 1.0,
    "evidence_recall@5": 1.0,
    "complete_evidence@5": 1.0,
    "mrr@5": 1.0,
}
BLOCKED_TEXT = "An answer was written, but its citations could not be checked"


def result_row(question, method, metrics=None):
    return {
        "question_id": question["id"],
        "split": question["split"],
        "category": question["category"],
        "origin": question["origin"],
        "answerable": question["answerable"],
        "method": method,
        "retrieval_ms": [4.0, 6.0, 5.0],
        "sources": [
            {"document_id": "d1", "page_start": 2, "page_end": 2, "content": "x"}
        ],
        "metrics": metrics,
    }


def answer_row(question_id, text, problems=None, draft=None):
    trace = {"grounding_ok": not problems, "grounding_problems": problems or []}
    if draft:
        trace["draft"] = draft
    return {
        "question_id": question_id,
        "method": "hybrid_rrf",
        "response": {
            "answer": text,
            "citations": [] if problems else [{"marker": 1}],
        },
        "generation_ms": 2000,
        "generation_trace": trace,
    }


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def read_table(path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


@pytest.fixture
def datasets(tmp_path, monkeypatch):
    folder = tmp_path / "datasets/all"
    folder.mkdir(parents=True)
    write_jsonl(folder / "questions.jsonl", QUESTIONS)
    monkeypatch.setattr(flat, "DATASETS", tmp_path / "datasets")


def make_run(parent, generate=True, name="run1"):
    run = parent / name
    run.mkdir(parents=True)
    config = {"generation_method": "hybrid_rrf"} if generate else {}
    (run / "config.json").write_text(json.dumps(config), encoding="utf-8")
    rows = []
    for method in ("vector", "hybrid_rrf"):
        rows.append(result_row(QUESTIONS[0], method, METRICS))
        rows.append(result_row(QUESTIONS[1], method, {**METRICS, "hit@5": 0.0}))
        rows.append(result_row(QUESTIONS[2], method, None))
    write_jsonl(run / "results.jsonl", rows)
    if generate:
        shown = answer_row("q1", "It is a pass [1].")
        shown["generation_trace"]["draft"] = {
            "answer": "It is a pass [1].",
            "citations": [{"marker": 1}],
        }
        blocked = answer_row(
            "q2",
            BLOCKED_TEXT,
            ["citation [1] is listed but never referred to", "second problem"],
            draft={"answer": "no markers here", "citations": []},
        )
        (run / "generation_answers.json").write_text(
            json.dumps([shown, blocked]), encoding="utf-8"
        )
        judged = {
            "correct": 2,
            "supported": 2,
            "useful": 1,
            "refused": False,
            "method": "hybrid_rrf",
        }
        (run / "judgements.json").write_text(
            json.dumps({"answers": {"q1": judged}}), encoding="utf-8"
        )
    (run / "checks.json").write_text(
        json.dumps(
            {
                "extraction_evidence_coverage": 0.5,
                "missing_after_extraction": ["q2-e1"],
                "not_intact_in_any_chunk": ["q2-e1"],
            }
        ),
        encoding="utf-8",
    )
    return run


def by_key(rows):
    return {(r["question_id"], r["pipeline"]): r for r in rows}


def test_columns_start_with_the_shared_contract_in_order(tmp_path, datasets):
    header, _ = read_table(flat.build_run(make_run(tmp_path)))
    assert header[:11] == [
        "run_id",
        "pipeline",
        "chunks_version",
        "question_id",
        "split",
        "category",
        "origin",
        "answerable",
        "verified",
        "is_hard_case",
        "author",
    ]
    assert header[11:17] == [
        "retrieval.hit@1",
        "retrieval.hit@3",
        "retrieval.hit@5",
        "retrieval.evidence_recall@5",
        "retrieval.complete_evidence@5",
        "retrieval.mrr@5",
    ]
    assert header[: len(flat.FIXED_COLUMNS)] == flat.FIXED_COLUMNS


def test_one_row_per_question_per_method(tmp_path, datasets):
    _, rows = read_table(flat.build_run(make_run(tmp_path)))
    assert len(rows) == 6
    assert {(r["question_id"], r["pipeline"]) for r in rows} == {
        (q, f"run_eval:{m}")
        for q in ("q1", "q2", "q3")
        for m in ("vector", "hybrid_rrf")
    }
    assert {r["chunks_version"] for r in rows} == {"run-local"}


def test_answer_and_judge_columns_only_on_the_generated_method(tmp_path, datasets):
    _, rows = read_table(flat.build_run(make_run(tmp_path)))
    table = by_key(rows)
    vector = table[("q1", "run_eval:vector")]
    for column in (
        "answer.state",
        "answer.shown",
        "answer.block_reason",
        "answer.n_citations",
        "answer.draft_has_markers",
        "judge.correct",
    ):
        assert vector[column] == ""
    shown = table[("q1", "run_eval:hybrid_rrf")]
    assert shown["answer.state"] == "shown"
    assert shown["answer.shown"] == "1"
    assert shown["answer.n_citations"] == "1"
    assert shown["answer.draft_has_markers"] == "1"
    assert shown["judge.correct"] == "2"
    assert shown["judge.useful"] == "1"


def test_blocked_answer_keeps_reasons_and_draft_marker_check(tmp_path, datasets):
    _, rows = read_table(flat.build_run(make_run(tmp_path)))
    blocked = by_key(rows)[("q2", "run_eval:hybrid_rrf")]
    assert blocked["answer.state"] == "blocked"
    assert blocked["answer.shown"] == "0"
    assert blocked["answer.block_reason"] == (
        "citation [1] is listed but never referred to | second problem"
    )
    assert blocked["answer.draft_has_markers"] == "0"
    # Generated but not judged: the judge cells are empty, not 0.
    assert blocked["judge.correct"] == ""


def test_missing_data_is_empty_never_zero(tmp_path, datasets):
    _, rows = read_table(flat.build_run(make_run(tmp_path)))
    unanswerable = by_key(rows)[("q3", "run_eval:hybrid_rrf")]
    assert unanswerable["retrieval.hit@5"] == ""
    assert unanswerable["retrieval.mrr@5"] == ""
    assert unanswerable["pipeline.extraction"] == ""  # no evidence to extract
    assert unanswerable["retrieval.ms"] == "5.0"  # timing exists without metrics
    assert unanswerable["answerable"] == "0"
    assert unanswerable["is_hard_case"] == ""  # field absent from the questions


def test_run_without_generation_or_checks_leaves_columns_empty(tmp_path, datasets):
    run = make_run(tmp_path, generate=False)
    (run / "checks.json").unlink()
    header, rows = read_table(flat.build_run(run))
    assert len(rows) == 6
    for row in rows:
        for column in flat.STEP_COLUMNS:
            if column.startswith(("answer.", "judge.", "pipeline.")):
                assert row[column] == ""
    assert all(not column.startswith("concern.") for column in header)


def test_run_with_no_results_writes_a_header_only_file(tmp_path, datasets):
    run = tmp_path / "empty"
    run.mkdir()
    (run / "config.json").write_text("{}", encoding="utf-8")
    header, rows = read_table(flat.build_run(run))
    assert header == flat.FIXED_COLUMNS
    assert rows == []


def test_pipeline_columns_are_the_share_of_evidence_kept(tmp_path, datasets):
    _, rows = read_table(flat.build_run(make_run(tmp_path)))
    table = by_key(rows)
    assert table[("q1", "run_eval:vector")]["pipeline.extraction"] == "1.0"
    assert table[("q2", "run_eval:vector")]["pipeline.extraction"] == "0.0"
    assert table[("q2", "run_eval:vector")]["pipeline.chunking"] == "0.0"


def test_concern_columns_follow_concerns_json_and_are_sorted(tmp_path, datasets):
    run = make_run(tmp_path)
    items = [
        {"id": "slow_answers", "status": "measured"},
        {"id": "blocked_answers", "status": "measured"},
        {"id": "wrong_answers", "status": "not_measured"},
    ]
    (run / "concerns.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    header, rows = read_table(flat.build_run(run))
    assert header[len(flat.FIXED_COLUMNS) :] == [
        "concern.blocked_answers",
        "concern.slow_answers",
    ]
    table = by_key(rows)
    assert table[("q1", "run_eval:hybrid_rrf")]["concern.blocked_answers"] == "0"
    assert table[("q2", "run_eval:hybrid_rrf")]["concern.blocked_answers"] == "1"
    assert table[("q1", "run_eval:vector")]["concern.blocked_answers"] == ""


def test_all_combines_runs_with_one_stable_header(tmp_path, datasets):
    runs = tmp_path / "runs"
    first = make_run(runs, name="a")
    make_run(runs, generate=False, name="b")
    (first / "concerns.json").write_text(
        json.dumps({"items": [{"id": "blocked_answers", "status": "measured"}]}),
        encoding="utf-8",
    )
    combined = flat.build_all(runs, tmp_path / "reports/results_flat.csv")
    header, rows = read_table(combined)
    assert header == [*flat.FIXED_COLUMNS, "concern.blocked_answers"]
    assert len(rows) == 12
    assert {r["run_id"] for r in rows} == {"a", "b"}
    assert (runs / "a" / flat.FILE_NAME).exists()
    assert (runs / "b" / flat.FILE_NAME).exists()
    # Run b has no concerns.json, so its concern cells are empty, not 0.
    assert {r["concern.blocked_answers"] for r in rows if r["run_id"] == "b"} == {""}
