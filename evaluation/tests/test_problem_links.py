"""problems.md and experiments.md point at each other. A tested fix must name
an experiment that exists, and an experiment must link to problems that exist,
so a claim in either file can always be traced to its evidence."""

import re
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
PROBLEMS = (EVALUATION / "problems.md").read_text(encoding="utf-8")
EXPERIMENTS = (EVALUATION / "experiments.md").read_text(encoding="utf-8")

experiment_ids = set(re.findall(r"^### (E\d+)\.", EXPERIMENTS, re.M))
problem_ids = {p.upper() for p in re.findall(r'<a id="(p\d+)"></a>', PROBLEMS)}


def numbered(ids: set[str]) -> list[int]:
    return sorted(int(i[1:]) for i in ids)


def test_ids_are_unique_and_have_no_gaps():
    for ids, text, pattern in (
        (experiment_ids, EXPERIMENTS, r"^### (E\d+)\."),
        (problem_ids, PROBLEMS, r'<a id="(p\d+)"></a>'),
    ):
        found = re.findall(pattern, text, re.M)
        assert len(found) == len(set(found)), f"repeated id in {found}"
        assert numbered(ids) == list(range(1, len(ids) + 1))


def test_every_experiment_named_in_problems_exists():
    named = set(re.findall(r"\bE\d+\b", PROBLEMS))
    assert named - experiment_ids == set()


def test_every_problem_linked_from_experiments_exists():
    linked = {p.upper() for p in re.findall(r"problems\.md#(p\d+)", EXPERIMENTS)}
    assert linked - problem_ids == set()


def test_summary_lists_every_problem():
    summary = {p.upper() for p in re.findall(r"^\| \[(P\d+)\]\(#p\d+\)", PROBLEMS, re.M)}
    assert summary == problem_ids
