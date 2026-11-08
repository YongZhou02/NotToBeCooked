import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import playground.toolkit  # noqa: F401,E402  (puts apps/api on the path)
from playground.toolkit.citation import (  # noqa: E402
    auto_marker, insert_markers, marker_styles, prod_check, quote_only, rewrite_marker_styles,
)
from playground.toolkit.trace import Trace  # noqa: E402

PAGE = ("The numbered list names 3 kinds of translators: (1) Compiler, (2) Interpreter, "
        "(3) Assembler. A pass is one complete scan through the program.")
SOURCES = [{"filename": "notes.pdf", "page_start": 4, "page_end": 4, "content": PAGE}]
GOOD = [{"marker": 1, "quote": "A pass is one complete scan through the program."}]
FAKE = [{"marker": 1, "quote": "A pass is two scans through the program."}]
VARIANTS = (prod_check, marker_styles, quote_only, auto_marker)


def test_prod_blocks_a_missing_marker_and_passes_a_marked_answer():
    assert prod_check("A pass is one scan.", GOOD, SOURCES)["problems"] == [
        "citation [1] is listed but never referred to in the answer"]
    assert prod_check("A pass is one scan [1].", GOOD, SOURCES)["ok"]


def test_prod_follows_production_marker_numbering():
    two = SOURCES + [{"filename": "b.pdf", "content": "Other text."}]
    wrong = [{"marker": 2, "quote": "A pass is one complete scan through the program."}]
    out = prod_check("A pass is one scan [2].", wrong, two)
    assert not out["ok"] and "does not appear" in out["problems"][0]


def test_fullwidth_markers_are_rewritten():
    out = marker_styles("A pass is one scan【1】.", GOOD, SOURCES)
    assert out["ok"] and out["answer"] == "A pass is one scan[1]." and out["changed"]


def test_bracket_pair_only_matters_when_listed():
    text, changes = rewrite_marker_styles("Seen【9】.", {1})
    assert text == "Seen[9]." and changes  # still fails prod later: 9 is not listed
    assert not marker_styles("Seen【9】.", GOOD, SOURCES)["ok"]


def test_paren_number_after_a_claim_is_a_citation():
    out = marker_styles("A pass is one complete scan (1).", GOOD, SOURCES)
    assert out["ok"] and out["answer"].endswith("scan [1].")


def test_list_numbering_is_not_a_citation():
    answer = "The kinds are (1) Compiler, (2) Interpreter and (3) Assembler."
    cites = [{"marker": 1, "quote": "(1) Compiler, (2) Interpreter, (3) Assembler."}]
    text, changes = rewrite_marker_styles(answer, {1, 2, 3})
    assert text == answer and not changes
    assert not marker_styles(answer, cites, SOURCES)["ok"]  # still no real marker


def test_list_item_at_line_start_and_repeated_number_are_not_citations():
    text, changes = rewrite_marker_styles("Steps:\n(1) Scan the program.\nIt ends here (1).", {1})
    assert not changes and text.startswith("Steps")


def test_name_with_number_is_not_a_citation():
    text, changes = rewrite_marker_styles("The grammar is not LL(1).", {1})
    assert not changes and text == "The grammar is not LL(1)."


def test_quote_only_ignores_only_the_missing_marker():
    out = quote_only("A pass is one scan.", GOOD, SOURCES)
    assert out["ok"] and out["answer"] == "A pass is one scan." and out["changed"]
    # an unlisted marker still blocks
    assert not quote_only("A pass is one scan [3].", GOOD, SOURCES)["ok"]
    # a repeated quote still blocks
    assert not quote_only("A pass is one scan.", GOOD + GOOD, SOURCES)["ok"]
    # uncovered claim with nothing cited still blocks
    assert not quote_only("No idea.", [], SOURCES, uncovered="the rest")["ok"]


def test_auto_marker_picks_the_best_sentence():
    answer = "Translators come in kinds. A pass is one complete scan through the program. Done."
    text, placed = insert_markers(answer, GOOD)
    assert text == ("Translators come in kinds. A pass is one complete scan through the program [1]. Done.")
    assert placed[0]["marker"] == 1 and placed[0]["sentence"].startswith("A pass is one")
    out = auto_marker(answer, GOOD, SOURCES)
    assert out["ok"] and out["answer"] == text and out["changes"][0]["marker"] == 1


def test_auto_marker_bullets_and_no_overlap():
    answer = "- **Pass**: one scan\n- **Other**: unrelated words"
    out = auto_marker(answer, GOOD, SOURCES)
    assert out["ok"] and out["answer"].splitlines()[0].endswith("one scan [1]")
    nothing, placed = insert_markers("Zzz qqq.", GOOD)
    assert nothing == "Zzz qqq." and not placed


def test_an_answer_prod_accepts_is_returned_unchanged():
    for variant in VARIANTS:
        out = variant("A pass is one scan [1].", GOOD, SOURCES)
        assert out["ok"] and out["answer"] == "A pass is one scan [1]." and not out["changed"]


def test_a_fake_quote_stays_blocked_in_every_variant():
    for answer in ("A pass is two scans.", "A pass is two scans [1].", "A pass is two scans (1)."):
        for variant in VARIANTS:
            out = variant(answer, FAKE, SOURCES)
            assert not out["ok"], (variant.__name__, answer)
            assert any("does not appear" in p for p in out["problems"])


def test_a_refusal_stays_a_refusal():
    for variant in VARIANTS:
        assert variant("The notes do not cover this.", [], SOURCES)["ok"]


def test_variants_are_traced():
    with Trace() as trace:
        auto_marker("A pass is one scan.", GOOD, SOURCES)
    assert "citation.auto_marker" in [s["step"] for s in trace.steps]
