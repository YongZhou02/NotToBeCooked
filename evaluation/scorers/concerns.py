"""Turn a run into plain-language concerns. Pure functions; no network, no files.

Every concern is one item in concerns.json. A missing input never raises: the
concern becomes `not_measured` or `partly_measured` and says why.
"""

import json
import random
import re
from collections import Counter

from scorers.retrieval import evidence_matches, normalize
from scorers.statistics import wilson_interval

JUDGE = "AI judge, not yet checked by a human"
# Copied from app/services/llm.py REFUSAL; the app's own wording for "not covered".
REFUSAL = "The supplied material does not cover this question."
SHOWN_STATES = ("shown",)
LONG_WAIT_MS = 10_000
SHORT_ANSWER_WORDS = 15
COPY_RUN_WORDS = 5
COPY_HIGH = 0.8
LOW_TEXT_RECALL = 0.7
SHORT_CHUNK_TOKENS = 40
STRESS_CATEGORIES = ("vague", "typo", "manglish", "explain", "cross_part")

# One place for every severity cutoff: (high at or above, medium at or above).
# Each is applied to the concern's main "bad" rate, noted beside the name.
THRESHOLDS = {
    "blocked_answers": (0.30, 0.10),  # share of answers blocked
    "wrong_answers": (0.40, 0.20),  # share of answers not fully correct
    "mechanical_answers": (0.40, 0.20),  # share of answers that do not really help
    "real_wording": (0.25, 0.10),  # Hit@5 lost from clean to stress questions
    "unanswerable": (0.50, 0.20),  # share of unanswerable questions answered anyway
    "weak_citations": (0.40, 0.20),  # share of citations off the gold pages
    "lost_content": (0.10, 0.02),  # share of required evidence missing from chunks
    "bad_metadata": (0.30, 0.10),  # share of headings not on the chunk's pages
    "wrong_document": (0.30, 0.10),  # share of rank-1 results from the wrong PDF
    "slow_answers": (0.50, 0.20),  # share of answers over 10 seconds
    "metric_trust": (0.35, 0.20),  # width of the 95% range on the headline pass
}

TEXT = {
    "blocked_answers": (
        "Good answers are thrown away",
        "I asked a clear question and the app said it could not show an answer.",
    ),
    "wrong_answers": (
        "Wrong or half answers",
        "The app answered with confidence, but the answer was wrong or missed a part.",
    ),
    "mechanical_answers": (
        "Dead or copied answers",
        "The answer repeats the slide or gives one short line. It does not help me understand.",
    ),
    "real_wording": (
        "Real student wording",
        "It works when I type a neat question, but not when I type the way I really do.",
    ),
    "unanswerable": (
        "Saying I do not know",
        (
            "I asked something the notes never cover and the app made up an answer, "
            "or it refused something the notes do cover."
        ),
    ),
    "weak_citations": (
        "Citations that do not help",
        "I opened the source and it was the wrong page, or it did not prove the answer.",
    ),
    "lost_content": (
        "Text lost before the model sees it",
        "The answer is in my slides, but the app never had that text.",
    ),
    "bad_metadata": (
        "Wrong headings and page data",
        "The heading says one topic, but the text under it is about another.",
    ),
    "wrong_document": (
        "Answers from the wrong PDF",
        "I asked about one lecture and the answer came from a different file.",
    ),
    "slow_answers": (
        "Long waits",
        "I waited so long that I gave up or asked a friend.",
    ),
    "metric_trust": (
        "Can we trust the score?",
        "The dashboard shows a nice number, but it may not mean what we think.",
    ),
    "follow_ups": (
        "Follow-up questions",
        "I asked 'what about the second one?' and the app did not know what I meant.",
    ),
    "clean_pdfs": (
        "Real slides with pictures",
        "My real slides have images and diagrams, and the app may miss them.",
    ),
    "filtered_search": (
        "Search inside a big shared database",
        "On the real server, search for my file returns too few results.",
    ),
}


# ---------- small helpers ----------


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def rate_text(successes: int, total: int) -> str:
    if total < 1:
        return "no questions"
    low, high = wilson_interval(successes, total)
    return f"{successes}/{total} ({pct(successes / total)}), 95% range {pct(low)} to {pct(high)}"


def metric(label: str, value, note: str = "", judged: bool = False) -> dict:
    return {
        "label": f"{label} ({JUDGE})" if judged else label,
        "value": str(value),
        "note": note,
    }


def severity(concern: str, bad: float | None) -> str:
    if bad is None:
        return "unknown"
    high, medium = THRESHOLDS[concern]
    return "high" if bad >= high else "medium" if bad >= medium else "low"


def item(
    concern: str, status: str, bad: float | None, headline: str, metrics, examples, how
) -> dict:
    title, feels_like = TEXT[concern]
    return {
        "id": concern,
        "title": title,
        "feels_like": feels_like,
        "status": status,
        "severity": "unknown" if status == "not_measured" else severity(concern, bad),
        "headline": headline,
        "metrics": metrics,
        "examples": examples[:3],
        "how_measured": how,
    }


def not_measured(concern: str, headline: str, how: str) -> dict:
    return item(concern, "not_measured", None, headline, [], [], how)


def words(text: str) -> list[str]:
    return re.findall(r"\w+", normalize(re.sub(r"\[\d+\]|【\d+】", " ", text)))


def copy_ratio(answer: str, sources: list[str]) -> float | None:
    """Share of the answer's 5-word runs found word for word in its sources."""
    tokens = words(answer)
    if len(tokens) < COPY_RUN_WORDS:
        return None
    runs = [
        tuple(tokens[i : i + COPY_RUN_WORDS])
        for i in range(len(tokens) - COPY_RUN_WORDS + 1)
    ]
    known = set()
    for text in sources:
        t = words(text)
        known.update(
            tuple(t[i : i + COPY_RUN_WORDS]) for i in range(len(t) - COPY_RUN_WORDS + 1)
        )
    return sum(run in known for run in runs) / len(runs)


def has_marker(answer: str) -> bool:
    return bool(re.search(r"\[\d+\]", answer))


def normalise_problem(problem: str) -> str:
    """Make marker numbers and quoted text the same across answers so reasons can be counted."""
    text = re.sub(r"\[\d+\]", "[n]", problem)
    text = re.sub(r"1\.\.\d+", "1..N", text)
    return re.sub(r"\(.*?\): .*$", "", text).strip()


# ---------- judge ----------

JUDGE_SYSTEM = (
    "You grade one answer from a study assistant. Reply with one JSON object and nothing "
    "else. Keys: correct, supported, useful (integers 0, 1 or 2), refused (true or false), "
    "note (one short sentence).\n"
    "correct: 0 wrong or against the reference, 1 partly right or misses a required fact, "
    "2 has every required fact and nothing wrong.\n"
    "supported: 0 the claims are not backed by the quotes, 1 some are, 2 all are. An answer "
    "that makes no claim, such as a refusal, scores 2.\n"
    "useful: 0 does not help the student, 1 answers but is flat, copied or mechanical, "
    "2 really helps a confused student understand.\n"
    "refused: true if the answer says it cannot answer or the material does not cover it.\n"
    "If answerable is false, the notes do not hold the answer. Then correct is 2 only if the "
    "answer says the material does not cover it or corrects the false premise, and 0 if it "
    "makes up an answer. Judge only from the reference and the quotes, not outside knowledge."
)


def judge_messages(question: dict, answer: str, quotes: list[str]) -> list[dict]:
    payload = {
        "question": question["question"],
        "reference_answer": question["reference_answer"],
        "required_facts": question.get("required_facts", []),
        "answerable": question.get("answerable", True),
        "answer": answer,
        "citation_quotes": quotes,
    }
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def parse_judgement(text: str) -> dict | None:
    """Pull the JSON object out of a reply that may carry <think> text or code fences."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    text = text.split("</think>")[-1]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        raw = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    result = {}
    for key in ("correct", "supported", "useful"):
        try:
            value = int(raw[key])
        except (KeyError, TypeError, ValueError):
            return None
        if not 0 <= value <= 2:
            return None
        result[key] = value
    refused = raw.get("refused", False)
    if isinstance(refused, str):
        refused = refused.strip().lower() == "true"
    result["refused"] = bool(refused)
    result["note"] = str(raw.get("note", ""))[:300]
    return result


# ---------- joining a run's files ----------


def gold_docs(question: dict | None) -> set[str]:
    groups = (question or {}).get("evidence_groups", [])
    return {a["document_id"] for g in groups for a in g["alternatives"]}


def gold_pages(question: dict | None) -> set[tuple[str, int]]:
    groups = (question or {}).get("evidence_groups", [])
    return {
        (a["document_id"], a["pdf_page"]) for g in groups for a in g["alternatives"]
    }


def answer_state(row: dict) -> str:
    """failed: the model call broke. blocked: the grounding check rejected the draft."""
    trace = row.get("generation_trace") or {}
    text = (row.get("response") or {}).get("answer", "")
    if trace.get("generation_error") or text.startswith(
        "The answer could not be generated"
    ):
        return "failed"
    if trace.get("grounding_ok") is False or text.startswith(
        "An answer was written, but"
    ):
        return "blocked"
    if text.startswith("No passage in your material could be found"):
        return "blocked"
    return "shown"


def context_chunks(row: dict) -> list[dict]:
    """The chunks the model saw, in marker order."""
    sources = row.get("sources", [])
    snapshots = row.get("scope_snapshots") or []
    used = (snapshots[0] if snapshots else {}).get("used_chunk_ids")
    if not used:
        return sources
    by_id = {s["chunk_id"]: s for s in sources}
    return [by_id[c] for c in used if c in by_id]


def draft_of(row: dict) -> dict | None:
    draft = (row.get("generation_trace") or {}).get("draft")
    if draft:
        return draft
    response = row.get("response")
    if response and answer_state(row) == "shown":
        return {
            "answer": response.get("answer", ""),
            "citations": response.get("citations", []),
        }
    return None


def answer_records(questions: dict, rows: list[dict], judgements: dict) -> list[dict]:
    """One record per generated answer, with everything the concerns need."""
    records = []
    for row in rows:
        if "response" not in row:
            continue
        q = questions.get(row["question_id"])
        draft = draft_of(row)
        chunks = context_chunks(row)
        cited = []
        for c in (draft or {}).get("citations", []):
            marker = c.get("marker")
            chunk = (
                chunks[marker - 1]
                if isinstance(marker, int) and 1 <= marker <= len(chunks)
                else None
            )
            cited.append(
                {
                    "marker": marker,
                    "quote": c.get("quote", ""),
                    "quote_ok": bool(chunk)
                    and normalize(c.get("quote", "")) in normalize(chunk["content"]),
                    "document_id": chunk["document_id"] if chunk else None,
                    "pages": (chunk["page_start"], chunk["page_end"])
                    if chunk
                    else None,
                }
            )
        records.append(
            {
                "id": row["question_id"],
                "category": (q or row).get("category", "general"),
                "split": (q or row).get("split", "test"),
                "origin": (q or row).get("origin", "synthetic"),
                "answerable": (q or row).get("answerable", True),
                "state": answer_state(row),
                "problems": (row.get("generation_trace") or {}).get(
                    "grounding_problems", []
                ),
                "draft": (draft or {}).get("answer"),
                "response": (row.get("response") or {}).get("answer", ""),
                "cited": cited,
                "context": [c["content"] for c in chunks],
                "ms": row.get("generation_ms"),
                "gold_pages": gold_pages(q),
                "judgement": judgements.get(row["question_id"]),
            }
        )
    return records


def end_to_end_pass(record: dict) -> bool | None:
    j = record["judgement"]
    if not j:
        return None
    if record["state"] != "shown":
        return False
    if record["answerable"]:
        return j["correct"] == 2 and j["supported"] >= 1
    return j["correct"] == 2


def is_refusal(record: dict) -> bool | None:
    j = record["judgement"]
    if j:
        return j["refused"]
    return (
        None
        if record["draft"] is None
        else normalize(record["draft"]) == normalize(REFUSAL)
    )


def examples_of(records: list[dict], note) -> list[dict]:
    return [{"question_id": r["id"], "note": note(r)} for r in records[:3]]


def judged_note(r: dict) -> str:
    return f"{JUDGE}: {r['judgement']['note']}" if r["judgement"] else ""


# ---------- the concerns ----------


def blocked_answers(records: list[dict]) -> dict:
    how = (
        "Count answers the app's own grounding check rejected, using the model's draft "
        "and the reasons recorded in each run. The judge then grades each blocked draft."
    )
    if not records:
        return not_measured(
            "blocked_answers", "This run made no generated answers.", how
        )
    n = len(records)
    states = Counter(r["state"] for r in records)
    shown, blocked = states["shown"], states["blocked"]
    reasons = Counter(
        p
        for r in records
        if r["state"] == "blocked"
        for p in {normalise_problem(x) for x in r["problems"]}
    )
    drafts = [r for r in records if r["draft"] is not None]
    no_marker = sum(not has_marker(r["draft"]) for r in drafts)
    quotes = [c for r in records for c in r["cited"]]
    judged_blocked = [r for r in records if r["state"] == "blocked" and r["judgement"]]
    good = [r for r in judged_blocked if r["judgement"]["correct"] == 2]
    metrics = [metric("Answers shown to the student", rate_text(shown, n))]
    if states["failed"]:
        metrics.append(
            metric("Model call failed", states["failed"], "No draft exists for these.")
        )
    metrics.append(
        metric(
            "Blocked answers",
            blocked,
            "The student saw a message instead of an answer.",
        )
    )
    metrics += [
        metric(f"Reason: {text}", f"{count} of {blocked} blocked")
        for text, count in reasons.most_common(6)
    ]
    metrics.append(
        metric(
            "Drafts with no [n] marker in the text", rate_text(no_marker, len(drafts))
        )
        if drafts
        else metric(
            "Drafts with no [n] marker in the text", "n/a", "No drafts recorded."
        )
    )
    metrics.append(
        metric(
            "Quotes that were valid",
            rate_text(sum(c["quote_ok"] for c in quotes), len(quotes))
            if quotes
            else "n/a",
            "A valid quote is word for word in the chunk its marker points to.",
        )
    )
    metrics.append(
        metric(
            "Blocked drafts that were fully correct (good answers thrown away)",
            f"{len(good)} of {len(judged_blocked)} judged"
            if judged_blocked
            else "not judged",
            "",
            judged=True,
        )
    )
    blocked_all = [r for r in records if r["state"] == "blocked"]
    status = (
        "measured" if len(judged_blocked) == len(blocked_all) else "partly_measured"
    )
    headline = f"{blocked} of {n} answers were blocked before the student saw them."
    if judged_blocked:
        headline += f" The judge says {len(good)} of {len(judged_blocked)} blocked drafts were fully correct ({JUDGE})."
    examples = examples_of(
        good or [r for r in records if r["state"] == "blocked"],
        lambda r: judged_note(r) or "; ".join(r["problems"][:1]),
    )
    return item(
        "blocked_answers", status, blocked / n, headline, metrics, examples, how
    )


def wrong_answers(records: list[dict]) -> dict:
    how = (
        "A different AI model grades each draft against the reference answer and "
        "required facts: 0 wrong, 1 partly right, 2 every required fact. Answerable questions only."
    )
    judged = [r for r in records if r["judgement"] and r["answerable"]]
    if not judged:
        return not_measured(
            "wrong_answers",
            "No answers were judged yet, so correctness is unknown.",
            how,
        )
    shown = [r for r in judged if r["state"] == "shown"]
    full = lambda rs: sum(r["judgement"]["correct"] == 2 for r in rs)
    spread = Counter(r["judgement"]["correct"] for r in judged)
    metrics = [
        metric(
            "Shown answers fully correct",
            rate_text(full(shown), len(shown)) if shown else "no answer was shown",
            judged=True,
        ),
        metric(
            "All drafts fully correct",
            rate_text(full(judged), len(judged)),
            "Includes blocked drafts.",
            judged=True,
        ),
        metric(
            "Drafts by score (0 / 1 / 2)",
            f"{spread[0]} / {spread[1]} / {spread[2]}",
            judged=True,
        ),
    ]
    sample = shown if len(shown) >= 5 else judged
    bad = 1 - full(sample) / len(sample) if len(sample) >= 5 else None
    status = (
        "measured"
        if len(judged) == len([r for r in records if r["answerable"]])
        else "partly_measured"
    )
    headline = (
        f"{full(judged)} of {len(judged)} drafts were fully correct and {len(shown)} were shown "
        f"({JUDGE})."
    )
    wrong = [r for r in sample if r["judgement"]["correct"] < 2]
    return item(
        "wrong_answers",
        status,
        bad,
        headline,
        metrics,
        examples_of(wrong, judged_note),
        how,
    )


def mechanical_answers(records: list[dict]) -> dict:
    how = (
        "Copy ratio is the share of the answer's 5-word runs found word for word in the chunks "
        "the model saw. Length is counted in words. The judge scores how helpful the answer is."
    )
    drafts = [r for r in records if r["draft"] is not None]
    if not drafts:
        return not_measured(
            "mechanical_answers", "No drafts were recorded in this run.", how
        )

    def block(rs: list[dict], tag: str) -> list[dict]:
        ratios = [
            x
            for x in (copy_ratio(r["draft"], r["context"]) for r in rs)
            if x is not None
        ]
        lengths = [len(words(r["draft"])) for r in rs]
        useful = [r["judgement"]["useful"] for r in rs if r["judgement"]]
        out = [
            metric(
                f"{tag}Median copy ratio",
                pct(percentile(ratios, 50)),
                "Near 100% means a copy of the slide.",
            ),
            metric(
                f"{tag}Median answer length", f"{percentile(lengths, 50):.0f} words"
            ),
            metric(
                f"{tag}Answers under {SHORT_ANSWER_WORDS} words",
                rate_text(sum(n < SHORT_ANSWER_WORDS for n in lengths), len(lengths)),
            ),
        ]
        if useful:
            out.append(
                metric(
                    f"{tag}Judged useful 0 / 1 / 2",
                    " / ".join(str(useful.count(v)) for v in (0, 1, 2)),
                    "0 does not help, 1 flat or mechanical, 2 really helps.",
                    judged=True,
                )
            )
        return out

    metrics = block(drafts, "")
    explain = [r for r in drafts if r["category"] == "explain"]
    metrics += (
        block(explain, "Explain questions: ")
        if explain
        else [metric("Explain questions", "none in this run")]
    )
    judged = [r for r in drafts if r["judgement"]]
    if len(judged) >= 5:
        flat = [r for r in judged if r["judgement"]["useful"] < 2]
        bad = len(flat) / len(judged)
    else:
        flat = [
            r
            for r in drafts
            if len(words(r["draft"])) < SHORT_ANSWER_WORDS
            or (copy_ratio(r["draft"], r["context"]) or 0) >= COPY_HIGH
        ]
        bad = len(flat) / len(drafts)
    status = "measured" if len(judged) == len(drafts) else "partly_measured"
    basis = (
        f"judged not fully helpful ({JUDGE})"
        if len(judged) >= 5
        else "short or copied (no judge yet)"
    )
    headline = f"{len(flat)} of {len(judged) if len(judged) >= 5 else len(drafts)} answers were {basis}."
    return item(
        "mechanical_answers",
        status,
        bad,
        headline,
        metrics,
        examples_of(
            flat, lambda r: judged_note(r) or f"{len(words(r['draft']))} words"
        ),
        how,
    )


def mean_metric(rows: list[dict], key: str) -> float | None:
    return mean([r["metrics"][key] for r in rows if r.get("metrics")])


def retrieval_cell(rows: list[dict]) -> str:
    if not rows:
        return "no questions"
    return f"{len(rows)} questions, Hit@5 {mean_metric(rows, 'hit@5'):.2f}, Recall@5 {mean_metric(rows, 'evidence_recall@5'):.2f}"


def real_wording(rows: list[dict], records: list[dict], questions: dict) -> dict:
    how = (
        "Compare questions written cleanly (dev and test) with the stress questions written the "
        "way students type, using the same pipeline. Retrieval is Hit@5 and Recall@5; "
        "end-to-end is the shown rate and the judged pass rate."
    )
    scored = [r for r in rows if r.get("metrics")]
    if not scored:
        return not_measured(
            "real_wording", "This run has no scored retrieval rows.", how
        )

    def origin(r):
        return (questions.get(r["question_id"]) or r).get("origin", "synthetic")

    def split(r):
        return (questions.get(r["question_id"]) or r).get("split", "test")

    def category(r):
        return (questions.get(r["question_id"]) or r).get("category", "general")

    hybrid = [r for r in scored if r["method"] == "hybrid_rrf"]
    clean = [r for r in hybrid if split(r) != "stress"]
    stress = [r for r in hybrid if split(r) == "stress"]
    metrics = [
        metric("Clean questions, hybrid", retrieval_cell(clean)),
        metric("Stress questions, hybrid", retrieval_cell(stress)),
    ]
    for method in ("vector", "keyword", "hybrid_rrf"):
        for name, test in (
            ("clean", lambda r: split(r) != "stress"),
            ("stress", lambda r: split(r) == "stress"),
        ):
            cell = [r for r in scored if r["method"] == method and test(r)]
            if cell:
                metrics.append(metric(f"{method}, {name}", retrieval_cell(cell)))
    for name in STRESS_CATEGORIES:
        cell = [r for r in hybrid if category(r) == name]
        if cell:
            metrics.append(metric(f"Category {name}, hybrid", retrieval_cell(cell)))
    origins = {origin(r) for r in hybrid}
    if "human" in origins:
        for name in sorted(origins):
            metrics.append(
                metric(
                    f"Written by {name}, hybrid",
                    retrieval_cell([r for r in hybrid if origin(r) == name]),
                )
            )
    for name, group in (
        ("clean", [r for r in records if r["split"] != "stress"]),
        ("stress", [r for r in records if r["split"] == "stress"]),
    ):
        if not group:
            continue
        shown = sum(r["state"] == "shown" for r in group)
        text = f"shown {rate_text(shown, len(group))}"
        passed = [
            end_to_end_pass(r)
            for r in group
            if r["judgement"] and r["answerable"] is not None
        ]
        if passed:
            text += f"; end-to-end pass {sum(passed)}/{len(passed)}"
        metrics.append(
            metric(
                f"End-to-end, {name}",
                text,
                "Pass needs the judge." if not passed else JUDGE,
            )
        )
    if clean and stress:
        gap = mean_metric(clean, "hit@5") - mean_metric(stress, "hit@5")
        headline = f"Hybrid Hit@5 is {mean_metric(clean, 'hit@5'):.2f} on clean questions and {mean_metric(stress, 'hit@5'):.2f} on stress questions."
        status = "measured"
    else:
        gap = None
        headline = "Only one kind of question was in this run, so clean and real wording cannot be compared."
        status = "partly_measured"
    worst = sorted(stress, key=lambda r: r["metrics"]["hit@5"])
    examples = [
        {
            "question_id": r["question_id"],
            "note": f"Hit@5 {r['metrics']['hit@5']:.0f}: {r['question'][:80]}",
        }
        for r in worst
        if r["metrics"]["hit@5"] < 1
    ]
    return item("real_wording", status, gap, headline, metrics, examples, how)


def unanswerable(records: list[dict]) -> dict:
    how = (
        "On questions the notes cannot answer, check the answer says so or corrects the false "
        "premise. On answerable questions, check how often the app refuses anyway. "
        "Uses the judge when available, otherwise the app's own refusal sentence."
    )
    if not records:
        return not_measured("unanswerable", "This run made no generated answers.", how)
    no_answer = [r for r in records if not r["answerable"]]
    has_answer = [r for r in records if r["answerable"]]
    judged = all(r["judgement"] for r in records)

    def handled(r):
        if r["judgement"]:
            return r["state"] == "shown" and r["judgement"]["correct"] == 2
        return r["state"] == "shown" and bool(is_refusal(r))

    ok = [r for r in no_answer if handled(r)]
    false_refusals = [r for r in has_answer if is_refusal(r)]
    metrics = [
        metric(
            "Unanswerable questions handled correctly",
            rate_text(len(ok), len(no_answer))
            if no_answer
            else "no unanswerable questions in this run",
            "Refused, or corrected the false premise.",
            judged=any(r["judgement"] for r in no_answer),
        ),
        metric(
            "Answerable questions refused anyway",
            rate_text(len(false_refusals), len(has_answer)) if has_answer else "n/a",
            judged=any(r["judgement"] for r in has_answer),
        ),
    ]
    bad = 1 - len(ok) / len(no_answer) if no_answer else None
    status = "measured" if no_answer and judged else "partly_measured"
    headline = (
        f"{len(no_answer) - len(ok)} of {len(no_answer)} unanswerable questions got an answer instead of 'I do not know'."
        if no_answer
        else "This run has no unanswerable questions; only false refusals were measured."
    )
    made_up = [r for r in no_answer if not handled(r)]
    return item(
        "unanswerable",
        status,
        bad,
        headline,
        metrics,
        examples_of(
            made_up or false_refusals,
            lambda r: judged_note(r) or (r["draft"] or "")[:100],
        ),
        how,
    )


def weak_citations(records: list[dict]) -> dict:
    how = (
        "For each citation the model wrote, find the chunk its [n] points to and check it is on "
        "a page that holds the gold evidence. The judge also scores whether the quotes back the claims."
    )
    drafts = [r for r in records if r["draft"] is not None]
    cited = [
        (r, c)
        for r in drafts
        if r["answerable"] and r["gold_pages"]
        for c in r["cited"]
    ]
    judged = [r for r in drafts if r["judgement"]]
    if not drafts or not (cited or judged):
        return not_measured(
            "weak_citations",
            "No citations or judged answers to check in this run.",
            how,
        )

    def on_gold(r, c):
        if not c["pages"]:
            return False
        return any(
            doc == c["document_id"] and c["pages"][0] <= page <= c["pages"][1]
            for doc, page in r["gold_pages"]
        )

    off = [(r, c) for r, c in cited if not on_gold(r, c)]
    per_answer = [len(r["cited"]) for r in drafts]
    shown = [len(r["cited"]) for r in drafts if r["state"] == "shown"]
    metrics = [
        metric(
            "Citations not on a gold page",
            rate_text(len(off), len(cited)) if cited else "n/a",
            "Answerable questions with gold evidence only.",
        ),
        metric("Citations per draft (mean)", f"{mean(per_answer):.1f}"),
        metric(
            "Citations per shown answer (mean)",
            f"{mean(shown):.1f}" if shown else "no answer was shown",
        ),
    ]
    if judged:
        support = [r["judgement"]["supported"] for r in judged]
        metrics.append(
            metric(
                "Claims backed by the quotes: 0 / 1 / 2",
                " / ".join(str(support.count(v)) for v in (0, 1, 2)),
                judged=True,
            )
        )
    bad = len(off) / len(cited) if cited else None
    status = "measured" if cited and judged else "partly_measured"
    headline = (
        f"{len(off)} of {len(cited)} citations pointed at a page that is not gold evidence."
        if cited
        else "No citations could be compared with gold pages."
    )
    examples = {}
    for r, c in off:
        gold = ", ".join(f"p{p}" for _, p in sorted(r["gold_pages"]))
        where = f"p{c['pages'][0]}" if c["pages"] else "no chunk"
        examples.setdefault(
            r["id"],
            f"Cited {where}; gold evidence is on {gold}. {judged_note(r)}".strip(),
        )
    return item(
        "weak_citations",
        status,
        bad,
        headline,
        metrics,
        [{"question_id": q, "note": note} for q, note in examples.items()],
        how,
    )


def lost_content(checks: dict | None, questions: dict) -> dict:
    how = (
        "checks.json compares the PDF text with what extraction kept and with what survived "
        "chunking, using the gold quotes. Pages are flagged when little of the PDF's words are kept."
    )
    if not checks or "chunk_evidence_coverage" not in checks:
        return not_measured("lost_content", "This run has no extraction checks.", how)
    group_to_question = {
        g["id"]: q["id"]
        for q in questions.values()
        for g in q.get("evidence_groups", [])
    }
    missing = sorted(
        set(checks.get("missing_after_extraction", []))
        | set(checks.get("not_intact_in_any_chunk", []))
    )
    low = [p for p in checks.get("pages", []) if p["token_recall"] < LOW_TEXT_RECALL]
    metrics = [
        metric(
            "Evidence found after extraction",
            pct(checks.get("extraction_evidence_coverage")),
        ),
        metric(
            "Evidence intact in a chunk",
            pct(checks["chunk_evidence_coverage"]),
            f"{checks.get('required_evidence_groups', '?')} required evidence groups.",
        ),
        metric("Evidence groups missing", ", ".join(missing) or "none"),
        metric(
            f"Pages keeping under {LOW_TEXT_RECALL:.0%} of the PDF words",
            f"{len(low)} of {len(checks.get('pages', []))}",
            ", ".join(
                f"{p['document_id']} p{p['pdf_page']} ({p['token_recall']:.0%})"
                for p in low[:8]
            ),
        ),
    ]
    headline = f"{len(missing)} required evidence group(s) never reached a chunk; {len(low)} page(s) lose much of their text."
    examples = [
        {
            "question_id": group_to_question.get(g, g),
            "note": f"Evidence {g} is lost before chunking.",
        }
        for g in missing
    ]
    return item(
        "lost_content",
        "measured",
        1 - checks["chunk_evidence_coverage"],
        headline,
        metrics,
        examples,
        how,
    )


def bad_metadata(chunks: list[dict], pages: list[dict]) -> dict:
    how = (
        "A heading is stale when its words are not on any PDF page the chunk covers. Also counted: "
        "the most repeated heading, chunks with no heading, very short chunks and chunks per document."
    )
    if not chunks:
        return not_measured("bad_metadata", "This run has no chunks.", how)
    text = {(p["document_id"], p["page_start"]): normalize(p["content"]) for p in pages}
    headed = [c for c in chunks if c.get("heading")]

    def stale(c):
        covered = [
            text.get((c["document_id"], n), "")
            for n in range(c["page_start"], c["page_end"] + 1)
        ]
        return not any(normalize(c["heading"]) in t for t in covered)

    stale_chunks = [c for c in headed if stale(c)] if pages else []
    common = Counter(c["heading"] for c in headed).most_common(1)
    per_doc = Counter(c["document_id"] for c in chunks)
    short = sum(c["token_count"] < SHORT_CHUNK_TOKENS for c in chunks)
    metrics = [
        metric(
            "Headings not on the chunk's pages",
            rate_text(len(stale_chunks), len(headed))
            if pages and headed
            else "no page text to compare",
        ),
        metric(
            "Most repeated heading",
            f"{common[0][0]!r} on {common[0][1]} chunks" if common else "no headings",
        ),
        metric(
            "Chunks with no heading", rate_text(len(chunks) - len(headed), len(chunks))
        ),
        metric(
            f"Chunks under {SHORT_CHUNK_TOKENS} tokens", rate_text(short, len(chunks))
        ),
        metric(
            "Chunks per document",
            ", ".join(f"{d} {n}" for d, n in sorted(per_doc.items())),
        ),
    ]
    status = "measured" if pages and headed else "partly_measured"
    bad = len(stale_chunks) / len(headed) if pages and headed else None
    headline = (
        f"{len(stale_chunks)} of {len(headed)} headed chunks carry a heading that is not on their pages."
        if pages and headed
        else "Chunk shape was counted, but headings could not be compared with the pages."
    )
    examples = [
        {
            "question_id": "",
            "note": f"Chunk {c['chunk_index']} of {c['document_id']} (p{c['page_start']}) says {c['heading']!r}.",
        }
        for c in stale_chunks
    ]
    return item("bad_metadata", status, bad, headline, metrics, examples, how)


def wrong_document(rows: list[dict], questions: dict) -> dict:
    how = (
        "For each answerable question with gold evidence, look at the hybrid results: how often "
        "rank 1 and the top 5 come from a PDF that holds no gold evidence. The two Topic 3 PDFs "
        "may share text, so a hit from the other one is not always a real mistake."
    )
    docs = {s["document_id"] for r in rows for s in r.get("sources", [])}
    if len(docs) < 2:
        return not_measured(
            "wrong_document",
            "This run searched one PDF, so a wrong-PDF answer could not happen.",
            how,
        )
    hybrid = [
        r
        for r in rows
        if r["method"] == "hybrid_rrf"
        and r.get("sources")
        and gold_docs(questions.get(r["question_id"]))
    ]
    if not hybrid:
        return not_measured(
            "wrong_document",
            "No questions with gold evidence were found for this run.",
            how,
        )
    per_doc: dict[str, list[dict]] = {}
    for r in hybrid:
        primary = Counter(
            a["document_id"]
            for g in questions[r["question_id"]]["evidence_groups"]
            for a in g["alternatives"]
        ).most_common(1)[0][0]
        per_doc.setdefault(primary, []).append(r)

    def wrong_share(rs, top):
        total = wrong = 0
        for r in rs:
            gold = gold_docs(questions[r["question_id"]])
            for s in r["sources"][:top]:
                total += 1
                wrong += s["document_id"] not in gold
        return wrong, total

    metrics = []
    for doc, rs in sorted(per_doc.items()):
        w1, t1 = wrong_share(rs, 1)
        w5, t5 = wrong_share(rs, 5)
        metrics.append(
            metric(
                f"Gold PDF {doc}: rank 1 from another PDF",
                rate_text(w1, t1),
                f"Top 5: {w5}/{t5} results from another PDF.",
            )
        )
    topic3 = {"cpt316-topic3-student", "cpt316-topic3-updated"}
    swaps = [
        r
        for r in hybrid
        if gold_docs(questions[r["question_id"]]) & topic3
        and r["sources"][0]["document_id"]
        in topic3 - gold_docs(questions[r["question_id"]])
    ]
    metrics.append(
        metric(
            "Rank 1 from the other Topic 3 PDF",
            str(len(swaps)),
            "The two Topic 3 PDFs may overlap, so check these by hand.",
        )
    )
    w1, t1 = wrong_share(hybrid, 1)
    examples = [
        {
            "question_id": r["question_id"],
            "note": f"Rank 1 came from {r['sources'][0]['document_id']}.",
        }
        for r in hybrid
        if r["sources"][0]["document_id"] not in gold_docs(questions[r["question_id"]])
    ]
    headline = (
        f"{w1} of {t1} questions had a rank-1 result from a PDF with no gold evidence."
    )
    return item("wrong_document", "measured", w1 / t1, headline, metrics, examples, how)


def slow_answers(records: list[dict]) -> dict:
    how = (
        "Time from question to answer for each generated answer. This includes any waiting on "
        "Groq rate limits, so a slow run may be slow because of the limit and not the app."
    )
    times = [r["ms"] for r in records if r["ms"] is not None]
    if not times:
        return not_measured("slow_answers", "No generation times in this run.", how)
    over = sum(t > LONG_WAIT_MS for t in times)
    metrics = [
        metric("Median time", f"{percentile(times, 50) / 1000:.1f} s"),
        metric("Slowest 5% (p95)", f"{percentile(times, 95) / 1000:.1f} s"),
        metric(
            "Answers over 10 s",
            rate_text(over, len(times)),
            "Includes waiting on Groq rate limits.",
        ),
    ]
    slow = sorted(
        (r for r in records if r["ms"] and r["ms"] > LONG_WAIT_MS),
        key=lambda r: -r["ms"],
    )
    headline = f"Median wait was {percentile(times, 50) / 1000:.1f} s and {over} of {len(times)} answers took over 10 s."
    return item(
        "slow_answers",
        "measured",
        over / len(times),
        headline,
        metrics,
        examples_of(slow, lambda r: f"{r['ms'] / 1000:.1f} s"),
        how,
    )


def random_retriever_baseline(
    chunks: list[dict],
    questions: list[dict],
    k: int = 5,
    trials: int = 300,
    seed: int = 37,
) -> dict | None:
    """Hit@5 and Recall@5 when 5 chunks are picked at random."""
    usable = [
        q for q in questions if q.get("answerable", True) and q.get("evidence_groups")
    ]
    if not usable or len(chunks) < k:
        return None
    matches = [
        [
            {
                i
                for i, c in enumerate(chunks)
                if any(evidence_matches(c, a) for a in g["alternatives"])
            }
            for g in q["evidence_groups"]
        ]
        for q in usable
    ]
    rng = random.Random(seed)
    hits = recalls = 0.0
    for _ in range(trials):
        pick = set(rng.sample(range(len(chunks)), k))
        for groups in matches:
            found = sum(bool(g & pick) for g in groups)
            hits += found > 0
            recalls += found / len(groups)
    total = trials * len(usable)
    return {
        "hit@5": hits / total,
        "evidence_recall@5": recalls / total,
        "questions": len(usable),
    }


def metric_trust(
    records: list[dict],
    questions: dict,
    chunks: list[dict],
    controls: list[dict],
    retrieved_ids: set[str],
) -> dict:
    how = (
        "Counts questions by origin and review status, the 95% range on the end-to-end pass "
        "rate, what one question is worth, a random-chunk baseline and the judge's own controls."
    )
    in_run = [questions[i] for i in sorted(retrieved_ids) if i in questions]
    if not in_run and not records:
        return not_measured(
            "metric_trust", "No questions could be matched to this run.", how
        )
    metrics = []
    by_origin: dict[str, list[dict]] = {}
    for q in in_run:
        by_origin.setdefault(q.get("origin", "synthetic"), []).append(q)
    for name, qs in sorted(by_origin.items()):
        metrics.append(
            metric(
                f"Questions written by {name}",
                f"{len(qs)}",
                f"{sum(bool(q.get('verified')) for q in qs)} verified by a human.",
            )
        )
    judged = [r for r in records if r["judgement"]]
    bad, headline = (
        None,
        "The end-to-end pass rate needs the judge, so it is not known yet.",
    )
    if judged:
        passed = sum(end_to_end_pass(r) for r in judged)
        low, high = wilson_interval(passed, len(judged))
        bad = high - low
        metrics.append(
            metric(
                "End-to-end pass",
                rate_text(passed, len(judged)),
                "Shown, correct 2 and supported 1 or more; or a correct refusal.",
                judged=True,
            )
        )
        headline = f"End-to-end pass is {pct(passed / len(judged))} but the 95% range is {pct(low)} to {pct(high)} ({JUDGE})."
    n = len(records) or len(in_run)
    if n:
        metrics.append(
            metric(
                "One question is worth", f"{100 / n:.1f} points", f"On {n} questions."
            )
        )
    base = random_retriever_baseline(chunks, in_run)
    if base:
        metrics.append(
            metric(
                "Random retriever, Hit@5",
                f"{base['hit@5']:.2f}",
                f"Recall@5 {base['evidence_recall@5']:.2f}; 5 random chunks, 300 trials, seed 37, {base['questions']} questions.",
            )
        )
    if controls:
        passed = sum(c["passed"] for c in controls)
        metrics.append(
            metric(
                "Judge control checks passed",
                rate_text(passed, len(controls)),
                "Half use the true answer (expect correct 1 or 2), half a different question's answer (expect 0).",
                judged=True,
            )
        )
    else:
        metrics.append(
            metric(
                "Judge control checks",
                "not run",
                "Run with --controls to test the judge.",
            )
        )
    status = "measured" if judged and controls else "partly_measured"
    return item("metric_trust", status, bad, headline, metrics, [], how)


def follow_ups() -> dict:
    return not_measured(
        "follow_ups",
        "Not measured. The harness asks one question at a time.",
        "Nothing measures this yet. A test would need two-turn conversations such as 'what about the second one?'.",
    )


def clean_pdfs() -> dict:
    return not_measured(
        "clean_pdfs",
        "Not measured. The test PDFs are text transcriptions.",
        "Real slides carry images and diagrams, so extraction scores here may be too high. "
        "A test needs a few real, untouched slide PDFs.",
    )


def filtered_search(extra: dict | None = None) -> dict:
    base = not_measured(
        "filtered_search",
        "Not measured. The test database is almost empty.",
        "Vector search filters by file. In a large shared table an approximate index may return "
        "too few rows. This needs a large database to show.",
    )
    return {**base, **extra} if extra else base


def build_concerns(run_id: str, data: dict) -> dict:
    """data: questions (id -> row), rows, judgements, controls, chunks, pages, checks, extra."""
    questions, rows = data["questions"], data["rows"]
    records = answer_records(questions, rows, data.get("judgements", {}))
    retrieved = {r["question_id"] for r in rows}
    items = [
        blocked_answers(records),
        wrong_answers(records),
        mechanical_answers(records),
        real_wording(rows, records, questions),
        unanswerable(records),
        weak_citations(records),
        lost_content(data.get("checks"), questions),
        bad_metadata(data.get("chunks", []), data.get("pages", [])),
        wrong_document(rows, questions),
        slow_answers(records),
        metric_trust(
            records,
            questions,
            data.get("chunks", []),
            data.get("controls", []),
            retrieved,
        ),
        follow_ups(),
        clean_pdfs(),
        filtered_search(data.get("filtered_search")),
    ]
    return {"run_id": run_id, "items": items}
