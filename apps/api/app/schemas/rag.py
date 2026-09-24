"""C4 contract: the interface between retrieval (AI-1) and generation (AI-3).

Owned by AI-3. Retrieval must produce `RetrievedChunk` exactly as defined here;
any change to that shape needs agreement from AI-1.
"""

from enum import StrEnum
from uuid import UUID

from sqlmodel import Field, SQLModel


class RagIntent(StrEnum):
    QUESTION = "question"
    DOCUMENT_SUMMARY = "document_summary"


class RagQueryRequest(SQLModel):
    """Inbound: frontend -> generation layer. A single question from the user.

    Scope precedence, because the two scope fields can legitimately disagree:

    - `file_ids` present -> it *is* the scope. Search exactly those files and
      ignore `course_id`, which is only the turn's home course.
    - `file_ids` null -> search the whole of `course_id`.
    - both null -> the whole corpus.

    They must not be ANDed. US-12 (MVP, MUST) lets the @-picker mention files
    from any course, so `course_id AND file_id IN (...)` returns nothing at all
    whenever the user mentions a file from outside the course they are sitting
    in -- silently, with no error to trace.
    """

    model_config = {"extra": "forbid"}

    question: str = Field(..., min_length=1, max_length=2000)
    course_id: UUID | None = Field(
        default=None, description="The turn's home course. Ignored when file_ids is set."
    )
    conversation_id: UUID | None = Field(default=None, description="The turn's conversation")
    file_ids: list[UUID] | None = Field(
        default=None,
        description="Explicit @-mention scope. May cross courses. When set, overrides course_id.",
    )
    intent: RagIntent = RagIntent.QUESTION
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunk(SQLModel):
    """C4 internal: retrieval (AI-1) -> generation (AI-3).

    Request-scoped. This object is never serialised over HTTP and is discarded
    once the request completes.
    """

    model_config = {"extra": "forbid"}

    chunk_id: UUID = Field(
        ...,
        description="For de-duplication, debug logging, and provenance. "
        "MUST NOT be persisted in a Citation: chunk ids change whenever the chunking "
        "strategy is re-run, so a citation anchored to one stops resolving after a "
        "re-index. It IS persisted in `ScopeSnapshot`, which is a debug record rather "
        "than a durable anchor -- finding R14, resolved 18 Aug.",
    )
    file_id: UUID
    course_id: UUID
    filename: str = Field(..., min_length=1)
    page_start: int | None = Field(
        default=None,
        ge=1,
        description="First page of this chunk, 1-based, matching what the user and PDF "
        "viewers see. Required for PDF sources; None for formats without pages.",
    )
    page_end: int | None = Field(default=None, ge=1)
    heading: str | None = Field(
        default=None,
        description="Section heading from the source document. None when the chunk has no "
        "heading; do not substitute the filename here, that is a rendering decision.",
    )
    content: str = Field(..., min_length=1)
    score: float = Field(
        ...,
        description="Retrieval similarity score. Used by the grounding check to decide "
        "whether anything relevant was found at all.",
    )


class Citation(SQLModel):
    """Outbound: generation -> frontend, and persisted into MESSAGE.citations.

    Deliberately anchored to file_id + page + quote and never to chunk_id:
    chunks are a regenerable intermediate product, while the file, the page and
    the quoted text survive re-ingestion.

    Finding R14 asked for chunk-level provenance here. It goes in `ScopeSnapshot`
    instead: that recovers the traceability without making a citation depend on an
    id that a re-index invalidates. Resolved 18 Aug.
    """

    model_config = {"extra": "forbid"}

    marker: int = Field(..., ge=1)
    file_id: UUID
    course_id: UUID
    filename: str = Field(..., min_length=1)
    page: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    quote: str = Field(
        ...,
        min_length=1,
        description="Verbatim excerpt the model relied on. Must be findable in the source "
        "chunk; this is what makes a citation machine-checkable.",
    )


class RagAnswer(SQLModel):
    """Outbound: generation -> frontend. Response model of POST /rag/query."""

    model_config = {"extra": "forbid"}

    answer: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool
    uncovered: str | None = Field(
        default=None,
        description="What the sources did not cover, when they answered the question only "
        "in part. None means the answer is complete against the material -- r47. It is a "
        "field rather than a sentence inside `answer` so that `grounded=true` stops "
        "carrying two different meanings: answered in full, and answered in part.",
    )
    used_chunks: int = Field(
        ...,
        ge=0,
        description="How many chunks were actually put into the prompt, after selection. "
        "0 means there was no material and the layer should have refused to answer.",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="The active or newly created conversation ID.",
    )


class ScopeSnapshot(SQLModel):
    """Outbound: generation -> MESSAGE.scope_snapshot. Written once, never updated.

    What retrieval was allowed to see for one turn, and what it actually used.
    This is where finding R14's chunk-level provenance lives: a `Citation` stays
    anchored to file + page + quote so it survives a re-index, while this record
    keeps the chunk ids for tracing a specific answer back to the exact text that
    produced it. A stale chunk id here is acceptable -- nothing resolves against
    it, it is evidence of what happened.

    Stored as JSONB. Nothing reads it on the hot path.
    """

    model_config = {"extra": "forbid"}

    scope_course_id: UUID | None = Field(
        default=None,
        description="The course in scope for this turn. None when the request carried "
        "neither a course nor file mentions, i.e. the whole corpus.",
    )
    mentioned_file_ids: list[UUID] | None = Field(
        default=None,
        description="The @-mention scope as the user gave it. When present this WAS the "
        "scope and `scope_course_id` was ignored -- the precedence rule on RagQueryRequest.",
    )
    retrieved_chunk_ids: list[UUID] = Field(
        default_factory=list,
        description="Every chunk retrieval returned, before selection.",
    )
    used_chunk_ids: list[UUID] = Field(
        default_factory=list,
        description="The chunks that actually went into the prompt. Length must equal "
        "RagAnswer.used_chunks; a mismatch means selection and reporting disagree.",
    )
    embedding_model: str | None = Field(
        default=None,
        description="Which model produced the query vector. Two models with the same "
        "output dimension put vectors in different spaces, so a snapshot without this "
        "cannot be compared against a later one -- finding R5.",
    )
