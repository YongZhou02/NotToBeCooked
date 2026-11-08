"""Write one flat table per run: one row per question per retrieval method.

The evaluation harness spreads one question's results over several files
(results.jsonl, generation_answers.json, judgements.json, checks.json ...).
This joins them into `results_flat.csv` so a run, or many runs, can be opened in
pandas or Excel without knowing the file layout.

An empty cell always means "not measured". It is never written as 0.

Run from the repository root:
uv run --project apps/api python evaluation/builder/flat_results.py --run RUN_DIR
uv run --project apps/api python evaluation/builder/flat_results.py --all
"""

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

EVALUATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION))

from scorers.concerns import (
    LONG_WAIT_MS,
    answer_records,
    answer_state,
    draft_of,
    gold_docs,
    has_marker,
    is_refusal,
)

DATASETS = EVALUATION / "datasets/cpt316"
RUNS = EVALUATION / "runs"
COMBINED = EVALUATION / "reports/results_flat.csv"
FILE_NAME = "results_flat.csv"
CHUNKS_VERSION = "run-local"
RETRIEVAL_METRICS = (
    "hit@1",
    "hit@3",
    "hit@5",
    "evidence_recall@5",
    "complete_evidence@5",
    "mrr@5",
)

# Shared with evaluation/playground: do not rename, reorder or remove these.
ID_COLUMNS = [
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
STEP_COLUMNS = [
    *(f"retrieval.{name}" for name in RETRIEVAL_METRICS),
    "retrieval.ms",
    "pipeline.extraction",
    "pipeline.chunking",
    "answer.state",
    "answer.shown",
    "answer.block_reason",
    "answer.n_citations",
    "answer.draft_has_markers",
    "judge.correct",
    "judge.supported",
    "judge.useful",
]
FIXED_COLUMNS = ID_COLUMNS + STEP_COLUMNS

# concerns.json only holds run-level items (examples are capped at three), so a
# per-question flag is worked out here with the same rule the concern uses.
CONCERN_IDS = (
    "blocked_answers",
    "wrong_answers",
    "mechanical_answers",
    "unanswerable",
    "weak_citations",
    "slow_answers",
    "wrong_document",
)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # a run still being written can end on a half line
    return rows


def flag(value: bool | None) -> int | None:
    """1/0 for a yes/no answer, None (an empty cell) for "not measured"."""
    return None if value is None else int(bool(value))


# ---------- questions ----------


def load_questions(run: Path, config: dict) -> dict[str, dict]:
    """The run does not store its questions, so find the dataset with its hash.

    Old runs used a questions file that no longer exists; for those, fall back to
    every current question file, newest bundle ("all") first, so a question id
    still gets its verified/author fields.
    """
    wanted = (config.get("dataset_hashes") or {}).get("questions.jsonl")
    folders = [DATASETS / name for name in ("all", "topic1", "topic1_stress")]
    merged: dict[str, dict] = {}
    for folder in folders:
        path = folder / "questions.jsonl"
        if not path.exists():
            continue
        if wanted and hashlib.sha256(path.read_bytes()).hexdigest() == wanted:
            return {row["id"]: row for row in read_jsonl(path)}
        for row in read_jsonl(path):
            merged.setdefault(row["id"], row)
    return merged


def question_meta(row: dict, question: dict | None) -> dict[str, Any]:
    """Split/category/origin/answerable as the run saw them; the rest from the question."""
    question = question or {}

    def pick(key: str, default: Any = None) -> Any:
        return row.get(key, question.get(key, default))

    return {
        "question_id": row["question_id"],
        "split": pick("split"),
        "category": pick("category"),
        "origin": pick("origin"),
        "answerable": flag(pick("answerable", True)),
        "verified": flag(question["verified"]) if "verified" in question else None,
        "is_hard_case": (
            flag(question["is_hard_case"]) if "is_hard_case" in question else None
        ),
        "author": question.get("author"),
    }


# ---------- one table cell group at a time ----------


def retrieval_cells(row: dict) -> dict[str, Any]:
    """Unanswerable questions have no metrics: leave the cells empty."""
    metrics = row.get("metrics") or {}
    timings = row.get("retrieval_ms") or []
    cells: dict[str, Any] = {
        f"retrieval.{name}": metrics.get(name) for name in RETRIEVAL_METRICS
    }
    cells["retrieval.ms"] = statistics.median(timings) if timings else None
    return cells


def pipeline_cells(question: dict | None, checks: dict | None) -> dict[str, Any]:
    """Share of the question's evidence groups that survived extraction / chunking.

    Matches question_scores in dashboard/build_dashboard_data.py, which counts a
    group as kept when any page (extraction) or chunk (chunking) holds its quote.
    """
    groups = [group["id"] for group in (question or {}).get("evidence_groups", [])]
    if not groups or not checks or "extraction_evidence_coverage" not in checks:
        return {"pipeline.extraction": None, "pipeline.chunking": None}
    lost_in_extraction = set(checks.get("missing_after_extraction", []))
    lost_in_chunks = set(checks.get("not_intact_in_any_chunk", []))
    return {
        "pipeline.extraction": 1 - len(lost_in_extraction & set(groups)) / len(groups),
        "pipeline.chunking": 1 - len(lost_in_chunks & set(groups)) / len(groups),
    }


def block_reason(answer: dict) -> str:
    """Why the student did not see the draft: grounding problems, else the model error."""
    trace = answer.get("generation_trace") or {}
    problems = trace.get("grounding_problems") or []
    if problems:
        return " | ".join(problems)
    lines = str(trace.get("generation_error") or "").strip().splitlines()
    return lines[0] if lines else ""


def answer_cells(answer: dict | None) -> dict[str, Any]:
    empty = {
        "answer.state": None,
        "answer.shown": None,
        "answer.block_reason": None,
        "answer.n_citations": None,
        "answer.draft_has_markers": None,
    }
    if not answer:
        return empty
    state = answer_state(answer)
    draft = draft_of(answer)
    citations = (answer.get("response") or {}).get("citations") or []
    return {
        "answer.state": state,
        "answer.shown": flag(state == "shown"),
        "answer.block_reason": block_reason(answer) if state != "shown" else "",
        "answer.n_citations": len(citations),
        "answer.draft_has_markers": (
            flag(has_marker(draft.get("answer", ""))) if draft else None
        ),
    }


def judge_cells(judgement: dict | None) -> dict[str, Any]:
    keys = ("correct", "supported", "useful")
    return {f"judge.{key}": (judgement or {}).get(key) for key in keys}


# ---------- concern flags ----------


def off_gold_citation(record: dict) -> bool | None:
    """True when any citation points at a page that holds no gold evidence."""
    if not record["answerable"] or not record["gold_pages"] or not record["cited"]:
        return None
    return any(
        not c["pages"]
        or not any(
            doc == c["document_id"] and c["pages"][0] <= page <= c["pages"][1]
            for doc, page in record["gold_pages"]
        )
        for c in record["cited"]
    )


def mishandled_unknown(record: dict) -> bool | None:
    """An unanswerable question answered anyway, or an answerable one refused."""
    if record["answerable"]:
        return is_refusal(record)
    if record["judgement"]:
        return not (record["state"] == "shown" and record["judgement"]["correct"] == 2)
    return not (record["state"] == "shown" and bool(is_refusal(record)))


def answer_concerns(record: dict) -> dict[str, bool | None]:
    """Per-answer version of each answer-based concern in scorers/concerns.py."""
    judgement = record["judgement"]
    return {
        "blocked_answers": record["state"] == "blocked",
        "wrong_answers": (
            judgement["correct"] < 2 if judgement and record["answerable"] else None
        ),
        "mechanical_answers": (
            judgement["useful"] < 2 if judgement and record["draft"] else None
        ),
        "unanswerable": mishandled_unknown(record),
        "weak_citations": off_gold_citation(record),
        "slow_answers": (
            record["ms"] > LONG_WAIT_MS if record["ms"] is not None else None
        ),
    }


def wrong_document(row: dict, question: dict | None) -> bool | None:
    """Hybrid rank 1 came from a PDF that holds no gold evidence for the question."""
    gold = gold_docs(question)
    if row["method"] != "hybrid_rrf" or not gold or not row.get("sources"):
        return None
    return row["sources"][0]["document_id"] not in gold


def concern_cells(
    concerns: dict | None, flags: dict[str, bool | None]
) -> dict[str, Any]:
    """`concern.<id>`: 1 the question shows the problem, 0 it does not, empty not measured.

    Only concerns that this run's concerns.json measured (fully or partly) get a
    column, so a run without concerns.json carries none.
    """
    measured = {
        entry["id"]
        for entry in (concerns or {}).get("items", [])
        if entry.get("status") != "not_measured"
    }
    return {
        f"concern.{name}": flag(flags.get(name))
        for name in CONCERN_IDS
        if name in measured
    }


# ---------- one run ----------


def generated_answers(run: Path, rows: list[dict], config: dict) -> dict[tuple, dict]:
    """Answers keyed by (question_id, method); generation_answers.json first."""
    items = read_json(run / "generation_answers.json", []) or [
        row for row in rows if "response" in row
    ]
    default_method = config.get("generation_method")
    return {
        (item["question_id"], item.get("method") or default_method): item
        for item in items
    }


def run_rows(run: Path) -> list[dict[str, Any]]:
    """Flat rows for one run folder; empty when the run has no retrieval results."""
    config = read_json(run / "config.json", {}) or {}
    rows = read_jsonl(run / "results.jsonl") or read_jsonl(run / "retrieval.jsonl")
    if not rows:
        return []
    questions = load_questions(run, config)
    checks = read_json(run / "checks.json")
    concerns = read_json(run / "concerns.json")
    judgements = (read_json(run / "judgements.json", {}) or {}).get("answers", {})
    answers = generated_answers(run, rows, config)
    records = {
        key: answer_records(questions, [{**answer, "method": key[1]}], judgements)[0]
        for key, answer in answers.items()
        if "response" in answer
    }
    output = []
    for row in rows:
        question = questions.get(row["question_id"])
        key = (row["question_id"], row["method"])
        answer = answers.get(key)
        judgement = judgements.get(row["question_id"])
        if judgement and judgement.get("method", row["method"]) != row["method"]:
            judgement = None  # the judge graded a different method's answer
        flags = dict(answer_concerns(records[key])) if key in records else {}
        flags["wrong_document"] = wrong_document(row, question)
        output.append(
            {
                "run_id": run.name,
                "pipeline": f"run_eval:{row['method']}",
                "chunks_version": CHUNKS_VERSION,
                **question_meta(row, question),
                **retrieval_cells(row),
                **pipeline_cells(question, checks),
                **answer_cells(answer),
                **judge_cells(judgement if answer else None),
                **concern_cells(concerns, flags),
            }
        )
    return output


# ---------- writing ----------


def columns_for(rows: list[dict[str, Any]]) -> list[str]:
    """The fixed columns in contract order, then every concern column sorted."""
    extra = sorted({key for row in rows for key in row} - set(FIXED_COLUMNS))
    return FIXED_COLUMNS + extra


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns_for(rows))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: "" if value is None else value for key, value in row.items()}
            )


def build_run(run: Path) -> Path:
    """Write <run>/results_flat.csv and return its path."""
    path = run / FILE_NAME
    write_csv(run_rows(run), path)
    return path


def run_folders(runs_path: Path) -> list[Path]:
    if not runs_path.exists():
        return []
    return sorted(
        path
        for path in runs_path.iterdir()
        if path.is_dir() and (path / "config.json").exists()
    )


def build_all(runs_path: Path, combined: Path) -> Path:
    """Write every run's own table and one combined table across all runs."""
    every: list[dict[str, Any]] = []
    for run in run_folders(runs_path):
        rows = run_rows(run)
        write_csv(rows, run / FILE_NAME)
        every.extend(rows)
    write_csv(every, combined)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="one run folder")
    parser.add_argument(
        "--all", action="store_true", help="every run folder, plus the combined table"
    )
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--combined", type=Path, default=COMBINED)
    args = parser.parse_args()
    if args.all:
        print(f"Wrote {build_all(args.runs.resolve(), args.combined.resolve())}")
    elif args.run:
        print(f"Wrote {build_run(args.run.resolve())}")
    else:
        parser.error("give --run RUN_DIR or --all")


if __name__ == "__main__":
    main()
