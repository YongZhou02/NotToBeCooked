"""create_chunk's boundaries -- the two rules added after the 10 Oct production test.

Token counting is replaced by a word count so the tests need no model; the
rules under test are about where chunks start, not how tokens are counted.
"""

from uuid import uuid4

import pytest

from app.services import ingestion
from app.services.ingestion import create_chunk


@pytest.fixture(autouse=True)
def _word_tokens(monkeypatch):
    monkeypatch.setattr(ingestion, "count_token", lambda text: len(text.split()))


def item(page: int, content: str, heading: str | None = "Syntax") -> dict:
    return {"heading": heading, "page_start": page, "page_end": page, "content": content}


def test_a_new_page_starts_a_new_chunk_even_under_the_same_heading():
    chunks = create_chunk(
        [item(18, "Syntax deals with sentences."), item(19, "A grammar is rules.")], uuid4()
    )
    assert [(c.page_start, c.page_end) for c in chunks] == [(18, 18), (19, 19)]


def test_items_on_the_same_page_stay_together():
    chunks = create_chunk([item(7, "Spelling checkers."), item(7, "Machine translation.")], uuid4())
    assert len(chunks) == 1
    assert chunks[0].content.endswith("Spelling checkers. Machine translation.")


def test_the_heading_is_the_first_line_of_the_searchable_text():
    # The slide's list never says "application"; only its title does.
    chunks = create_chunk(
        [item(7, "Spelling and grammar checkers.", heading="Applications of Language Processing")],
        uuid4(),
    )
    assert (
        chunks[0].content == "Applications of Language Processing\nSpelling and grammar checkers."
    )
    assert chunks[0].heading == "Applications of Language Processing"


def test_no_heading_means_no_prefix():
    chunks = create_chunk([item(1, "An Overview of Language Processing", heading=None)], uuid4())
    assert chunks[0].content == "An Overview of Language Processing"


def test_the_heading_counts_against_the_token_budget():
    # Heading 1 word + 2 + 2 = 5 > 4, so the second item opens a new chunk.
    chunks = create_chunk([item(3, "one two"), item(3, "three four")], uuid4(), max_token=4)
    assert len(chunks) == 2
