from uuid import uuid4

from app.routers.rag import _rrf_merge_many
from app.schemas.rag import RetrievedChunk


def make_chunk(content, page, file_id):
    return RetrievedChunk(
        chunk_id=uuid4(),
        file_id=file_id,
        course_id=uuid4(),
        filename="test.pdf",
        page_start=page,
        page_end=page,
        heading="Test",
        content=content,
        score=1.0,
    )


def test_distinct_facts_same_page_are_preserved():
    file_id = uuid4()

    a = make_chunk(
        "Example expression syntax tree shows source identifier "
        "mapping: Position becomes id1, initial becomes id2, "
        "rate becomes id3 before parsing.",
        13,
        file_id,
    )

    b = make_chunk(
        "Example expression syntax tree shows type coercion: "
        "integer 60 becomes inttoreal(60) before multiplication "
        "by real id3, preserving numeric type.",
        13,
        file_id,
    )

    result = _rrf_merge_many(
        [[a, b]],
        limit=5,
        dedupe_pages=False,
        dedupe_similar=True,
    )

    assert {c.chunk_id for c in result} == {
        a.chunk_id,
        b.chunk_id,
    }


def test_identical_content_different_pages_is_deduplicated():
    file_id = uuid4()
    content = (
        "Semantic analysis inserts inttoreal conversion "
        "above integer literal 60 in expression tree."
    )

    a = make_chunk(content, 17, file_id)
    b = make_chunk(content, 18, file_id)

    result = _rrf_merge_many(
        [[a, b]],
        limit=5,
        dedupe_pages=False,
        dedupe_similar=True,
    )

    assert len(result) == 1
    assert result[0].chunk_id == a.chunk_id
