"""Citation checks: the real production check, and three looser variants to try.

Every function takes the model's draft in plain form and returns one "report":

    answer       the text the student would see if the draft is shown
    ok           True when the draft would be shown
    problems     the reasons it was blocked (empty when ok)
    citations    the citations that survived the production clean-up steps
    changed      True when the variant altered the answer text or the verdict
    changes      what exactly it altered (empty for prod)

Inputs:
    answer       the model's answer text
    citations    [{"marker": 1, "quote": "..."}, ...]
    sources      the chunks that were put in the prompt, in prompt order
                 (dicts with content, filename, page_start, ... as saved in a run)
    uncovered    the model's "uncovered" sentence, or None

Nothing here calls a model. The one rule no variant relaxes: a quote has to be
found, word for word, on the source its marker names. That test is the real
`check_grounding` in every variant, never a copy of it.
"""

from __future__ import annotations

import re
from typing import Any

from .trace import traced

# Fields of RetrievedChunk (the saved run rows carry extras such as `rank`).
_CHUNK_FIELDS = (
    "chunk_id", "file_id", "course_id", "filename", "page_start", "page_end",
    "heading", "content", "score",
)
_NIL = "00000000-0000-0000-0000-000000000000"

_NEVER_REFERRED = re.compile(r"^citation \[\d+\] is listed but never referred to in the answer$")


def _chunks(sources: list[dict]) -> list[Any]:
    from app.schemas.rag import RetrievedChunk

    rows = []
    for source in sources:
        row = {k: source[k] for k in _CHUNK_FIELDS if k in source}
        for key in ("chunk_id", "file_id", "course_id"):
            row.setdefault(key, _NIL)
        row.setdefault("score", 0.0)
        rows.append(RetrievedChunk(**row))
    return rows


def _report(answer: str, ok: bool, problems: list[str], citations: list[dict],
            changes: list[Any]) -> dict:
    return {
        "answer": answer,
        "ok": ok,
        "problems": problems,
        "citations": citations,
        "changed": bool(changes),
        "changes": changes,
    }


def _prod(answer: str, citations: list[dict], sources: list[dict],
          uncovered: str | None = None) -> dict:
    """The production steps, in the order apps/api/app/routers/rag.py runs them:
    build_context -> _resolve_citations -> drop_unreferenced -> drop_unverified ->
    check_grounding. All five are the real functions."""
    from app.routers.rag import _resolve_citations
    from app.services.grounding import check_grounding, drop_unreferenced, drop_unverified
    from app.services.llm import LlmCitation
    from app.services.prompt import build_context

    _, selected = build_context(_chunks(sources), max_sources=8)
    drafted = [LlmCitation(marker=c["marker"], quote=c["quote"]) for c in citations]
    resolved = _resolve_citations(drafted, selected)
    resolved, dropped = drop_unreferenced(answer, resolved)
    resolved, unverified = drop_unverified(resolved, selected)
    report = check_grounding(answer, resolved, selected, uncovered=uncovered)
    out = _report(answer, report.ok, report.problems,
                  [{"marker": c.marker, "quote": c.quote} for c in resolved], [])
    out["dropped_unreferenced"] = dropped
    out["dropped_unverified"] = [{"marker": c.marker, "quote": c.quote} for c in unverified]
    return out


@traced("citation.prod_check")
def prod_check(answer: str, citations: list[dict], sources: list[dict],
               uncovered: str | None = None) -> dict:
    """What production does: the real clean-up steps and the real check_grounding."""
    return _prod(answer, citations, sources, uncovered)


# --- a. other marker styles ---------------------------------------------------

_FULLWIDTH = re.compile(r"[【［\[]\s*(\d+)\s*[】］\]]")
_PAREN = re.compile(r"\((\d+)\)")


def _is_list_number(text: str, match: re.Match) -> bool:
    """Is this "(n)" the number of a list item, not a citation?

    List numbering looks like "(1) Compiler, (2) Interpreter": the number comes
    first and a word follows it. A citation comes last: the number follows the
    claim and punctuation, the end of the line or another marker follows it.
    So "(n)" counts as list numbering when it
      - starts a line (after spaces or a bullet "-", "*", "•"), or
      - is followed, on the same line, by a letter or digit.
    """
    start, end = match.span()
    line_start = text.rfind("\n", 0, start) + 1
    if re.fullmatch(r"\s*(?:[-*•]\s*)?", text[line_start:start]):
        return True
    line_end = text.find("\n", end)
    rest = text[end: len(text) if line_end == -1 else line_end]
    return bool(re.match(r"\s*[A-Za-z0-9]", rest))


def rewrite_marker_styles(answer: str, listed: set[int]) -> tuple[str, list[str]]:
    """Rewrite other marker styles to [n]. Returns the new text and what changed.

    Rule 1: fullwidth brackets 【n】 and ［n］ (also with fullwidth digits) always
    become [n]. Nobody writes these brackets for any other purpose, and a number
    that is not listed still fails the production check ("cites [n] but no
    citation carries that marker").

    Rule 2: "(n)" becomes [n] only when ALL hold:
      - n is the number of a listed citation (otherwise it is just a number);
      - it does not touch the word before it ("LL(1)", "f(1)" are names, not citations);
      - this "(n)" is not list numbering (see _is_list_number);
      - the same n is not used for list numbering anywhere else in the answer
        (if "(1) Compiler" is a list item, a later "(1)" is read the same way).
    The rule is deliberately cautious. A missed citation leaves the answer
    blocked, as today. A wrongly rewritten list number would invent a citation.
    """
    changes: list[str] = []

    def fullwidth(match: re.Match) -> str:
        whole = match.group(0)
        if whole.startswith("[") and whole.endswith("]"):
            return whole
        number = int(match.group(1))
        changes.append(f"{whole} -> [{number}]")
        return f"[{number}]"

    text = _FULLWIDTH.sub(fullwidth, answer)

    list_numbers = {int(m.group(1)) for m in _PAREN.finditer(text) if _is_list_number(text, m)}

    def paren(match: re.Match) -> str:
        number = int(match.group(1))
        glued = match.start() > 0 and text[match.start() - 1].isalnum()
        if number in listed and number not in list_numbers and not glued:
            changes.append(f"({number}) -> [{number}]")
            return f"[{number}]"
        return match.group(0)

    return _PAREN.sub(paren, text), changes


@traced("citation.marker_styles")
def marker_styles(answer: str, citations: list[dict], sources: list[dict],
                  uncovered: str | None = None) -> dict:
    """Rewrite 【n】, ［n］ and safe "(n)" to [n], then run the unchanged prod check."""
    base = _prod(answer, citations, sources, uncovered)
    if base["ok"]:
        return base
    new_answer, changes = rewrite_marker_styles(answer, {c["marker"] for c in citations})
    if not changes:
        return base
    again = _prod(new_answer, citations, sources, uncovered)
    again["changes"], again["changed"] = changes, True
    return again


# --- b. quote only --------------------------------------------------------------

@traced("citation.quote_only")
def quote_only(answer: str, citations: list[dict], sources: list[dict],
               uncovered: str | None = None) -> dict:
    """Show the draft when every quote is on its source. The only problem ignored is
    "citation [n] is listed but never referred to in the answer"; every other
    production rule (bad quote, unlisted marker, duplicate quote, range, uncovered
    rules) still blocks. The text is shown as written, markers or not."""
    base = _prod(answer, citations, sources, uncovered)
    if base["ok"]:
        return base
    kept = [p for p in base["problems"] if not _NEVER_REFERRED.match(p)]
    ignored = [p for p in base["problems"] if _NEVER_REFERRED.match(p)]
    if kept or not ignored:
        return base
    out = dict(base)
    out.update(ok=True, problems=[], changed=True, changes=[f"ignored: {p}" for p in ignored])
    return out


# --- c. auto marker -------------------------------------------------------------

_STOP = frozenset(
    "a an the of in on at to for and or is are was were be been being it its this that these "
    "those as by with from which who what when how not no can may will than then also into "
    "such has have had do does".split()
)
_SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.casefold()) if t not in _STOP and len(t) > 1}


def _sentence_spans(answer: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence; each line (a bullet, a heading) is split on its own."""
    spans = []
    offset = 0
    for line in answer.split("\n"):
        for match in _SENTENCE.finditer(line):
            text = match.group(0)
            if text.strip():
                strip_left = len(text) - len(text.lstrip())
                spans.append((offset + match.start() + strip_left,
                              offset + match.start() + len(text.rstrip())))
        offset += len(line) + 1
    return spans


def _best_sentence(answer: str, quote: str) -> tuple[int, float] | None:
    """Index of the sentence that best matches the quote, with its score, or None.

    Score is the F1 of word overlap (stop words ignored). Ties go to the earlier
    sentence. No shared word at all means no match."""
    wanted = _tokens(quote)
    best: tuple[int, float] | None = None
    for index, (start, end) in enumerate(_sentence_spans(answer)):
        have = _tokens(answer[start:end])
        shared = len(wanted & have)
        if not shared:
            continue
        precision, recall = shared / len(have), shared / len(wanted)
        score = 2 * precision * recall / (precision + recall)
        if best is None or score > best[1] + 1e-12:
            best = (index, score)
    return best


def insert_markers(answer: str, citations: list[dict]) -> tuple[str, list[dict]]:
    """Add [n] for every listed marker the answer never writes.

    The marker goes at the end of the best-matching sentence, before its final
    full stop, like "... is a program [1]." Returns the new text and, for each
    marker placed, {"marker", "sentence", "quote", "score"}."""
    from app.services.grounding import extract_markers

    present = extract_markers(answer)
    spans = _sentence_spans(answer)
    placed: list[dict] = []
    wanted: dict[int, list[int]] = {}
    for citation in citations:
        if citation["marker"] in present:
            continue
        match = _best_sentence(answer, citation["quote"])
        if match is None:
            continue
        index, score = match
        if citation["marker"] not in wanted.setdefault(index, []):
            wanted[index].append(citation["marker"])
            placed.append({"marker": citation["marker"], "sentence": answer[spans[index][0]:spans[index][1]],
                           "quote": citation["quote"], "score": round(score, 3)})
    text = answer
    for index in sorted(wanted, reverse=True):  # right to left keeps earlier spans valid
        start, end = spans[index]
        sentence = text[start:end]
        tail = re.search(r"[.!?]+$", sentence)
        cut = end - len(tail.group(0)) if tail else end
        tags = " ".join(f"[{m}]" for m in sorted(wanted[index]))
        text = text[:cut] + " " + tags + text[cut:]
    return text, placed


@traced("citation.auto_marker")
def auto_marker(answer: str, citations: list[dict], sources: list[dict],
                uncovered: str | None = None) -> dict:
    """Insert [n] after the sentence that best matches each unreferenced quote, then
    run the unchanged prod check. `changes` lists which sentence got which marker."""
    base = _prod(answer, citations, sources, uncovered)
    if base["ok"]:
        return base
    new_answer, placed = insert_markers(answer, citations)
    if not placed:
        return base
    again = _prod(new_answer, citations, sources, uncovered)
    again["changes"], again["changed"] = placed, True
    return again


VARIANTS = {
    "prod": prod_check,
    "marker_styles": marker_styles,
    "quote_only": quote_only,
    "auto_marker": auto_marker,
}
