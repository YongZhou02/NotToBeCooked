"""The /rag/query route -- question in, grounded answer out, with database IO.

The order below is the whole design: retrieve, render, generate, **verify**,
then decide what to send. Verification sits between the model and the response
because `grounded` is a promise to the user, and a promise the model makes about
itself is not evidence.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.database import get_session
from app.db.vector_ops import SearchConfig, hybrid_search
from app.dependencies.auth import get_current_user
from app.schemas.chat import ChatRole, Message
from app.schemas.course import Course
from app.schemas.errors import ApiError
from app.schemas.file import File as FileRow
from app.schemas.folder import Folder
from app.schemas.rag import (
    Citation,
    RagAnswer,
    RagQueryRequest,
    RetrievedChunk,
    ScopeSnapshot,
)
from app.services.chat import get_or_create_conversation
from app.services.embeddings import embed_query
from app.services.grounding import check_grounding, drop_unreferenced, drop_unverified
from app.services.llm import REFUSAL, UNVERIFIED, LlmAnswer, LlmCitation, generate_answer
from app.services.prompt import build_context

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
    request: RagQueryRequest, session: AsyncSession, user_id: UUID
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
    """
    file_ids = await _scope_file_ids(request, session, user_id)
    if not file_ids:
        # Nothing the caller can see matches the scope. Returning early is not
        # an optimisation: `hybrid_search` reads an empty list as "no filter".
        return []

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
        config=SearchConfig(final_limit=request.top_k),
    )


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

    chunks = await _retrieve(rag_request, session, UUID(str(user_id)))
    if not chunks and settings.LLM_FAKE_MODE:
        chunks = _placeholder_sources(rag_request, conversation.course_id)

    context, selected = build_context(chunks)

    # 4. Generate.
    try:
        draft = await generate_answer(question=clean_rag_query, context=context, sources=selected)
    except Exception:
        # There is no retry. The user is already waiting on a chat turn and a
        # second timeout helps nobody; the traceback is for us, the refusal is
        # for them.
        logger.exception("generation failed: conversation_id=%s", conv_id)
        draft = LlmAnswer(answer=REFUSAL, grounded=False, citations=[])

    # 5. Verify, then decide. This is the step that makes `grounded` mean
    #    something: the model's own claim is an input to the decision, never the
    #    decision itself.
    citations = _resolve_citations(draft.citations, selected)
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
