"""The /rag/query route -- question in, grounded answer out, with database IO.

The order below is the whole design: retrieve, render, generate, **verify**,
then decide what to send. Verification sits between the model and the response
because `grounded` is a promise to the user, and a promise the model makes about
itself is not evidence.
"""

import asyncio
import logging
import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.database import get_session
from app.db.vector_ops import (
    SearchConfig,
    _vector_similarity_search,
    hybrid_search,
    keyword_search,
)
from app.dependencies.auth import get_current_user
from app.schemas.chat import ChatRole, Message
from app.schemas.chunk import Chunk
from app.schemas.course import Course
from app.schemas.errors import ApiError
from app.schemas.file import File as FileRow
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun
from app.schemas.rag import (
    Citation,
    RagAnswer,
    RagIntent,
    RagQueryRequest,
    RetrievedChunk,
    ScopeSnapshot,
)
from app.services.chat import get_or_create_conversation
from app.services.embeddings import embed_query
from app.services.grounding import (
    check_grounding,
    drop_duplicate_citations,
    drop_unreferenced,
    drop_unverified,
    extract_markers,
)
from app.services.llm import (
    GENERATION_FAILED,
    NOTHING_CITED,
    UNVERIFIED,
    LlmAnswer,
    LlmCitation,
    generate_answer,
)
from app.services.prompt import HISTORY_TURNS, build_context, render_history
from app.services.query_rewrite import rewrite_query
from app.services.question_decomposition import decompose_question

logger = logging.getLogger(__name__)

rag_router = APIRouter(dependencies=[Depends(get_current_user)])


async def _scope_file_ids(
    request: RagQueryRequest, session: AsyncSession, user_id: UUID
) -> list[UUID]:
    """Turn the request's scope into the exact file ids retrieval may read.

    Every branch starts from the caller's own files and narrows from there.
    That is the point of the function, not a detail of it: `hybrid_search`
    filters on `is_active` and on the file ids it is handed, and on nothing
    else. It has no idea who is asking. Hand it a course's files and it is
    correct; hand it an empty list and `if file_ids:` inside it skips the
    filter entirely and the search runs across every user in the database.

    So the empty list never reaches it -- see `_retrieve`.

    The three branches are the scope precedence written in `RagQueryRequest`:

    - `file_ids` given: it IS the scope, and it may cross courses (US-12).
      Ids the caller does not own are dropped rather than rejected. A 404 would
      answer "does this file id exist", which is a question a stranger should
      not be able to ask; dropping answers nothing and still reads nothing.
    - `course_id` only: that course's files, if the course is the caller's.
    - neither: the caller's whole corpus. "Whole corpus" in the C4 contract
      means everything the asker can see, never everything in the table.
    """
    statement = (
        select(FileRow.id)
        .join(Folder, col(FileRow.folder_id) == col(Folder.id))
        .join(Course, col(Folder.course_id) == col(Course.id))
        .where(col(Course.user_id) == user_id)
    )
    if request.file_ids:
        statement = statement.where(col(FileRow.id).in_(request.file_ids))
    elif request.course_id is not None:
        statement = statement.where(col(Course.id) == request.course_id)

    # `File.id` is declared `UUID | None` so that SQLModel can default it, so a
    # selected id is typed optional even though a row that exists always has
    # one. Dropping the impossible None keeps the return type honest rather than
    # casting it away.
    return [file_id for file_id in (await session.exec(statement)).all() if file_id is not None]


async def _retrieve(
    request: RagQueryRequest,
    session: AsyncSession,
    user_id: UUID,
    query_vector: list[float] | None = None,
    search_config: SearchConfig | None = None,
) -> list[RetrievedChunk]:
    """Retrieval for one turn -- Gantt r48, the caller `hybrid_search` never had.

    The body has existed in `app/db/vector_ops.py` since 13 August and nothing
    called it; `_retrieve` returned `[]`, so every answer in every demo came
    from `_placeholder_sources` below. This is the wiring, and it is all this
    function is: scope, embed, search.

    `embed_query` runs in a thread. It is a torch forward pass on the request
    path, and the event loop is shared by every other request in the process --
    the same failure as report 5, where a 60-page ingest made `/health` stop
    answering for six and a half minutes. Measured 10 September on the OCI A1
    (2 OCPU) after that fix: 331 s of ingest, 329 `/health` samples, worst
    latency 0.19 s. A query embedding is milliseconds by comparison, but it is
    the same kind of work and it belongs off the loop for the same reason.

    `query_vector` is for a caller that already embedded this question and
    needs the vector for something else too -- see `_retrieve_follow_up`. One
    embedding took about 0.38 s on the VM, measured 22 October.
    """
    file_ids = await _scope_file_ids(request, session, user_id)
    if not file_ids:
        # Nothing the caller can see matches the scope. Returning early is not
        # an optimisation: `hybrid_search` reads an empty list as "no filter".
        return []

    if query_vector is None:
        query_vector = await asyncio.to_thread(embed_query, request.question)
    return await hybrid_search(
        query_text=request.question,
        query_vector=query_vector,
        # Decision 1, 15 September: scope is decided here, in `_scope_file_ids`,
        # and `hybrid_search` is handed the answer rather than the question.
        # The parameter is required, so this is not a value being defaulted --
        # it is the caller saying it has no course filter to apply. Inside
        # `vector_ops.py:78` the order is `if file_ids:` then `elif course_id
        # is not None:`, and `file_ids` is never empty by the return above, so
        # the `elif` is unreachable from here either way.
        course_id=None,
        session=session,
        file_ids=file_ids,
        config=search_config or SearchConfig(final_limit=request.top_k),
    )


async def _retrieve_document_chunks(
    request: RagQueryRequest,
    session: AsyncSession,
    user_id: UUID,
) -> list[RetrievedChunk]:
    if request.file_ids is None or len(request.file_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document summary requires exactly one file",
        )
    owned_file_ids = await _scope_file_ids(request, session, user_id)

    if not owned_file_ids:
        return []

    file_id = owned_file_ids[0]

    statement = (
        select(Chunk, FileRow)
        .join(FileRow, col(Chunk.file_id) == col(FileRow.id))
        .join(
            IngestionRun,
            col(Chunk.ingestion_run_id) == col(IngestionRun.id),
        )
        .where(
            col(Chunk.file_id) == file_id,
            col(IngestionRun.is_active).is_(True),
        )
        .order_by(Chunk.chunk_index)
    )
    rows = (await session.exec(statement)).all()
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            file_id=chunk.file_id,
            course_id=chunk.course_id,
            filename=file_row.filename,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            heading=chunk.heading,
            content=chunk.content,
            score=1.0,
        )
        for chunk, file_row in rows
    ]


def _placeholder_sources(request: RagQueryRequest, course_id: UUID) -> list[RetrievedChunk]:
    """Stand-in material so the frontend has something to render.

    Only reachable under LLM_FAKE_MODE, and now only when retrieval found
    nothing. It fabricates the *sources*, not the answer -- everything after
    this point is the production path, so the shape the UI receives is the
    shape it will receive for real.

    This used to say "delete this the day `_retrieve` returns rows". That day
    is 13 September 2026 and it is deliberately still here: F3 (Gantt r36, due
    16 Sep) is built mock-first against a database with no ingested chunks in
    it, and deleting this would turn every one of AI-1's screens into a refusal
    overnight.

    **Lead call, 13 September 2026: it stays.** Recorded with a trigger rather
    than left as a judgement, because the reason it is defensible today is a
    fact that will stop being true: there is no shared database with an
    ingested file in it. **Delete this the day there is one.** From that day the
    fallback stops standing in for an empty corpus and starts hiding one, and an
    empty corpus is exactly what a demo needs to show rather than paper over.
    """
    file_ids = request.file_ids or [uuid4()]
    bodies = [
        "A partial index covers only the rows matching its WHERE clause, so it is "
        "smaller than a full index and is only usable when the query repeats that clause.",
        "A B-tree index stores keys in sorted order, which is why a range scan can walk "
        "the leaves without returning to the root.",
    ]
    return [
        RetrievedChunk(
            chunk_id=uuid4(),
            file_id=file_id,
            course_id=course_id,
            filename=f"Placeholder {index}.pdf",
            page_start=1,
            page_end=1,
            heading=None,
            content=bodies[(index - 1) % len(bodies)],
            score=1.0 - index * 0.1,
        )
        for index, file_id in enumerate(file_ids[:2], start=1)
    ]


def _resolve_citations(
    drafted: list[LlmCitation], selected: list[RetrievedChunk]
) -> list[Citation]:
    """Attach provenance the model was never asked for.

    The model supplies a marker and a quote. `file_id`, `course_id`, `filename`
    and `page` come from the chunk the marker resolves to -- never from the
    model, which would produce a well-formed UUID for a file that does not
    exist.

    A marker outside the range is dropped rather than clamped: there is no chunk
    to take provenance from, so there is no honest Citation to build. It does not
    escape unnoticed, because the marker is still written in the answer text and
    `check_grounding` reports it as cited-with-nothing-behind-it.
    """
    resolved: list[Citation] = []
    for item in drafted:
        if not 1 <= item.marker <= len(selected):
            continue
        source = selected[item.marker - 1]
        resolved.append(
            Citation(
                marker=item.marker,
                file_id=source.file_id,
                course_id=source.course_id,
                filename=source.filename,
                page=source.page_start,
                page_end=source.page_end,
                quote=item.quote,
            )
        )
    return resolved


def _pair_turns(
    messages: list[Message], limit: int = HISTORY_TURNS
) -> list[tuple[str, str | None]]:
    """The last `limit` (question, answer) pairs, oldest first. US-14.

    `messages` is one conversation in time order. An answer is kept only when
    that turn was grounded; otherwise the pair carries None and the question
    alone, which still says what the student was asking about.
    """
    pairs: list[tuple[str, str | None]] = []
    for message in messages:
        if message.role == ChatRole.USER:
            pairs.append((message.content, None))
        elif pairs and pairs[-1][1] is None and message.grounded:
            pairs[-1] = (pairs[-1][0], message.content)
    return pairs[-limit:] if limit > 0 else []


async def _recent_turns(
    session: AsyncSession, conversation_id: UUID
) -> list[tuple[str, str | None]]:
    """Read before this turn's own user message is added, so it is not included."""
    statement = (
        select(Message)
        .where(col(Message.conversation_id) == conversation_id)
        .order_by(col(Message.created_at).desc())
        .limit(HISTORY_TURNS * 2 + 2)
    )
    newest_first = list((await session.exec(statement)).all())
    return _pair_turns(list(reversed(newest_first)))


def _interleave(
    first: list[RetrievedChunk], second: list[RetrievedChunk], limit: int
) -> list[RetrievedChunk]:
    """first[0], second[0], first[1], ... without repeats, at most `limit`."""
    merged: list[RetrievedChunk] = []
    seen: set[UUID] = set()
    for pair in zip(first, second, strict=False):
        for chunk in pair:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                merged.append(chunk)
    longer = first if len(first) > len(second) else second
    for chunk in longer[min(len(first), len(second)) :]:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            merged.append(chunk)
    return merged[:limit]


# Below this, the question alone matches nothing in its scope well enough to
# stand on its own, so the search joined to the previous question goes first.
# Measured 22 October on the VM: 36 questions over the two NLP lectures and
# GLOSSARY.md, each searched alone, cosine similarity of the closest chunk.
#   English lectures   follow-ups <= 0.454, new questions >= 0.541
#   GLOSSARY (Chinese) follow-ups <= 0.497, new questions >= 0.493
# At 0.5 one of the 36 is misjudged: "reflog 有什么用" is read as a follow-up.
# Chinese PDFs and scanned PDFs were not measured. A wrong call costs the
# order, not the results: both lists are still interleaved.
STANDS_ALONE_SIMILARITY = 0.5
RELEVANT_CHUNK_SIMILARITY = 0.48
CONFIDENCE_FLOOR = 0.35
CONFIDENCE_CEILING = 0.65
CONFIDENCE_SUPPORT_TARGET = 3
ANCHOR_STOPWORDS = {
    "about",
    "according",
    "after",
    "before",
    "becomes",
    "could",
    "does",
    "from",
    "into",
    "lecture",
    "material",
    "operation",
    "question",
    "same",
    "source",
    "their",
    "these",
    "they",
    "this",
    "what",
    "when",
    "whereas",
    "which",
    "while",
    "with",
    "would",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _confidence_from_similarities(similarities: list[float]) -> dict[str, Any]:
    """Explainable retrieval routing score; not answer-correctness probability."""
    ordered = sorted(similarities, reverse=True)
    best = ordered[0] if ordered else 0.0
    strong_count = sum(score >= RELEVANT_CHUNK_SIMILARITY for score in ordered)
    peak = _clamp01((best - CONFIDENCE_FLOOR) / (CONFIDENCE_CEILING - CONFIDENCE_FLOOR))
    support = _clamp01(strong_count / CONFIDENCE_SUPPORT_TARGET)
    score = 0.7 * peak + 0.3 * support
    return {
        "score": score,
        "best_similarity": best,
        "strong_chunk_count": strong_count,
        "top_similarities": ordered,
        "peak_component": peak,
        "support_component": support,
    }


async def _retrieval_confidence(
    request: RagQueryRequest,
    query_vector: list[float],
    session: AsyncSession,
    user_id: UUID,
) -> dict[str, Any]:
    file_ids = await _scope_file_ids(request, session, user_id)
    if not file_ids:
        return _confidence_from_similarities([])
    rows = await _vector_similarity_search(
        query_vector, session, None, file_ids, top_k=request.top_k
    )
    return _confidence_from_similarities([1 - float(row[2]) for row in rows])


def _rrf_merge(
    original: list[RetrievedChunk], rewritten: list[RetrievedChunk], limit: int
) -> list[RetrievedChunk]:
    """Fuse two ranked lists without trusting incomparable provider scores."""
    return _rrf_merge_many([original, rewritten], limit)


def _rrf_merge_many(
    rankings: list[list[RetrievedChunk]],
    limit: int,
    *,
    dedupe_pages: bool = False,
    dedupe_similar: bool = False,
) -> list[RetrievedChunk]:
    """Fuse original + auxiliary rankings; auxiliary queries get a discovery bonus."""
    by_id: dict[UUID, RetrievedChunk] = {}
    fused: dict[UUID, float] = {}
    for list_index, ranked in enumerate(rankings):
        # A small discovery bonus keeps a new rewrite-only passage from being
        # crowded out by four chunks duplicated across both lists.
        weight = 1.0 if list_index == 0 else 1.2
        for rank, chunk in enumerate(ranked, 1):
            by_id[chunk.chunk_id] = chunk
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + weight / (60 + rank)
    ordered = sorted(fused, key=lambda chunk_id: fused[chunk_id], reverse=True)
    merged: list[RetrievedChunk] = []
    seen_pages: set[tuple[UUID, int | None, int | None]] = set()
    seen_content: list[tuple[UUID, set[str]]] = []
    for chunk_id in ordered:
        chunk = by_id[chunk_id]
        page_key = (chunk.file_id, chunk.page_start, chunk.page_end)
        if dedupe_pages and chunk.page_start is not None and page_key in seen_pages:
            continue
        content_terms = _content_terms(chunk.content)
        if dedupe_similar and any(
            chunk.file_id == file_id
            and content_terms
            and len(content_terms & previous_terms) / len(content_terms | previous_terms) >= 0.35
            for file_id, previous_terms in seen_content
        ):
            continue
        seen_pages.add(page_key)
        seen_content.append((chunk.file_id, content_terms))
        merged.append(chunk.model_copy(update={"score": fused[chunk_id]}))
        if len(merged) == limit:
            break
    return merged


def _content_terms(content: str) -> set[str]:
    """Return stable lexical features for cheap, local near-duplicate detection."""
    stopwords = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "before",
        "for",
        "from",
        "into",
        "that",
        "the",
        "their",
        "then",
        "this",
        "through",
        "using",
        "with",
    }
    return {
        term
        for term in re.findall(r"[a-z][a-z0-9_-]{2,}", content.casefold())
        if term not in stopwords
    }


def _should_decompose(question: str) -> bool:
    """Conservative, local router: false positives cost an LLM call and retrievals."""
    text = " ".join(question.casefold().split())
    if len(re.findall(r"\b\w+\b", text)) < 10:
        return False
    if text.count("?") > 1:
        return True
    comparison_markers = (
        " compare ",
        " difference ",
        " differ ",
        " whereas ",
        " relationship between ",
        " the same ",
        " respectively",
    )
    if any(marker in f" {text} " for marker in comparison_markers):
        return True
    multi_stage_markers = (
        "progress from",
        "from source",
        "before and after",
        "before parsing",
        "then finally",
        "and why",
    )
    return any(marker in text for marker in multi_stage_markers)


def _anchor_terms(question: str, limit: int = 8) -> list[str]:
    """Distinct content words for one-term full-text probes."""
    terms: list[str] = []
    for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", question.casefold()):
        if term not in ANCHOR_STOPWORDS and term not in terms:
            terms.append(term)
    return terms[:limit]


async def _keyword_anchor_retrieve(
    request: RagQueryRequest, session: AsyncSession, user_id: UUID
) -> list[RetrievedChunk]:
    """Take the best exact-term hit per content word, preserving request scope."""
    file_ids = await _scope_file_ids(request, session, user_id)
    if not file_ids:
        return []
    # AsyncSession does not support concurrent operations on the same session.
    rows_by_term = []
    for term in _anchor_terms(request.question):
        rows_by_term.append(await keyword_search(term, session, None, file_ids, top_k=1))
    found: list[RetrievedChunk] = []
    seen: set[UUID] = set()
    for rows in rows_by_term:
        if not rows:
            continue
        chunk, file, rank = rows[0]
        if chunk.id in seen:
            continue
        seen.add(chunk.id)
        found.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                course_id=chunk.course_id,
                filename=file.filename,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                heading=chunk.heading,
                content=chunk.content,
                score=float(rank),
            )
        )
    return found


async def _best_similarity(
    request: RagQueryRequest,
    query_vector: list[float],
    session: AsyncSession,
    user_id: UUID,
) -> float:
    """Cosine similarity of the closest chunk in scope: 1.0 identical, 0 unrelated.

    Takes the vector the search already computed rather than embedding the
    question a second time. Same scope rule as `_retrieve`: an empty scope
    never reaches the search, because an empty list there means "no filter".
    """
    file_ids = await _scope_file_ids(request, session, user_id)
    if not file_ids:
        return 0.0
    rows = await _vector_similarity_search(query_vector, session, None, file_ids, top_k=1)
    # The search orders by cosine distance, which is 1 - similarity.
    return 1 - float(rows[0][2]) if rows else 0.0


async def _retrieve_follow_up(
    request: RagQueryRequest,
    previous_question: str | None,
    session: AsyncSession,
    user_id: UUID,
    query_vector: list[float] | None = None,
) -> list[RetrievedChunk]:
    """Search for the question alone and for it joined to the previous one. US-14.

    "What are its drawbacks?" has nothing in it to search for; joined to "what
    is a lexicon?" it does. But a question that changes topic would be pulled
    back by the old one, so both searches run and their results alternate.

    Which list goes first depends on whether the question stands alone.
    Measured 22 October, after "finite state automata": "what does it used for"
    searched alone returned five passages on corpora and regular expressions
    and none on FSA, while "what is corpus annotation" searched joined put the
    FSA page first. A pronoun does not decide it -- "give me an example" has
    none and "what does this regular expression match" has one -- so the
    question's best similarity does, see `STANDS_ALONE_SIMILARITY`.

    No model call: two embeddings, two searches, and one top-1 lookup that
    reuses the first embedding.
    """
    if not previous_question:
        return await _retrieve(request, session, user_id, query_vector=query_vector)
    if query_vector is None:
        query_vector = await asyncio.to_thread(embed_query, request.question)

    alone = await _retrieve(request, session, user_id, query_vector=query_vector)
    joined_question = " ".join(f"{previous_question} {request.question}".split())
    joined = await _retrieve(
        request.model_copy(update={"question": joined_question}), session, user_id
    )
    similarity = await _best_similarity(request, query_vector, session, user_id)
    if similarity < STANDS_ALONE_SIMILARITY:
        return _interleave(joined, alone, request.top_k)
    return _interleave(alone, joined, request.top_k)


@rag_router.post(
    "/query",
    response_model=RagAnswer,
    responses={
        401: {"model": ApiError, "description": "Missing, invalid or expired access token"},
        404: {"model": ApiError, "description": "Session or course not found"},
    },
)
async def query(
    request: RagQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> RagAnswer:
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or tampered token"},
        )

    # 1. Get or create conversation via services/chat.py
    first_line = next(
        (line.strip() for line in request.question.split("\n") if line.strip()), "New Chat"
    )
    clean_title = first_line[:40].strip() + ("..." if len(first_line) > 40 else "")
    conversation = await get_or_create_conversation(
        session=session,
        user_id=UUID(str(user_id)),
        course_id=request.course_id,
        conversation_id=request.conversation_id,
        title=clean_title or "New Chat",
    )

    if conversation.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "SESSION_INIT_FAILED",
                "message": "Conversation ID was not initialized",
            },
        )
    conv_id: UUID = conversation.id

    # Read before the user turn below is added: that turn is this question,
    # not part of the history it is asked against.
    turns = await _recent_turns(session, conv_id) if request.conversation_id else []

    # 2. Record the user turn. Stores the raw multiline text exactly as sent.
    session.add(
        Message(
            id=uuid4(),
            conversation_id=conv_id,
            scope_course_id=conversation.course_id,
            role=ChatRole.USER,
            content=request.question,
            grounded=False,
            citations=None,
            mentioned_file_ids=request.file_ids,
            created_at=datetime.now(UTC),
        )
    )

    # 3. Retrieve. Newlines are collapsed for the search and for the prompt; the
    #    stored user turn above keeps the original.
    clean_rag_query = " ".join(request.question.split()).strip()
    rag_request = request.model_copy(update={"question": clean_rag_query})

    rewrite_trace: dict[str, Any] = {
        "enabled": settings.QUERY_REWRITE_ENABLED,
        "attempted": False,
    }
    decomposition_trace: dict[str, Any] = {
        "enabled": settings.RETRIEVAL_DECOMPOSITION_ENABLED,
        "attempted": False,
    }
    if rag_request.intent == RagIntent.DOCUMENT_SUMMARY:
        chunks = await _retrieve_document_chunks(
            rag_request,
            session,
            UUID(str(user_id)),
        )
    else:
        decomposition_candidate = (
            settings.RETRIEVAL_DECOMPOSITION_ENABLED
            and not settings.LLM_FAKE_MODE
            and _should_decompose(clean_rag_query)
        )
        auxiliary_retrieval_enabled = (
            settings.QUERY_REWRITE_ENABLED or settings.RETRIEVAL_DECOMPOSITION_ENABLED
        ) and not settings.LLM_FAKE_MODE
        query_vector = (
            await asyncio.to_thread(embed_query, clean_rag_query)
            if auxiliary_retrieval_enabled
            else None
        )
        chunks = await _retrieve_follow_up(
            rag_request,
            turns[-1][0] if turns else None,
            session,
            UUID(str(user_id)),
            query_vector=query_vector,
        )
        if (
            settings.QUERY_REWRITE_ENABLED
            and not settings.LLM_FAKE_MODE
            and not decomposition_candidate
        ):
            assert query_vector is not None
            confidence = await _retrieval_confidence(
                rag_request, query_vector, session, UUID(str(user_id))
            )
            rewrite_trace["initial_confidence"] = confidence
            rewrite_trace["threshold"] = settings.QUERY_REWRITE_CONFIDENCE_THRESHOLD
        else:
            confidence = None
        if decomposition_candidate:
            started = perf_counter()
            decomposition_trace.update(
                attempted=True,
                original_query=clean_rag_query,
                first_chunk_ids=[str(c.chunk_id) for c in chunks],
            )
            try:
                sub_questions = await decompose_question(
                    clean_rag_query, [chunk.content for chunk in chunks[:5]]
                )
                decomposition_trace["sub_questions"] = sub_questions
                rankings = [chunks]
                subquery_sources: list[dict[str, Any]] = []
                for sub_question in sub_questions:
                    sub_request = rag_request.model_copy(
                        update={"question": sub_question, "top_k": min(5, rag_request.top_k)}
                    )
                    sub_chunks = await _retrieve(
                        sub_request,
                        session,
                        UUID(str(user_id)),
                        search_config=SearchConfig(final_limit=min(5, rag_request.top_k)),
                    )
                    rankings.append(sub_chunks)
                    subquery_sources.append(
                        {
                            "question": sub_question,
                            "chunk_ids": [str(c.chunk_id) for c in sub_chunks],
                            "pages": [c.page_start for c in sub_chunks],
                        }
                    )
                merged = _rrf_merge_many(
                    rankings,
                    rag_request.top_k,
                    dedupe_pages=False,
                    dedupe_similar=True,
                )

                candidate_map = {
                    str(c.chunk_id): c
                    for ranked in rankings
                    for c in ranked
                }
                selected_ids = {str(c.chunk_id) for c in merged}
                decomposition_trace["candidate_count"] = len(candidate_map)
                decomposition_trace["selected_pages"] = [
                    c.page_start for c in merged
                ]
                decomposition_trace["dropped_candidate_pages"] = sorted({
                    c.page_start
                    for cid, c in candidate_map.items()
                    if cid not in selected_ids and c.page_start is not None
                })
                decomposition_trace["subquery_sources"] = subquery_sources
                decomposition_trace["merged_chunk_ids"] = [str(c.chunk_id) for c in merged]
                decomposition_trace["accepted"] = merged != chunks
                chunks = merged
            except Exception as exc:
                decomposition_trace["error_type"] = type(exc).__name__
                logger.exception("question decomposition failed: conversation_id=%s", conv_id)
            decomposition_trace["extra_latency_ms"] = (perf_counter() - started) * 1000
            decomposition_trace.setdefault("accepted", False)
            logger.info(
                "selective question decomposition: conversation_id=%s trace=%s",
                conv_id,
                decomposition_trace,
            )
        elif confidence and confidence["score"] < settings.QUERY_REWRITE_CONFIDENCE_THRESHOLD:
            started = perf_counter()
            rewrite_trace.update(
                attempted=True,
                original_query=clean_rag_query,
                first_source_pages=[c.page_start for c in chunks],
                first_chunk_ids=[str(c.chunk_id) for c in chunks],
            )
            try:
                rewritten = await rewrite_query(clean_rag_query, turns[-1][0] if turns else None)
                rewrite_trace["rewritten_query"] = rewritten
                if rewritten.casefold() == clean_rag_query.casefold():
                    rewrite_trace["skip_reason"] = "unchanged_query"
                else:
                    rewritten_request = rag_request.model_copy(update={"question": rewritten})
                    rewritten_vector = await asyncio.to_thread(embed_query, rewritten)
                    retry_chunks = await _retrieve(
                        rewritten_request,
                        session,
                        UUID(str(user_id)),
                        query_vector=rewritten_vector,
                        search_config=SearchConfig(
                            keyword_weight=2.0,
                            vector_weight=1.0,
                            final_limit=rag_request.top_k,
                        ),
                    )
                    anchor_chunks = await _keyword_anchor_retrieve(
                        rag_request, session, UUID(str(user_id))
                    )
                    expanded_chunks = _interleave(anchor_chunks, retry_chunks, rag_request.top_k)
                    rewrite_trace["rewritten_confidence"] = await _retrieval_confidence(
                        rewritten_request,
                        rewritten_vector,
                        session,
                        UUID(str(user_id)),
                    )
                    rewrite_trace["retry_source_pages"] = [c.page_start for c in retry_chunks]
                    rewrite_trace["retry_chunk_ids"] = [str(c.chunk_id) for c in retry_chunks]
                    rewrite_trace["anchor_terms"] = _anchor_terms(clean_rag_query)
                    rewrite_trace["anchor_source_pages"] = [c.page_start for c in anchor_chunks]
                    merged = _rrf_merge(chunks, expanded_chunks, rag_request.top_k)
                    rewrite_trace["merged_chunk_ids"] = [str(c.chunk_id) for c in merged]
                    rewrite_trace["accepted"] = merged != chunks
                    chunks = merged
            except Exception as exc:
                rewrite_trace["error_type"] = type(exc).__name__
                logger.exception("query rewrite failed: conversation_id=%s", conv_id)
            rewrite_trace["extra_latency_ms"] = (perf_counter() - started) * 1000
            rewrite_trace.setdefault("accepted", False)
            logger.info(
                "retrieval confidence rewrite: conversation_id=%s trace=%s",
                conv_id,
                rewrite_trace,
            )
    if not chunks and settings.LLM_FAKE_MODE and rag_request.intent == RagIntent.QUESTION:
        chunks = _placeholder_sources(rag_request, conversation.course_id)

    # A normal question needs only the strongest few search results. A document
    # summary is different: `_retrieve_document_chunks` deliberately returns
    # the complete active ingestion run in document order, so truncating it to
    # the normal source cap would summarize only the opening pages.
    context, selected = build_context(
        chunks,
        max_sources=None if rag_request.intent == RagIntent.DOCUMENT_SUMMARY else 8,
    )

    # 4. Generate.
    try:
        draft = await generate_answer(
            question=clean_rag_query,
            context=context,
            sources=selected,
            document_summary=(rag_request.intent == RagIntent.DOCUMENT_SUMMARY),
            history=render_history(turns),
        )
    except Exception:
        # There is no retry. The user is already waiting on a chat turn and a
        # second timeout helps nobody; the traceback is for us, the message is
        # for them. Not REFUSAL: that claims the material has no answer, and
        # nothing here looked at the material.
        logger.exception("generation failed: conversation_id=%s", conv_id)
        draft = LlmAnswer(answer=GENERATION_FAILED, grounded=False, citations=[])

    # 5. Verify, then decide. This is the step that makes `grounded` mean
    #    something: the model's own claim is an input to the decision, never the
    #    decision itself.
    citations = _resolve_citations(draft.citations, selected)
    citations, duplicates = drop_duplicate_citations(citations)
    if duplicates:
        logger.info(
            "dropped duplicate citations: conversation_id=%s markers=%s",
            conv_id,
            [citation.marker for citation in duplicates],
        )
    citations, dropped = drop_unreferenced(draft.answer, citations)
    if dropped:
        logger.info(
            "dropped citations the answer never refers to: conversation_id=%s markers=%s",
            conv_id,
            dropped,
        )
    citations, unverified = drop_unverified(citations, selected)
    if unverified:
        # The quote text is logged because this is the only place it survives:
        # the citation is gone from the response and from the stored turn.
        logger.info(
            "dropped quotes that failed while their marker kept a verified one: "
            "conversation_id=%s quotes=%s",
            conv_id,
            [(c.marker, c.quote) for c in unverified],
        )
    report = check_grounding(draft.answer, citations, selected, uncovered=draft.uncovered)

    if report.ok:
        answer_text = draft.answer
        grounded = bool(citations) and draft.grounded
        # Carried only when the answer is grounded. An ungrounded answer names
        # no sources, so "the part the sources did not cover" is every part of
        # it, and repeating that in a field would read as a narrower claim than
        # the refusal it sits next to -- r47.
        uncovered = draft.uncovered if grounded else None
    elif (draft.uncovered or "").strip() and not citations and not extract_markers(draft.answer):
        # The model named a gap but cited nothing and marked nothing. r47 still
        # refuses to send it -- an answer resting on no source -- but the
        # reader is told nothing was found, not that citations failed a check:
        # there were none to check.
        logger.info("answer named a gap but cited nothing: conversation_id=%s", conv_id)
        answer_text, citations, grounded, uncovered = NOTHING_CITED, [], False, None
    else:
        # Not a 500. The pipeline worked; the answer failed its own check, and
        # sending it with grounded=False would still put unverifiable citations
        # in front of the reader. Nor REFUSAL: that says the material has no
        # answer, and nothing here checked that.
        logger.warning(
            "answer rejected by grounding check: conversation_id=%s problems=%s",
            conv_id,
            report.problems,
        )
        answer_text, citations, grounded, uncovered = UNVERIFIED, [], False, None

    # 6. Record the assistant turn, with the scope frozen alongside it.
    #    ScopeSnapshot is written here and never updated: it is the evidence for
    #    re-checking this answer later, which is why it keeps chunk ids that a
    #    re-index will invalidate while `citations` deliberately does not (R14).
    snapshot = ScopeSnapshot(
        # The turn's scope as the request expressed it. None only when the
        # request carried neither a course nor @-mentions -- the whole corpus.
        # When file_ids is set it WAS the scope and this was ignored, which is
        # why both are recorded rather than one being folded into the other.
        scope_course_id=request.course_id,
        mentioned_file_ids=request.file_ids,
        retrieved_chunk_ids=[c.chunk_id for c in chunks],
        used_chunk_ids=[c.chunk_id for c in selected],
        embedding_model=settings.MODEL_TYPE,
        query_rewrite=rewrite_trace,
        question_decomposition=decomposition_trace,
    )

    session.add(
        Message(
            id=uuid4(),
            conversation_id=conv_id,
            scope_course_id=conversation.course_id,
            role=ChatRole.ASSISTANT,
            content=answer_text,
            grounded=grounded,
            uncovered=uncovered,
            citations=[c.model_dump(mode="json") for c in citations],
            mentioned_file_ids=request.file_ids,
            scope_snapshot=snapshot.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
    )

    conversation.updated_at = datetime.now(UTC)
    await session.commit()

    return RagAnswer(
        answer=answer_text,
        citations=citations,
        grounded=grounded,
        uncovered=uncovered,
        # What actually went into the prompt, not how many citations came back.
        # A model that cited one of five sources still had five in front of it.
        used_chunks=len(selected),
        conversation_id=conv_id,
    )
