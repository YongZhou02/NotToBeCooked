"""The call to the model, and the shape of what comes back.

The model is asked for JSON, not prose, and it is asked for the *minimum*: the
answer text, whether it considers itself grounded, and for each citation a
marker and a verbatim quote. Nothing else.

That minimum is a security boundary, not a style preference. A `Citation` also
carries `file_id`, `course_id`, `filename` and `page` -- and a model asked for a
UUID will produce a well-formed UUID whether or not it corresponds to anything.
Those four fields are filled in by the caller from the chunk the marker resolves
to, so the worst a wrong marker can do is point at the wrong source we actually
sent, which `check_grounding` then catches. It can never invent a file that does
not exist or a page that was never retrieved.
"""

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.rag import RetrievedChunk
from app.services.prompt import (
    DOCUMENT_SUMMARY_INSTRUCTION,
    SYSTEM_INSTRUCTION,
)


class LlmCitation(BaseModel):
    """One citation as the model is allowed to express it."""

    marker: int = Field(..., ge=1)
    quote: str


class LlmAnswer(BaseModel):
    """The whole of what the model returns. Internal to generation; never sent."""

    answer: str
    grounded: bool
    citations: list[LlmCitation] = Field(default_factory=list)

    # r47. `prompt.py` has always instructed the model to "state which part the
    # material does not cover", and until now there was nowhere to state it but
    # the prose -- which means nothing could check that it had been said. A
    # field can be checked; a sentence buried in a paragraph cannot.
    #
    # Optional, because a full answer has nothing to report here. Absent and
    # empty mean different things and only one of them is legal: absent is "the
    # sources covered the question", while a present-but-blank value is the
    # model claiming a gap and then declining to name it. `check_grounding`
    # rejects the second.
    uncovered: str | None = None


# Gemini's responseSchema is an OpenAPI subset with upper-case type names. It is
# written out rather than derived from LlmAnswer because the two are not the
# same object: this constrains what the model may emit, and LlmAnswer validates
# what actually arrived. Deriving one from the other would mean a schema change
# silently loosens the check that catches it.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "grounded": {"type": "BOOLEAN"},
        # Deliberately absent from `required` below: the model must be able to
        # omit it, because most answers have no gap to declare. A required
        # nullable string would invite the empty string instead of the omission.
        "uncovered": {"type": "STRING", "nullable": True},
        "citations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "marker": {"type": "INTEGER"},
                    "quote": {"type": "STRING"},
                },
                "required": ["marker", "quote"],
            },
        },
    },
    "required": ["answer", "grounded", "citations"],
}

REFUSAL = "The supplied material does not cover this question."

# What the reader sees when an answer was written but failed `check_grounding`.
# It used to be REFUSAL, which told them the material had no answer -- a claim
# about their files that nobody had checked. What actually happened is that the
# answer's citations could not be verified, so that is what this says.
UNVERIFIED = (
    "An answer was written, but its citations could not be checked against "
    "the material, so it is not shown. Try asking again, or ask about one part "
    "of the document at a time."
)


def _verbatim_opening(content: str, limit: int = 110) -> str:
    """A prefix of `content`, cut at a word boundary. Never altered.

    Used only by fake mode, and it must stay an exact substring: the fake answer
    goes through the same `check_grounding` as a real one, so a fake that tidied
    up its own quote would fail verification and hide the fact that fake mode
    exercises nothing.
    """
    if len(content) <= limit:
        return content
    head = content[:limit]
    cut = head.rfind(" ")
    return head[:cut] if cut > 0 else head


def _fake_answer(question: str, sources: list[RetrievedChunk]) -> LlmAnswer:
    """A grounded answer with no model behind it.

    It quotes the real sources verbatim, so everything downstream -- marker
    consistency, quote verification, the `grounded` verdict, the snapshot -- runs
    the same code it runs in production. A fake that returned invented filenames
    would leave all of that untested and, worse, would look like it worked.
    """
    if not sources:
        return LlmAnswer(answer=REFUSAL, grounded=False, citations=[])

    used = sources[:2]
    sentences = [f'"{_verbatim_opening(c.content)}" [{i}]' for i, c in enumerate(used, start=1)]
    return LlmAnswer(
        answer=(
            f"[FAKE MODE] On {question.rstrip('?')}, the supplied material says: "
            + " ".join(sentences)
        ),
        grounded=True,
        citations=[
            LlmCitation(marker=i, quote=_verbatim_opening(c.content))
            for i, c in enumerate(used, start=1)
        ],
    )


async def generate_answer(
    *,
    question: str,
    context: str,
    sources: list[RetrievedChunk],
    document_summary: bool = False,
) -> LlmAnswer:
    """Ask the model one question against one rendered source list.

    Raises on any transport or protocol failure. The caller is expected to
    refuse rather than to retry: a request that reaches here has already been
    answered by retrieval, and a user waiting on a chat turn is not helped by a
    second thirty-second timeout.

    **Measured 6 September 2026**, two live calls against gemini-3.5-flash-lite,
    one question over two real chunks:

        1.33 s / 1.31 s round trip
        responseSchema honoured on the first attempt -- valid JSON, no prose to
        parse and no repair path needed
        both answers verified by check_grounding

    1.3 seconds is why this stays inside the request while ingestion does not:
    the same kind of measurement for a 55-page PDF was 430.84 s (CR-33).
    """
    if settings.LLM_FAKE_MODE:
        return _fake_answer(question, sources)

    url = f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL_NAME}:generateContent"

    # The instruction goes in system_instruction rather than being pasted on top
    # of the question. Prepending it would put the rules inside the same turn as
    # user-supplied text, where "ignore the above" is one sentence away.
    system_instruction = SYSTEM_INSTRUCTION

    if document_summary:
        system_instruction += "\n\n" + DOCUMENT_SUMMARY_INSTRUCTION
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": f"SOURCES\n\n{context}\n\nQUESTION\n\n{question}"}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }

    # A client per call. A shared client on the app lifespan would reuse the TLS
    # connection and is the right shape later; against a request that takes
    # seconds, the handshake is noise, and a module-level client would bind to
    # whichever event loop imported it.
    async with httpx.AsyncClient(timeout=settings.GEMINI_API_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY.get_secret_value()},
            json=payload,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Gemini {response.status_code}: {response.text}")

    body = response.json()
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        # A response with no candidate is what a safety block looks like, and it
        # is a 200. Without this it surfaces as a bare KeyError three frames up.
        raise RuntimeError(f"Gemini returned no candidate: {body}") from exc

    # responseMimeType is a request, not a guarantee, so this is validated
    # rather than trusted.
    return LlmAnswer.model_validate(json.loads(text))
