"""Compare paired generation runs without treating grounding as correctness."""

import argparse
import json
from pathlib import Path
from statistics import mean

from scorers.retrieval import retrieval_metrics


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare(before, after, dataset, before_supplement=None, after_prefix=None):
    configs = [read(folder / "config.json") for folder in (before, after)]
    for field in (
        "dataset_hashes",
        "source_hashes",
        "generation_model",
        "embedding_model",
        "generation_method",
        "question_split",
    ):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError(f"Runs differ in {field}; use matching settings/code")
    if configs[0].get("query_rewrite_enabled") or not configs[1].get(
        "query_rewrite_enabled"
    ):
        raise ValueError("Expected baseline off and treatment on")
    labels = {
        row["id"]: {"answerable": True, **row}
        for line in (dataset / "questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    runs = [
        {row["question_id"]: row for row in read(folder / "generation_answers.json")}
        for folder in (before, after)
    ]
    if before_supplement:
        supplement_config = read(before_supplement / "config.json")
        for field in (
            "dataset_hashes",
            "source_hashes",
            "generation_model",
            "embedding_model",
            "generation_method",
            "question_split",
            "query_rewrite_enabled",
        ):
            if supplement_config.get(field) != configs[0].get(field):
                raise ValueError(f"Baseline supplement differs in {field}")
        for row in read(before_supplement / "generation_answers.json"):
            old = runs[0].get(row["question_id"])
            if not old or not old["generation_trace"].get("generation_error"):
                raise ValueError(
                    "Supplement may replace only baseline provider failures"
                )
            if row["generation_trace"].get("generation_error"):
                raise ValueError("Supplement still contains provider failures")
            runs[0][row["question_id"]] = row
    if after_prefix:
        prefix_config = read(after_prefix / "config.json")
        for field in (
            "dataset_hashes",
            "source_hashes",
            "generation_model",
            "embedding_model",
            "generation_method",
            "question_split",
            "query_rewrite_enabled",
        ):
            if prefix_config.get(field) != configs[1].get(field):
                raise ValueError(f"Treatment prefix differs in {field}")
        for row in read(after_prefix / "generation_answers.json"):
            if row["question_id"] in runs[1]:
                raise ValueError("Treatment partitions must be disjoint")
            runs[1][row["question_id"]] = row
    if runs[0].keys() != runs[1].keys() or not runs[0]:
        raise ValueError("Runs must contain exactly the same nonempty question set")
    rows = []
    for question_id, baseline in runs[0].items():
        treatment = runs[1][question_id]
        label = labels[question_id]
        retry = next(
            (
                s.get("query_rewrite")
                for s in treatment["scope_snapshots"]
                if s.get("query_rewrite")
            ),
            {},
        )
        selected = (
            treatment["generation_trace"].get("retry_sources", [])
            if retry.get("accepted")
            else treatment["sources"]
        )
        metrics = (
            [
                retrieval_metrics(sources, label["evidence_groups"])
                for sources in (baseline["sources"], selected)
            ]
            if label["answerable"]
            else [None, None]
        )
        rows.append(
            {
                "question_id": question_id,
                "question": label["question"],
                "answerable": label["answerable"],
                "reference_answer": label["reference_answer"],
                "required_facts": label["required_facts"],
                "before": baseline["response"],
                "after": treatment["response"],
                "treatment_initial_draft": treatment["generation_trace"].get(
                    "drafts", [None]
                )[0],
                "before_ms": baseline["generation_ms"],
                "after_ms": treatment["generation_ms"],
                "rewrite": retry,
                "before_retrieval": metrics[0],
                "after_retrieval": metrics[1],
                "before_error": baseline["generation_trace"].get("generation_error"),
                "after_error": treatment["generation_trace"].get("generation_error"),
                "review": {
                    "reviewer": None,
                    "before_correctness_0_to_2": None,
                    "after_correctness_0_to_2": None,
                    "notes": "",
                },
            }
        )
    summary = {
        "questions": len(rows),
        "answerable": sum(r["answerable"] for r in rows),
        "rewrite_attempted": sum(bool(r["rewrite"].get("attempted")) for r in rows),
        "rewrite_accepted": sum(bool(r["rewrite"].get("accepted")) for r in rows),
        "independent_model_runs": True,
    }
    for side in ("before", "after"):
        summary[side] = {
            "grounded_rate_NOT_accuracy": mean(r[side]["grounded"] for r in rows),
            "mean_generation_ms": mean(r[f"{side}_ms"] for r in rows),
            "generation_errors": sum(bool(r[f"{side}_error"]) for r in rows),
            "answerable_evidence_recall@5": mean(
                r[f"{side}_retrieval"]["evidence_recall@5"]
                for r in rows
                if r["answerable"]
            )
            if any(r["answerable"] for r in rows)
            else None,
        }
    return {
        "baseline": str(before),
        "baseline_provider_failure_retest": str(before_supplement)
        if before_supplement
        else None,
        "treatment": str(after),
        "treatment_prefix": str(after_prefix) if after_prefix else None,
        "summary": summary,
        "questions": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--before-supplement", type=Path)
    parser.add_argument("--after-prefix", type=Path)
    parser.add_argument(
        "--ratings", type=Path, help="Explicit per-question correctness ratings"
    )
    args = parser.parse_args()
    result = compare(
        args.before, args.after, args.dataset, args.before_supplement, args.after_prefix
    )
    if args.ratings:
        ratings = read(args.ratings)
        if set(ratings["reviews"]) != {r["question_id"] for r in result["questions"]}:
            raise ValueError("Ratings must cover exactly the compared question IDs")
        for row in result["questions"]:
            review = ratings["reviews"][row["question_id"]]
            for side in ("before", "after"):
                score = review[f"{side}_correctness_0_to_2"]
                if type(score) is not int or score not in (0, 1, 2):
                    raise ValueError("Correctness ratings must be integers 0, 1 or 2")
            row["review"] = {**review, "reviewer": ratings["reviewer"]}
        result["summary"]["correctness_review_status"] = ratings["status"]
        for side in ("before", "after"):
            scores = [
                r["review"][f"{side}_correctness_0_to_2"] for r in result["questions"]
            ]
            result["summary"][side]["fully_correct_count"] = scores.count(2)
            result["summary"][side]["strict_full_reference_answer_rate"] = scores.count(
                2
            ) / len(scores)
            result["summary"][side]["partial_credit_score"] = sum(scores) / (
                2 * len(scores)
            )
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "comparison.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Query rewrite pilot comparison",
        "",
        "Grounding is not answer correctness. Score each answer against all required facts:",
        "0 = incorrect / missing answer; 1 = partially correct; 2 = fully correct.",
        "For unanswerable questions, an appropriate refusal receives 2; invented answers receive 0.",
        "Provider failures remain in end-to-end scores and must also be reported separately.",
        "",
        "```json",
        json.dumps(result["summary"], indent=2),
        "```",
        "",
    ]
    for row in result["questions"]:
        lines += [
            f"## {row['question_id']}",
            "",
            row["question"],
            "",
            "Reference: " + row["reference_answer"],
            "",
            "Before:",
            "",
            row["before"]["answer"],
            "",
            "After:",
            "",
            row["after"]["answer"],
            "",
            f"Rewrite attempted: {row['rewrite'].get('attempted', False)}; accepted: {row['rewrite'].get('accepted', False)}",
            "",
            (
                f"Review: before {row['review']['before_correctness_0_to_2']}/2; "
                f"after {row['review']['after_correctness_0_to_2']}/2; notes: {row['review']['notes']}"
            ),
            "",
        ]
    (args.out / "review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Review: {args.out / 'review.md'}")


if __name__ == "__main__":
    main()
