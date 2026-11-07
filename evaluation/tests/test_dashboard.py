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
    assert len(data["runs"]) == 3
    assert len(data["questions"]) == 50
    baseline = next(run for run in data["runs"] if run["id"] == data["selected_run_id"])
    assert [phase["id"] for phase in baseline["phases"]] == [
        "extraction",
        "chunking",
        "retrieval",
        "context",
        "citation",
        "generation",
    ]
    assert baseline["same_source_run_count"] == 3
    assert baseline["retrieval_methods"]["hybrid_rrf"]["evidence_recall@5"] > 0


def test_generated_dashboard_json_is_the_ui_source():
    path = SCRIPT.parent / "dashboard_data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ui_mode"] == "prototype; no live run backend"
    assert data["fuzzy_matching"]["diagnostic_only"] is True
