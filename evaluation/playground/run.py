"""Run one or more pipelines over the question set and write a run folder each.

    uv run --project apps/api python evaluation/playground/run.py \
        --pipeline prod_hybrid --pipeline memory_hybrid --chunks v1 [--split dev] [--limit 10]

Writes evaluation/playground/runs/<UTC timestamp>-<pipeline>/{config.json, trace.jsonl, results.csv}.
See README.md for the table layout. No pipeline run here calls a language model.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib
import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playground.toolkit import EVALUATION, PLAYGROUND, ROOT  # noqa: E402
from playground.toolkit.chunks import read_manifest  # noqa: E402
from playground.toolkit.trace import Trace, csv_cell  # noqa: E402
from scorers.retrieval import retrieval_metrics  # noqa: E402

DATASET = EVALUATION / "datasets/cpt316/all"
RUNS = PLAYGROUND / "runs"
PIPELINES = PLAYGROUND / "pipelines"
SPLITS = ("dev", "test", "stress")
IDENTITY_COLUMNS = [
    "run_id", "pipeline", "chunks_version", "question_id", "split", "category", "origin",
    "answerable", "verified", "is_hard_case", "author",
]
RETRIEVAL_COLUMNS = [
    "retrieval.hit@1", "retrieval.hit@3", "retrieval.hit@5", "retrieval.evidence_recall@5",
    "retrieval.complete_evidence@5", "retrieval.mrr@5", "retrieval.ms",
]
SUMMARY_COLUMNS = [
    "retrieval.hit@1", "retrieval.hit@3", "retrieval.hit@5", "retrieval.evidence_recall@5",
    "retrieval.complete_evidence@5", "retrieval.mrr@5",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def read_questions(dataset: Path, splits: list[str] | None = None, limit: int | None = None) -> list[dict]:
    """Same eligibility as run_eval.load_dataset: rows marked not strict-retrieval-eligible are dropped."""
    lines = (dataset / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    rows = [r for r in rows if r.get("label_review", {}).get("strict_retrieval_eligible", True)]
    if splits:
        rows = [r for r in rows if r["split"] in splits]
    return rows[:limit] if limit else rows


def load_pipeline(name: str) -> ModuleType:
    """A pipeline by file name (`prod_hybrid`) or by its NAME constant."""
    stems = [p.stem for p in sorted(PIPELINES.glob("*.py")) if not p.stem.startswith("_")]
    for stem in stems:
        module = importlib.import_module(f"playground.pipelines.{stem}")
        if name in (stem, getattr(module, "NAME", None)):
            return module
    raise SystemExit(f"No pipeline named {name!r}. Available: {', '.join(stems)}")


def retrieval_cells(question: dict, output: dict, trace: Trace) -> dict[str, Any]:
    """Retrieval scores when the pipeline returned `sources` for an answerable question."""
    cells: dict[str, Any] = {}
    sources = output.get("sources")
    groups = question.get("evidence_groups") or []
    if sources is not None and question.get("answerable", True) and groups:
        cells.update({f"retrieval.{k}": v for k, v in retrieval_metrics(sources, groups).items()})
    timings = [s["ms"] for s in trace.steps if s["step"].startswith("retrieval.") and s["ms"] is not None]
    if timings:
        cells["retrieval.ms"] = round(sum(timings), 3)
    return cells


async def answer_one(module: ModuleType, question: dict, tk: Any) -> tuple[dict, Trace]:
    """Call the pipeline inside its own Trace. A failure is recorded, not hidden, and the run goes on."""
    with Trace() as trace:
        try:
            output = await module.answer(question, tk) or {}
        except Exception as error:
            trace.record("pipeline.error", {"question_id": question["id"]}, None, None, repr(error)[:500])
            print(f"  ! {question['id']}: {error!r}", flush=True)
            output = {}
    return output, trace


def table_row(run_id: str, module: ModuleType, chunks_version: str, question: dict, cells: dict) -> dict:
    identity = {
        "run_id": run_id,
        "pipeline": module.NAME,
        "chunks_version": chunks_version,
        "question_id": question["id"],
        "split": question["split"],
        "category": question["category"],
        "origin": question.get("origin", "synthetic"),
        "answerable": question.get("answerable", True),
        "verified": question.get("verified"),
        "is_hard_case": question.get("is_hard_case", False),
        "author": question.get("author"),
    }
    return {**identity, **cells}


def write_results(path: Path, rows: list[dict]) -> None:
    """README column order: identity columns, retrieval columns, then any other step columns as first seen."""
    extra = list(dict.fromkeys(k for r in rows for k in r if k not in IDENTITY_COLUMNS + RETRIEVAL_COLUMNS))
    header = IDENTITY_COLUMNS + RETRIEVAL_COLUMNS + extra
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, restval="", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: csv_cell(v) for k, v in row.items()})


def summarise_rows(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Mean of each retrieval measure over scored rows, for all splits and per split."""
    summary = {}
    for label in ("all", *SPLITS):
        chosen = [r for r in rows if label == "all" or r["split"] == label]
        scored = [r for r in chosen if r.get("retrieval.hit@5") is not None]
        if not scored:
            continue
        means: dict[str, float] = {c: statistics.mean(r[c] for r in scored) for c in SUMMARY_COLUMNS}
        timings = [r["retrieval.ms"] for r in scored if r.get("retrieval.ms") is not None]
        means["retrieval.median_ms"] = statistics.median(timings) if timings else float("nan")
        means["scored"] = len(scored)
        summary[label] = means
    return summary


def print_summary(name: str, out: Path, rows: list[dict], failures: int) -> None:
    print(f"\n{name}: {len(rows)} questions -> {out}" + (f"  ({failures} FAILED)" if failures else ""))
    for label, m in summarise_rows(rows).items():
        print(
            f"  {label:<7} n={m['scored']:<3} hit@1 {m['retrieval.hit@1']:.3f}  hit@3 {m['retrieval.hit@3']:.3f}  "
            f"hit@5 {m['retrieval.hit@5']:.3f}  recall@5 {m['retrieval.evidence_recall@5']:.3f}  "
            f"complete@5 {m['retrieval.complete_evidence@5']:.3f}  mrr@5 {m['retrieval.mrr@5']:.3f}  "
            f"median {m['retrieval.median_ms']:.1f} ms"
        )


async def run_pipeline(
    module: ModuleType,
    questions: list[dict],
    tk: Any,
    runs_root: Path,
    config: dict[str, Any],
) -> tuple[Path, list[dict]]:
    """Run one pipeline over `questions`; write config.json, trace.jsonl, results.csv. Returns folder and rows."""
    started = datetime.now(UTC)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{module.NAME}"
    out = runs_root / run_id
    out.mkdir(parents=True)
    chunks_version = config["chunks"]["version"]
    pipeline_file = Path(module.__file__)
    (out / "config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": started.isoformat(),
                "pipeline": {
                    "name": module.NAME,
                    "description": getattr(module, "DESCRIPTION", ""),
                    "file": pipeline_file.name,
                    "sha256": sha256_file(pipeline_file),
                },
                **config,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    rows, failures = [], 0
    with (out / "trace.jsonl").open("w", encoding="utf-8") as trace_file:
        for number, question in enumerate(questions, start=1):
            output, trace = await answer_one(module, question, tk)
            failures += any(s["error"] for s in trace.steps if s["step"] == "pipeline.error")
            cells = {**retrieval_cells(question, output, trace), **(output.get("columns") or {})}
            rows.append(table_row(run_id, module, chunks_version, question, cells))
            trace_file.write(
                json.dumps(
                    {"question_id": question["id"], "question": question["question"], "steps": trace.steps},
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )
            trace_file.flush()
            if number % 20 == 0 or number == len(questions):
                print(f"  {module.NAME}: {number}/{len(questions)}", flush=True)
    write_results(out / "results.csv", rows)
    print_summary(module.NAME, out, rows, failures)
    return out, rows


async def main(args: argparse.Namespace) -> None:
    from playground.toolkit.kit import Toolkit  # heavy imports only when really running

    modules = [load_pipeline(name) for name in args.pipeline]
    questions = read_questions(args.dataset, args.split, args.limit)
    if not questions:
        raise SystemExit("No questions selected")
    manifest = read_manifest(args.chunks)
    questions_file = args.dataset / "questions.jsonl"
    git_dirty = bool(git_output("status", "--porcelain"))
    async with Toolkit.open(args.chunks) as tk:
        print(f"Preparing embeddings for {len(tk.chunks)} chunks and {len(questions)} questions (cached after the first run)")
        await tk.prepare(
            [q["question"] for q in questions],
            database=any(getattr(m, "NEEDS_DATABASE", False) for m in modules),
        )
        config = {
            "chunks": {"version": args.chunks, "sha256": manifest["chunks_sha256"]},
            "questions": {
                "file": str(questions_file.relative_to(ROOT)) if questions_file.is_relative_to(ROOT) else str(questions_file),
                "sha256": sha256_file(questions_file),
                "count": len(questions),
                "splits": args.split or "all",
                "limit": args.limit,
            },
            "embedding_model": tk.embedding_model,
            "git_commit": git_output("rev-parse", "HEAD"),
            "git_dirty": git_dirty,
        }
        for module in modules:
            await run_pipeline(module, questions, tk, args.runs, config)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pipeline", action="append", required=True, help="file name in pipelines/ (repeatable)")
    parser.add_argument("--chunks", default="v1", help="frozen chunk version (default v1)")
    parser.add_argument("--split", action="append", choices=SPLITS, help="only these splits (repeatable); default all")
    parser.add_argument("--limit", type=int, help="only the first N questions after the split filter")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--runs", type=Path, default=RUNS, help="where run folders go")
    return parser.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
