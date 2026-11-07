"""Assemble evaluation datasets and run artifacts into one dashboard JSON file.

This does not run extraction, retrieval, or generation. It only reads existing
artifacts, recomputes trace metadata, and writes a UI-ready JSON document.
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

EVALUATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION))

from scorers.answer_quality import review_summary
from scorers.retrieval import covered_groups, evidence_matches, normalize

FUZZY_THRESHOLD = 0.88
METHODS = ("vector", "keyword", "hybrid_rrf")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def load_dataset(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(path / "dataset.json")
    sources = read_json(path / "sources.json")
    questions = read_jsonl(path / "questions.jsonl")
    return {**config, **sources}, questions


def partial_similarity(expected: str, actual: str) -> float:
    """Page-aware fuzzy quote similarity; diagnostic only, never a gold-label rewrite."""
    expected_norm, actual_norm = normalize(expected), normalize(actual)
    if not expected_norm:
        return 0.0
    if expected_norm in actual_norm:
        return 1.0
    if not actual_norm:
        return 0.0
    width = len(expected_norm)
    if len(actual_norm) <= width:
        return SequenceMatcher(None, expected_norm, actual_norm).ratio()
    step = max(1, width // 5)
    starts = list(range(0, len(actual_norm) - width + 1, step))
    starts.append(len(actual_norm) - width)
    return max(
        SequenceMatcher(None, expected_norm, actual_norm[start : start + width]).ratio()
        for start in starts
    )


def page_blocks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[str]] = defaultdict(list)
    for item in items:
        for page in range(item["page_start"], item["page_end"] + 1):
            grouped[(item["document_id"], page)].append(item["content"])
    return [
        {
            "document_id": document_id,
            "page_start": page,
            "page_end": page,
            "content": " ".join(content),
        }
        for (document_id, page), content in grouped.items()
    ]


def fuzzy_group_score(group: dict[str, Any], pages: list[dict[str, Any]]) -> float:
    score = 0.0
    for alternative in group["alternatives"]:
        for page in pages:
            if (
                page["document_id"] == alternative["document_id"]
                and page["page_start"] <= alternative["pdf_page"] <= page["page_end"]
            ):
                score = max(
                    score, partial_similarity(alternative["quote"], page["content"])
                )
    return score


def result_rows(run: Path) -> list[dict[str, Any]]:
    preferred = run / "results.jsonl"
    return read_jsonl(preferred if preferred.exists() else run / "retrieval.jsonl")


def method_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {}
    test_rows = [row for row in rows if row.get("split") == "test"]
    for method in METHODS:
        selected = [row for row in test_rows if row.get("method") == method]
        if not selected:
            continue
        timings = [value for row in selected for value in row.get("retrieval_ms", [])]
        output[method] = {
            "questions": len(selected),
            **{
                metric: statistics.mean(row["metrics"][metric] for row in selected)
                for metric in (
                    "hit@1",
                    "hit@5",
                    "evidence_recall@5",
                    "complete_evidence@5",
                    "mrr@5",
                )
            },
            "median_retrieval_ms": statistics.median(timings) if timings else None,
        }
    return output


def score(value: float | None, metric: str, status: str = "measured") -> dict[str, Any]:
    return {
        "value": round(value, 1) if value is not None else None,
        "metric": metric,
        "status": status if value is not None else "unavailable",
    }


def phase_scores(
    checks: dict[str, Any],
    methods: dict[str, Any],
    assistant_reviews: list[dict[str, Any]],
    fuzzy_coverage: float | None,
) -> list[dict[str, Any]]:
    hybrid = methods.get("hybrid_rrf", {})
    reviews = review_summary(assistant_reviews)
    means = reviews["mean_scores_0_to_2"]
    generation_dimensions = [
        means[name] for name in ("faithfulness", "correctness", "completeness")
    ]
    generation = (
        statistics.mean(generation_dimensions) / 2 * 100
        if all(value is not None for value in generation_dimensions)
        else None
    )
    citation = (
        means["citation_support"] / 2 * 100
        if means["citation_support"] is not None
        else None
    )
    return [
        {
            "id": "extraction",
            "number": 1,
            "label": "Extraction",
            **score(
                checks.get("extraction_evidence_coverage", 0) * 100 if checks else None,
                "gold exact coverage",
            ),
            "secondary": (
                f"fuzzy ≥ {FUZZY_THRESHOLD:.2f}: {fuzzy_coverage:.1f}%"
                if fuzzy_coverage is not None
                else "fuzzy unavailable"
            ),
        },
        {
            "id": "chunking",
            "number": 2,
            "label": "Chunking",
            **score(
                checks.get("chunk_evidence_coverage", 0) * 100 if checks else None,
                "evidence intact",
            ),
            "secondary": f"over budget: {len(checks.get('over_budget_chunks', []))}"
            if checks
            else "",
        },
        {
            "id": "retrieval",
            "number": 3,
            "label": "Embedding + retrieval",
            **score(
                hybrid.get("evidence_recall@5", 0) * 100 if hybrid else None,
                "hybrid recall@5",
            ),
            "secondary": f"MRR {hybrid.get('mrr@5', 0):.3f}" if hybrid else "",
        },
        {
            "id": "context",
            "number": 4,
            "label": "Context assembly",
            **score(
                hybrid.get("complete_evidence@5", 0) * 100 if hybrid else None,
                "complete evidence@5",
            ),
            "secondary": "retrieval proxy",
        },
        {
            "id": "citation",
            "number": 5,
            "label": "Citation",
            **score(citation, "support / 2", "assistant review"),
            "secondary": f"assistant: {reviews['completed']}/{reviews['total']}",
        },
        {
            "id": "generation",
            "number": 6,
            "label": "Generation",
            **score(generation, "faithful + correct + complete", "assistant review"),
            "secondary": f"assistant: {reviews['completed']}/{reviews['total']}",
        },
    ]


def compact_match(block: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "pages": [block["page_start"], block["page_end"]],
        "heading": block.get("heading"),
        "content": block["content"],
    }


def trace_question(
    question: dict[str, Any],
    run: Path,
    extracted: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    generation: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    groups = question["evidence_groups"]
    pages = page_blocks(extracted)
    per_group = []
    for group in groups:
        extraction_matches = [
            compact_match(block, index)
            for index, block in enumerate(pages)
            if group["id"] in covered_groups([block], [group])
        ]
        chunk_matches = [
            compact_match(block, index)
            for index, block in enumerate(chunks)
            if group["id"] in covered_groups([block], [group])
        ]
        fuzzy_value = fuzzy_group_score(group, pages)
        retrieval = {}
        for method in METHODS:
            result = next(
                (
                    row
                    for row in rows
                    if row["question_id"] == question["id"] and row["method"] == method
                ),
                None,
            )
            if result:
                ranks = [
                    source.get("rank", index + 1)
                    for index, source in enumerate(result["sources"])
                    if any(
                        evidence_matches(source, alt) for alt in group["alternatives"]
                    )
                ]
                retrieval[method] = {"ranks": ranks, "found": bool(ranks)}
        per_group.append(
            {
                "id": group["id"],
                "alternatives": group["alternatives"],
                "extraction": {
                    "exact": bool(extraction_matches),
                    "fuzzy_score": round(fuzzy_value, 4),
                    "fuzzy_pass": fuzzy_value >= FUZZY_THRESHOLD,
                    "matches": extraction_matches,
                },
                "chunking": {"intact": bool(chunk_matches), "matches": chunk_matches},
                "retrieval": retrieval,
            }
        )
    hybrid = next(
        (
            row
            for row in rows
            if row["question_id"] == question["id"] and row["method"] == "hybrid_rrf"
        ),
        None,
    )
    answer = next(
        (item for item in generation if item["question_id"] == question["id"]), None
    )
    review = next(
        (item for item in reviews if item["question_id"] == question["id"]), None
    )
    return {
        "run_id": run.name,
        "groups": per_group,
        "context": {
            "chunks": hybrid["sources"] if hybrid else [],
            "metrics": hybrid.get("metrics") if hybrid else None,
        },
        "citation": answer.get("response", {}).get("citations", []) if answer else [],
        "generation": answer.get("response") if answer else None,
        "assistant_review": (
            {
                key: review.get(key)
                for key in (
                    "faithfulness",
                    "correctness",
                    "completeness",
                    "citation_support",
                    "notes",
                )
            }
            if review
            else None
        ),
    }


def assemble(dataset_path: Path, runs_path: Path) -> dict[str, Any]:
    dataset, questions = load_dataset(dataset_path)
    run_paths = sorted(
        [
            path
            for path in runs_path.iterdir()
            if path.is_dir() and (path / "config.json").exists()
        ]
    )
    runs, trace_by_question = [], {question["id"]: {} for question in questions}
    for run in run_paths:
        config = read_json(run / "config.json", {})
        checks = read_json(run / "checks.json", {})
        extracted = read_json(run / "extracted_items.json", [])
        chunks = read_json(run / "chunks.json", [])
        rows = result_rows(run)
        generation = read_json(run / "generation_answers.json", [])
        assistant_reviews = read_json(run / "assistant_reviews.json", [])
        methods = method_summary(rows)
        pages = page_blocks(extracted)
        all_groups = [
            group for question in questions for group in question["evidence_groups"]
        ]
        fuzzy_count = sum(
            fuzzy_group_score(group, pages) >= FUZZY_THRESHOLD for group in all_groups
        )
        fuzzy_coverage = (
            fuzzy_count / len(all_groups) * 100 if all_groups and extracted else None
        )
        mode = (
            "Full + generation"
            if generation
            else "Retrieval"
            if rows
            else "Extraction only"
        )
        fingerprint = "+".join(
            document["sha256"]
            for document in config.get("corpus", {}).get("documents", [])
        )
        runs.append(
            {
                "id": run.name,
                "created_at": str(config.get("created_at", "")),
                "mode": mode,
                "repeats": config.get("repeats", 1),
                "source_fingerprint": fingerprint,
                "documents": config.get("corpus", {}).get("documents", []),
                "phases": phase_scores(
                    checks, methods, assistant_reviews, fuzzy_coverage
                ),
                "retrieval_methods": methods,
                "questions_evaluated": len({row["question_id"] for row in rows}),
                "generation_answers": len(generation),
            }
        )
        for question in questions:
            trace_by_question[question["id"]][run.name] = trace_question(
                question, run, extracted, chunks, rows, generation, assistant_reviews
            )
    fingerprint_counts: dict[str, int] = defaultdict(int)
    for run in runs:
        fingerprint_counts[run["source_fingerprint"]] += 1
    for run in runs:
        run["same_source_run_count"] = fingerprint_counts[run["source_fingerprint"]]
    preferred = next(
        (run["id"] for run in reversed(runs) if run["mode"] == "Full + generation"),
        runs[-1]["id"],
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ui_mode": "prototype; no live run backend",
        "fuzzy_matching": {
            "threshold": FUZZY_THRESHOLD,
            "method": "page-aware normalized sliding-window SequenceMatcher",
            "diagnostic_only": True,
        },
        "dataset": {
            "name": dataset["name"],
            "scope": dataset["scope"],
            "questions": len(questions),
            "evidence_groups": sum(
                len(question["evidence_groups"]) for question in questions
            ),
            "documents": dataset["documents"],
        },
        "selected_run_id": preferred,
        "runs": list(reversed(runs)),
        "questions": [
            {
                "id": question["id"],
                "question": question["question"],
                "category": question["category"],
                "split": question["split"],
                "reference_answer": question["reference_answer"],
                "required_facts": question["required_facts"],
                "evidence_groups": question["evidence_groups"],
                "traces": trace_by_question[question["id"]],
            }
            for question in questions
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=EVALUATION / "datasets/cpt316/topic1"
    )
    parser.add_argument("--runs", type=Path, default=EVALUATION / "runs")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "dashboard_data.json"
    )
    args = parser.parse_args()
    data = assemble(args.dataset.resolve(), args.runs.resolve())
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output.resolve()} | {len(data['runs'])} runs | "
        f"{len(data['questions'])} questions"
    )


if __name__ == "__main__":
    main()
