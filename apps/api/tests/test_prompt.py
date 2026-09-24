from uuid import uuid4

from app.schemas.rag import RetrievedChunk
from app.services.prompt import build_context


def test_summary_can_include_all_chunks_without_changing_question_limit():
    file_id = uuid4()
    course_id = uuid4()
    chunks = [
        RetrievedChunk(
            chunk_id=uuid4(),
            file_id=file_id,
            course_id=course_id,
            filename="lecture.pdf",
            page_start=index + 1,
            page_end=index + 1,
            heading=None,
            content=f"chunk {index}",
            score=1.0,
        )
        for index in range(10)
    ]

    _, normal_selection = build_context(chunks)
    full_context, summary_selection = build_context(chunks, max_sources=None)

    assert normal_selection == chunks[:8]
    assert summary_selection == chunks
    assert "chunk 9" in full_context
