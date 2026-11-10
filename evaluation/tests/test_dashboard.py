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


def test_dashboard_assembly_keeps_six_phases_and_history():
    evaluation = SCRIPT.parents[1]
    data = builder.assemble(
        evaluation / "datasets/cpt316/topic1",
        evaluation / "runs",
    )
    assert len(data["runs"]) >= 3
    assert len(data["questions"]) == 50
    assert data["dataset"]["verified_questions"] == 50
    assert data["dataset"]["strict_retrieval_questions"] == 49
    baseline = next(run for run in data["runs"] if run["id"] == data["selected_run_id"])
    assert [phase["id"] for phase in baseline["phases"]] == [
        "extraction",
        "chunking",
        "retrieval",
        "context",
        "citation",
        "generation",
    ]
    assert baseline["same_source_run_count"] == sum(
        run["source_fingerprint"] == baseline["source_fingerprint"]
        for run in data["runs"]
    )
    assert any(
        (run.get("retrieval_methods", {}).get("hybrid_rrf") or {}).get(
            "evidence_recall@5", 0
        ) > 0
        for run in data["runs"]
    )
    assert "splits" in data["dataset"]
    assert data["dataset"]["splits"]["dev"]["questions"] == 15
    assert data["dataset"]["splits"]["test"]["questions"] == 35
    assert data["dataset"]["splits"]["dev"]["golden_quotes"] == 21
    assert data["dataset"]["splits"]["test"]["golden_quotes"] == 51
    assert "origin" in data["questions"][0]
    assert "verified" in data["questions"][0]
    assert "evidence_groups" in data["questions"][0]


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
