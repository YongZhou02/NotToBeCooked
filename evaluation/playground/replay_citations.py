"""Replay the answers saved in a run through citation-check variants. No model calls.

    uv run --project apps/api python evaluation/playground/replay_citations.py [--run <run dir>]

For every saved draft it runs: prod, marker_styles, quote_only, auto_marker.
Writes reports/citation_replay.csv and reports/citation_replay.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playground.toolkit import EVALUATION, PLAYGROUND  # noqa: E402
from playground.toolkit.citation import VARIANTS  # noqa: E402
from playground.toolkit.trace import Trace  # noqa: E402

DEFAULT_RUN = EVALUATION / "runs/20261108T004258996111Z"
QUESTIONS = EVALUATION / "datasets/cpt316/all/questions.jsonl"
REPORTS = PLAYGROUND / "reports"
FIXED = ["run_id", "pipeline", "chunks_version", "question_id", "split", "category", "origin",
         "answerable", "verified", "is_hard_case", "author"]
STEP = ["answer.shown", "answer.block_reason", "answer.n_citations",
        "judge.correct", "judge.supported", "judge.useful", "citation.changed"]
QUOTE_FAILURES = {
    "t1-015": "the model put a full stop between two lines. The page reads "
              "\"t1 = id3 * 60.0 id1 = id2 + t1\" with no full stop. It also wrote no marker.",
    "t1-041": "the model joined two separate lines of the page into one sentence "
              "(\"Output of analysis = ...\" and \"Input to synthesis = ...\"). Other text sits between "
              "them on the page. It also wrote no marker.",
    "t1-044": "the page has arrows with brackets, like \"-> [Compiler] -> Target Assembly Program\". "
              "The model rewrote them as \"Compiler -> Target Assembly Program\", which is not on the page. "
              "It did write markers, so this is its only problem.",
}
GRADE = {2: "correct", 1: "partly correct", 0: "wrong"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def replay(run: Path) -> list[dict]:
    answers = read(run / "generation_answers.json")
    judged = read(run / "judgements.json")["answers"]
    questions = {q["id"]: q for q in map(json.loads, QUESTIONS.read_text(encoding="utf-8").splitlines()) if q}
    rows = []
    for item in answers:
        qid = item["question_id"]
        trace = item["generation_trace"]
        draft = trace.get("draft")
        question = questions.get(qid, {})
        judge = judged.get(qid, {})
        for name, variant in VARIANTS.items():
            row = {
                "run_id": run.name,
                "pipeline": f"replay:{name}", "chunks_version": "run-local",
                "question_id": qid, "split": item.get("split"), "category": item.get("category"),
                "origin": item.get("origin"), "answerable": item.get("answerable"),
                "verified": question.get("verified"), "is_hard_case": bool(question.get("is_hard_case")),
                "author": question.get("author"),
                "judge.correct": judge.get("correct"), "judge.supported": judge.get("supported"),
                "judge.useful": judge.get("useful"),
                "_variant": name, "_refused": judge.get("refused"), "_note": judge.get("note"),
                "_saved_ok": trace.get("grounding_ok"), "_saved_problems": trace.get("grounding_problems"),
            }
            if draft is None:  # the model call itself failed; there is nothing to replay
                row.update({"answer.shown": False, "answer.block_reason": "no draft: " + trace.get("generation_error", "")[:60],
                            "answer.n_citations": 0, "citation.changed": False,
                            "_report": None, "_draft": None})
                rows.append(row)
                continue
            with Trace():
                report = variant(draft["answer"], draft["citations"], item["sources"], draft.get("uncovered"))
            row.update({
                "answer.shown": report["ok"],
                "answer.block_reason": " | ".join(report["problems"]),
                "answer.n_citations": len(report["citations"]) if report["ok"] else 0,
                "citation.changed": report["changed"] and report["ok"],
                "_report": report, "_draft": draft,
            })
            rows.append(row)
    return rows


def acceptance(rows: list[dict]) -> tuple[int, list[dict]]:
    """prod replay must give the saved grounding_ok and grounding_problems exactly."""
    checked, bad = 0, []
    for row in rows:
        if row["_variant"] != "prod" or row["_report"] is None:
            continue
        checked += 1
        report = row["_report"]
        if report["ok"] != row["_saved_ok"] or report["problems"] != row["_saved_problems"]:
            bad.append({"question_id": row["question_id"], "replayed": report["problems"],
                        "saved": row["_saved_problems"]})
    return checked, bad


def write_csv(rows: list[dict]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "citation_replay.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIXED + STEP, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def grade_counts(rows: list[dict]) -> str:
    counts = Counter(r["judge.correct"] for r in rows)
    return f"{counts[2]} / {counts[1]} / {counts[0]}"


def write_report(rows: list[dict], run: Path, checked: int, bad: list[dict]) -> Path:
    by = {v: {r["question_id"]: r for r in rows if r["_variant"] == v} for v in VARIANTS}
    prod = by["prod"]
    total = len(prod)
    prod_shown = {q for q, r in prod.items() if r["answer.shown"]}
    lines = [
        "# Citation check replay",
        "",
        f"Run: `{run.name}`. {total} saved answers from the production model. No new model calls were made.",
        "",
        "## What was tested",
        "",
        "The production check blocks an answer when the model lists a citation but forgets to write the "
        "marker, like [1], in the answer text. Most blocked answers were blocked for only that reason. "
        "Three other ways of checking were tried on the same saved answers. In all of them, a quote must "
        "still be found word for word on the page it names.",
        "",
        "- **prod**: the real production check, unchanged.",
        "- **marker_styles**: turns marker styles like 【1】 and (1) into [1] first. A (1) is changed only "
        "when 1 is a listed citation and it is not a list number such as \"(1) Compiler\".",
        "- **quote_only**: shows the answer when every quote is on its page. It ignores only the "
        "\"listed but never referred to\" problem.",
        "- **auto_marker**: adds the missing [n] after the sentence that best matches the quote, then runs "
        "the unchanged production check.",
        "",
        "Checking the replay itself: " + (
            f"the replayed production check gave the same result as the saved run for all {checked} "
            f"answers that have a draft ({total - checked} answer had no draft because the model call failed)."
            if not bad else f"the replay DID NOT match the saved run for {len(bad)} of {checked} answers."),
        "",
        "## Results",
        "",
        "Judge grades are from the AI judge (qwen), which graded the draft whether or not it was shown. "
        "Grades are written as correct / partly correct / wrong.",
        "",
        "| Variant | Shown | Blocked | Rescued vs prod | Judge on all shown | Judge on rescued |",
        "|---|---|---|---|---|---|",
    ]
    rescued_by: dict[str, list[dict]] = {}
    for name in VARIANTS:
        shown = [r for r in by[name].values() if r["answer.shown"]]
        rescued = [r for r in shown if r["question_id"] not in prod_shown]
        rescued_by[name] = rescued
        lines.append(f"| {name} | {len(shown)} | {total - len(shown)} | {len(rescued)} | "
                     f"{grade_counts(shown)} | {grade_counts(rescued) if name != 'prod' else '-'} |")
    lines += ["", "(Shown counts include honest \"not in the notes\" answers, which production already shows.)", "",
              "The answers that looked like they used \"(1)\" markers were checked by hand. They wrote "
              "\"LL(1)\", which is the name of a parsing method, not a citation. marker_styles leaves "
              "these alone on purpose. Only the 【1】 style was a real marker, in 2 answers.", ""]

    lines += ["## Risks", ""]
    for name in list(VARIANTS)[1:]:
        risky = [r for r in rescued_by[name] if r["answerable"] is False]
        wrong = [r for r in rescued_by[name] if r["judge.correct"] == 0 and r["answerable"] is not False]
        lines.append(f"**{name}**")
        if risky:
            for r in risky:
                lines.append(f"- Unanswerable question {r['question_id']} was rescued. Judge grade: "
                             f"{GRADE.get(r['judge.correct'])}. This is a real risk.")
        else:
            lines.append("- No answer to an unanswerable question was rescued.")
        if wrong:
            for r in wrong:
                lines.append(f"- {r['question_id']} was rescued but the judge rated it wrong: {r['_note']}")
        else:
            lines.append("- No rescued answer was rated wrong by the judge.")
        lines.append("")

    # The genuine quote failures.
    fails = [r for r in prod.values() if r["_report"] and any("does not appear" in p for p in r["_report"]["problems"])]
    lines += ["## The quote failures", "",
              f"{len(fails)} answers have a quote that is not on its page. No variant shows them, "
              "which is correct: the check works as it should here.", ""]
    for r in fails:
        qid = r["question_id"]
        still = all(not by[v][qid]["answer.shown"] for v in list(VARIANTS)[1:])
        lines.append(f"- {qid} ({'blocked in every variant' if still else 'RESCUED BY A VARIANT'}): "
                     + QUOTE_FAILURES.get(qid, "the quote is not on the page it names."))
    lines.append("")

    changed = [r for r in by["auto_marker"].values() if r["answer.shown"] and r["citation.changed"]]
    places = [p for r in changed for p in r["_report"]["changes"]]
    weak = [p for p in places if p["score"] < 0.3]
    several = sum(1 for r in changed if len({p["sentence"] for p in r["_report"]["changes"]}) > 1)
    lines += ["## Where auto_marker put the markers", "",
              f"It added markers to {len(changed)} answers ({len(places)} markers in all). "
              f"{several} answers got markers on more than one sentence. {len(weak)} placements were weak "
              "matches (little shared wording between the quote and the sentence). A person should look at "
              "those before this is trusted. The sentence chosen for each marker is kept in the replay "
              "(the `changes` of each report).", ""]

    shown_auto = sum(1 for r in by["auto_marker"].values() if r["answer.shown"])
    n = len(rescued_by["auto_marker"])
    ok_n = sum(1 for r in rescued_by["auto_marker"] if r["judge.correct"] == 2)
    bad_n = sum(1 for r in rescued_by["auto_marker"] if r["judge.correct"] == 0)
    lines += [
        "## Recommendation", "",
        f"Today a student sees an answer for only {len(prod_shown)} of these {total} questions, because the "
        "check blocks answers whose quotes are fine but whose [n] markers are missing. Adding the missing "
        f"markers (auto_marker) would show {shown_auto} answers, and each one still has to pass the full quote "
        f"check, so no made-up quote gets through. Of the {n} newly shown answers the judge rated {ok_n} "
        f"correct and {bad_n} wrong. auto_marker is better than quote_only because it shows the same answers "
        "but with clickable citations, so the student can see which line supports which sentence; quote_only "
        "would show plain text with no markers at all. Fixing the marker styles helps only 2 answers, so it "
        "is a small extra, not the fix. The cost is that the old check was also hiding some bad answers by "
        "accident: the wrong ones quote real lines but answer a different question, or go along with a wrong "
        "idea in the question. The quote check cannot catch those. So this change should go together with a "
        "check that the answer is about what was asked, and a person should read the weak marker placements first.",
        "",
    ]
    text = "\n".join(lines) + "\n"
    path = REPORTS / "citation_replay.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    run = args.run if args.run.is_absolute() else Path.cwd() / args.run
    rows = replay(run)
    checked, bad = acceptance(rows)
    print(f"prod replay: {checked - len(bad)}/{checked} identical to the saved grounding result")
    for item in bad:
        print("  MISMATCH", item)
    write_csv(rows)
    write_report(rows, run, checked, bad)
    for name in VARIANTS:
        shown = sum(1 for r in rows if r["_variant"] == name and r["answer.shown"])
        print(f"{name:14} shown {shown}")


if __name__ == "__main__":
    main()
