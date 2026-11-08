import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "dashboard/build_dashboard_data.py"
spec = importlib.util.spec_from_file_location("dashboard_builder", SCRIPT)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_partial_similarity_is_exact_or_conservative():
    assert builder.partial_similarity("source -> target", "source -> target") == 1
    assert builder.partial_similarity("source -> target", "target -> source") < 0.88
    assert builder.partial_similarity("", "anything") == 0


def make_run(runs, name, sha, rows=(), concerns=None):
    """A tiny run folder, so the tests do not depend on local (gitignored) runs."""
    folder = runs / name
    folder.mkdir(parents=True)
    config = {"corpus": {"documents": [{"id": "topic1", "sha256": sha}]}}
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    if rows:
        (folder / "results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows) + "{half a line",
            encoding="utf-8",
        )
    if concerns:
        (folder / "concerns.json").write_text(json.dumps(concerns), encoding="utf-8")
    return folder


def result(question_id, split="test", metrics=True):
    metrics_value = (
        {
            "hit@1": 1.0,
            "hit@3": 1.0,
            "hit@5": 1.0,
            "evidence_recall@5": 1.0,
            "complete_evidence@5": 1.0,
            "mrr@5": 1.0,
        }
        if metrics
        else None
    )
    return {
        "question_id": question_id,
        "method": "hybrid_rrf",
        "split": split,
        "retrieval_ms": [1.0],
        "sources": [],
        "metrics": metrics_value,
    }


def test_dashboard_assembly_keeps_six_phases_and_history(tmp_path):
    evaluation = SCRIPT.parents[1]
    runs = tmp_path / "runs"
    make_run(runs, "20260101T000000Z", "same")
    make_run(runs, "20260102T000000Z", "same", rows=[result("t1-004")])
    make_run(runs, "20260103T000000Z", "other")
    data = builder.assemble(evaluation / "datasets/cpt316/topic1", runs)
    assert [run["id"] for run in data["runs"]] == [
        "20260103T000000Z",
        "20260102T000000Z",
        "20260101T000000Z",
    ]
    assert len(data["questions"]) == 50
    assert data["dataset"]["verified_questions"] == 50
    assert data["dataset"]["strict_retrieval_questions"] == 49
    baseline = next(run for run in data["runs"] if run["id"] == "20260102T000000Z")
    assert [phase["id"] for phase in baseline["phases"]] == [
        "extraction",
        "chunking",
        "retrieval",
        "context",
        "citation",
        "generation",
    ]
    assert baseline["same_source_run_count"] == 2
    assert data["runs"][0]["same_source_run_count"] == 1
    assert baseline["retrieval_methods"]["hybrid_rrf"]["evidence_recall@5"] > 0
    assert "concerns" not in data
    assert data["dataset"]["splits"]["dev"]["questions"] == 15
    assert data["dataset"]["splits"]["test"]["questions"] == 35
    assert data["dataset"]["splits"]["dev"]["golden_quotes"] == 21
    assert data["dataset"]["splits"]["test"]["golden_quotes"] == 51
    assert "origin" in data["questions"][0]
    assert "verified" in data["questions"][0]
    assert "evidence_groups" in data["questions"][0]


def test_dashboard_default_dataset_lists_four_documents_and_new_rows(tmp_path):
    evaluation = SCRIPT.parents[1]
    dataset = evaluation / "datasets/cpt316/all"
    rows = builder.read_jsonl(dataset / "questions.jsonl")
    assert any(not row.get("answerable", True) for row in rows)
    unanswerable = next(row for row in rows if not row.get("answerable", True))
    stress = next(row for row in rows if row["split"] == "stress")
    runs = tmp_path / "runs"
    make_run(
        runs,
        "20260101T000000Z",
        "x",
        rows=[
            result(unanswerable["id"], split="stress", metrics=False),
            result(stress["id"], split="stress"),
            result("t1-004"),
        ],
    )
    data = builder.assemble(dataset, runs)
    assert len(data["questions"]) == len(rows)
    documents = data["dataset"]["documents"]
    assert len(documents) == 4
    assert all(doc["id"] and doc["path"] for doc in documents)
    assert data["dataset"]["splits"]["stress"]["questions"] > 0
    trace = next(q for q in data["questions"] if q["id"] == unanswerable["id"])
    assert trace["answerable"] is False
    assert trace["traces"]["20260101T000000Z"]["context"]["metrics"] is None
    assert builder.assemble(dataset, tmp_path / "no_runs")["runs"] == []


def test_dashboard_carries_concerns_from_newest_run_that_has_them(tmp_path):
    evaluation = SCRIPT.parents[1]
    runs = tmp_path / "runs"
    make_run(runs, "20260101T000000Z", "a", concerns={"run_id": "old", "items": []})
    make_run(runs, "20260102T000000Z", "a", concerns={"run_id": "new", "items": []})
    make_run(runs, "20260103T000000Z", "a")
    data = builder.assemble(evaluation / "datasets/cpt316/topic1", runs)
    assert data["concerns"]["run_id"] == "new"


def test_generated_dashboard_json_is_the_ui_source():
    path = SCRIPT.parent / "dashboard_data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ui_mode"] == "prototype; no live run backend"
    assert data["fuzzy_matching"]["diagnostic_only"] is True


def test_dashboard_ui_html_has_three_tabs_and_required_panels():
    html_path = SCRIPT.parent / "index.html"
    content = html_path.read_text(encoding="utf-8")
    assert 'data-tab="dashboard"' in content
    assert 'data-tab="runs"' in content
    assert 'data-tab="visualization"' in content
    assert 'data-panel="dashboard"' in content
    assert 'data-panel="runs"' in content
    assert 'data-panel="visualization"' in content
    assert 'id="runDatasetStats"' in content
    assert 'id="visDatasetStats"' in content
    assert 'id="btnToggleAddQuestion"' in content
    assert 'id="filterVerification"' in content
