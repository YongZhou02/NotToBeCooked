"""Offline review compiler safety and metric consistency checks."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "reports/build_review.py"
spec = importlib.util.spec_from_file_location("review_compiler", SCRIPT)
assert spec and spec.loader
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


def test_embedded_passage_cannot_close_script():
    html = compiler.render({"passage": "</script><script>alert(1)</script>"})
    assert "</script><script>alert(1)" not in html
    assert "\\u003c/script\\u003e" in html


def test_full_existing_run_recomputes_and_keeps_comparison_separate():
    import pytest

    evaluation = SCRIPT.parents[1]
    dataset = evaluation / "datasets/cpt316/topic1"
    baseline = evaluation / "runs/20261107T113258086748Z"
    comparison = evaluation / "runs/20261107T115210823381Z"
    if not baseline.exists() or not comparison.exists():
        pytest.skip("Local ignored pilot artifacts are not included in the repository")
    data = compiler.assemble(dataset, baseline, comparison)
    assert len(data["runs"][0]["retrieval"]) == 150
    assert not data["runs"][1]["retrieval"]
    before, after = [
        r["evidence_audit"]["t1-001"]["extracted_items"]["t1-001-e1"]
        for r in data["runs"]
    ]
    assert not before
    assert after
