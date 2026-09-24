"""Every case here is a way an answer can look right and be wrong."""

from uuid import uuid4

from app.schemas.rag import Citation, RetrievedChunk
from app.services.grounding import (
    check_grounding,
    drop_unreferenced,
    drop_unverified,
    extract_markers,
)

COURSE_ID = uuid4()

# The line break in the first chunk is load-bearing: it is what a quote spanning
# a PDF's wrap looks like, and it is the reason _normalise exists.
C1 = RetrievedChunk(
    chunk_id=uuid4(), file_id=uuid4(), course_id=COURSE_ID, filename="A.pdf",
    page_start=1, page_end=1, heading=None, score=0.9,
    content="Photosynthesis converts light energy\ninto chemical energy stored in glucose.",
)
C2 = RetrievedChunk(
    chunk_id=uuid4(), file_id=uuid4(), course_id=COURSE_ID, filename="B.pdf",
    page_start=2, page_end=2, heading=None, score=0.8,
    content="The Calvin cycle fixes carbon dioxide into glucose.",
)
C3 = RetrievedChunk(
    chunk_id=uuid4(), file_id=uuid4(), course_id=COURSE_ID, filename="C.pdf",
    page_start=3, page_end=3, heading=None, score=0.7,
    content="Chlorophyll absorbs light most strongly in the blue and red bands.",
)
SELECTED = [C1, C2, C3]


def cite(marker: int, source: RetrievedChunk, quote: str) -> Citation:
    return Citation(
        marker=marker, file_id=source.file_id, course_id=source.course_id,
        filename=source.filename, page=source.page_start, quote=quote,
    )


def test_extract_markers_ignores_markdown_links():
    answer = "See [1] and [2], but not [this link](https://example.test) or [x]."
    assert extract_markers(answer) == {1, 2}


def test_a_consistent_answer_passes():
    report = check_grounding(
        answer="Plants turn light into chemical energy [1]. Carbon is fixed later [2].",
        citations=[
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(2, C2, "fixes carbon dioxide into glucose"),
        ],
        selected=SELECTED,
    )
    assert report.ok, report.problems


def test_marker_in_the_answer_with_no_citation_behind_it_fails():
    """The pill the reader clicks resolves to nothing."""
    report = check_grounding(
        answer="Light is captured [1], carbon is fixed [2], and pigments matter [3].",
        citations=[
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(2, C2, "fixes carbon dioxide into glucose"),
        ],
        selected=SELECTED,
    )
    assert not report.ok
    assert any("[3]" in p for p in report.problems)


def test_citation_never_referred_to_in_the_answer_fails():
    """A source the reader is told was used, and cannot locate."""
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(2, C2, "fixes carbon dioxide into glucose"),
        ],
        selected=SELECTED,
    )
    assert not report.ok
    assert any("[2]" in p for p in report.problems)


def test_an_unreferenced_citation_is_dropped_and_the_rest_then_passes():
    """The same answer as above. Nothing the reader sees rested on [2]."""
    answer = "Plants turn light into chemical energy [1]."
    kept, dropped = drop_unreferenced(
        answer,
        [
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(2, C2, "fixes carbon dioxide into glucose"),
        ],
    )
    assert [c.marker for c in kept] == [1]
    assert dropped == [2]
    assert check_grounding(answer, kept, SELECTED).ok


def test_dropping_never_rescues_a_bad_quote_on_a_marker_the_answer_uses():
    answer = "Plants turn light into chemical energy [1]."
    kept, _ = drop_unreferenced(answer, [cite(1, C1, "Photosynthesis never converts light")])
    report = check_grounding(answer, kept, SELECTED)
    assert not report.ok
    # The rejected quote is in the message, because the log is built from it.
    assert any("Photosynthesis never converts light" in p for p in report.problems)


def test_an_answer_with_no_markers_keeps_its_citations():
    """Dropping them all would make uncited prose look like a refusal."""
    citations = [cite(1, C1, "Photosynthesis converts light energy")]
    kept, dropped = drop_unreferenced("Plants turn light into chemical energy.", citations)
    assert kept == citations
    assert dropped == []
    assert not check_grounding("Plants turn light into chemical energy.", kept, SELECTED).ok


def test_a_failed_quote_goes_when_its_marker_keeps_a_verified_one():
    """[1] still leads to a line the reader can find, so the bad quote goes."""
    answer = "Plants turn light into chemical energy [1]."
    good = cite(1, C1, "Photosynthesis converts light energy")
    bad = cite(1, C1, "Photosynthesis never converts light")
    kept, dropped = drop_unverified([good, bad], SELECTED)
    assert kept == [good]
    assert dropped == [bad]
    assert check_grounding(answer, kept, SELECTED).ok


def test_a_marker_whose_quotes_all_fail_is_not_rescued():
    """Nothing behind [1] was checked, so the whole answer still fails."""
    answer = "Plants turn light into chemical energy [1]. Carbon is fixed later [2]."
    citations = [
        cite(1, C1, "Photosynthesis never converts light"),
        cite(2, C2, "fixes carbon dioxide into glucose"),
    ]
    kept, dropped = drop_unverified(citations, SELECTED)
    assert kept == citations
    assert dropped == []
    assert not check_grounding(answer, kept, SELECTED).ok


def test_a_verified_quote_under_another_marker_rescues_nothing():
    """[2] holding says nothing about [1]."""
    citations = [
        cite(1, C1, "Photosynthesis never converts light"),
        cite(2, C2, "fixes carbon dioxide into glucose"),
    ]
    _, dropped = drop_unverified(citations, SELECTED)
    assert dropped == []


def test_marker_outside_the_supplied_sources_fails():
    report = check_grounding(
        answer="Pigments absorb light [4].",
        citations=[cite(4, C3, "Chlorophyll absorbs light")],
        selected=SELECTED,
    )
    assert not report.ok
    assert any("outside" in p for p in report.problems)


def test_one_changed_word_fails():
    """power, not energy. Nothing else differs."""
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[cite(1, C1, "Photosynthesis converts light power")],
        selected=SELECTED,
    )
    assert not report.ok


def test_a_real_quote_under_the_wrong_marker_fails():
    """The sharp one.

    This sentence exists, word for word, in C2. It is cited as [1]. An
    implementation that asks "is this quote in any source" passes every other
    test in this file and sends the reader to the wrong document here.
    """
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[cite(1, C1, "fixes carbon dioxide into glucose")],
        selected=SELECTED,
    )
    assert not report.ok
    assert any("does not appear in the source it points at" in p for p in report.problems)


def test_a_quote_spanning_a_line_break_in_the_source_passes():
    """Where the PDF wrapped is not evidence about the model."""
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[cite(1, C1, "converts light energy into chemical energy")],
        selected=SELECTED,
    )
    assert report.ok, report.problems


def test_one_source_may_carry_two_different_quotes():
    """`marker` names a source, not a citation slot.

    Measured 6 Sep 2026 against Gemini: asked for one-sentence quotes, it
    returned two, both under [1], one per claim. That is correct citation
    behaviour and the check must not reject it.
    """
    report = check_grounding(
        answer="Light becomes chemical energy [1], and it is stored in glucose [1].",
        citations=[
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(1, C1, "chemical energy stored in glucose"),
        ],
        selected=SELECTED,
    )
    assert report.ok, report.problems


def test_the_same_quote_listed_twice_fails():
    """A repeat carries no second piece of evidence."""
    report = check_grounding(
        answer="Light becomes chemical energy [1], and that is the point [1].",
        citations=[
            cite(1, C1, "Photosynthesis converts light energy"),
            cite(1, C1, "Photosynthesis  converts   light energy"),
        ],
        selected=SELECTED,
    )
    assert not report.ok
    assert any("repeats a quote" in p for p in report.problems)


def test_a_refusal_is_not_a_grounding_failure():
    """No markers, no citations. prompt.py asks for exactly this when the
    sources do not cover the question, and it must not read as a defect."""
    report = check_grounding(
        answer="The supplied material does not cover this question.",
        citations=[],
        selected=SELECTED,
    )
    assert report.ok, report.problems


# --- r47: the answer's own claim about what it did not cover -------------------
#
# None of these can be checked against the truth -- whether the material really
# left something out needs the right answer, which is the one thing this system
# does not have. What they check is whether the answer contradicts itself.


def test_a_partial_answer_that_names_the_gap_passes():
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[cite(1, C1, "Photosynthesis converts light energy")],
        selected=SELECTED,
        uncovered="The sources do not say how the light reactions are regulated.",
    )
    assert report.ok, report.problems


def test_a_declared_gap_with_nothing_in_it_fails():
    """"Part of this is missing" and then no word about which part."""
    report = check_grounding(
        answer="Plants turn light into chemical energy [1].",
        citations=[cite(1, C1, "Photosynthesis converts light energy")],
        selected=SELECTED,
        uncovered="   ",
    )
    assert not report.ok
    assert any("does not name it" in p for p in report.problems)


def test_a_declared_gap_with_no_citations_fails():
    """"The sources cover half of this" and "none of this came from the sources"
    cannot both be true. The marker checks above pass here, because both lists
    are empty and so they agree -- this is the one that catches it."""
    report = check_grounding(
        answer="Plants turn light into chemical energy.",
        citations=[],
        selected=SELECTED,
        uncovered="The sources do not cover the Calvin cycle.",
    )
    assert not report.ok
    assert any("cites none of them" in p for p in report.problems)


def test_an_answer_with_no_claim_about_coverage_is_unchanged():
    """The default keeps every pre-r47 caller meaning what it meant."""
    report = check_grounding(
        answer="The supplied material does not cover this question.",
        citations=[],
        selected=SELECTED,
    )
    assert report.ok, report.problems
