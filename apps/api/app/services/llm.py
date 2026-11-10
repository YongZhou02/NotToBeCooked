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

import asyncio
import json
import re
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, Field, field_validator

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

    @field_validator("answer", mode="before")
    @classmethod
    def canonicalise_marker_brackets(cls, value: Any) -> Any:
        """Accept visual bracket variants without changing marker numbers.

        Some providers render ``[5]`` as ``【5】`` or ``［5］``. These are the
        same source reference to a reader, so normalise only those exact numeric
        forms. Missing markers, unknown numbers and prose remain untouched and
        still have to pass the grounding gate.
        """
        if not isinstance(value, str):
            return value
        return re.sub(r"[【［]\s*(\d+)\s*[】］]", r"[\1]", value)


class LlmClaim(BaseModel):
    """One Groq answer claim with source numbers, before server rendering."""

    text: str = Field(..., min_length=1)
    markers: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)


class GroqCitation(BaseModel):
    """A source marker plus an ID for server-owned verbatim evidence."""

    marker: int = Field(..., ge=1)
    evidence_id: str = Field(..., min_length=3)


class GroqAnswer(BaseModel):
    """Structured Groq output: the server, not the model, prints ``[n]``."""

    claims: list[LlmClaim]
    grounded: bool
    citations: list[GroqCitation] = Field(default_factory=list)
    uncovered: str | None = None

    def render(self, evidence: dict[str, tuple[int, str]]) -> LlmAnswer:
        parts: list[str] = []
        for claim in self.claims:
            text = claim.text.strip()
            if re.search(r"(?:\[|【|［)\s*\d+\s*(?:\]|】|］)", text):
                raise ValueError("Groq claim text must not contain handwritten markers")
            markers = list(dict.fromkeys(claim.markers))
            if self.grounded and not markers:
                raise ValueError("Every grounded Groq claim needs a source marker")
            suffix = " ".join(f"[{marker}]" for marker in markers)
            parts.append(f"{text} {suffix}".rstrip())
        if not parts:
            raise ValueError("Groq returned no answer claims")
        citations: list[LlmCitation] = []
        for citation in self.citations:
            resolved = evidence.get(citation.evidence_id)
            if resolved is None:
                raise ValueError(f"Unknown Groq evidence ID: {citation.evidence_id}")
            marker, quote = resolved
            if marker != citation.marker:
                raise ValueError(
                    f"Evidence {citation.evidence_id} belongs to marker {marker}, "
                    f"not {citation.marker}"
                )
            citations.append(LlmCitation(marker=marker, quote=quote))
        return LlmAnswer(
            answer="\n\n".join(parts),
            grounded=self.grounded,
            citations=citations,
            uncovered=self.uncovered,
        )


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

# The same constraint in standard JSON Schema, for OpenAI-compatible providers.
_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "One answer claim without citation brackets.",
                    },
                    "markers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Source numbers supporting this claim.",
                    },
                },
                "required": ["text", "markers"],
            },
        },
        "grounded": {"type": "boolean"},
        "uncovered": {"type": ["string", "null"]},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "marker": {"type": "integer"},
                    "evidence_id": {"type": "string"},
                },
                "required": ["marker", "evidence_id"],
            },
        },
    },
    "required": ["claims", "grounded", "citations"],
}

_GROQ_CLAIM_INSTRUCTION = """
OUTPUT FORMAT OVERRIDE FOR THIS PROVIDER

Return the answer as `claims`, not as one `answer` string. Each claim has plain
`text` with no handwritten citation brackets and a `markers` array containing
the source numbers that support that claim. The server renders those numbers as
`[n]`. For every citation, copy an `evidence_id` from the EVIDENCE PASSAGES
catalogue; never write or paraphrase a quote. The server resolves that ID back
to the exact source text. For a refusal, return one plain claim with an empty
markers array, set grounded to false, and leave citations empty.

IMPORTANT: If `grounded` is true, every claim MUST have at least one integer
in its `markers` array. Never return `grounded: true` with empty markers.
""".strip()

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

# What the reader sees when the model cited nothing but still claimed the
# sources cover part of the question (`uncovered` set). Found 11 October 2026:
# asked about rrf_k, the model answered with no markers and no citations, and
# the reader got UNVERIFIED -- "citations could not be checked" -- when there
# were no citations to check. Not REFUSAL either: GLOSSARY.md defines rrf_k, so
# "the material does not cover this" would be false. What is true is that no
# passage was found to stand behind an answer.
NOTHING_CITED = (
    "No passage in your material could be found to support an answer, so none "
    "is shown. Try naming the document with @, or asking with the words the "
    "material uses."
)

# What the reader sees when the call to the model itself failed -- a timeout, a
# 5xx, a safety block. It used to be REFUSAL, which tells the reader their
# material has no answer when nobody has looked at the material at all; the same
# mistake UNVERIFIED was introduced to stop. This one says what happened and
# that trying again is reasonable.
GENERATION_FAILED = (
    "The answer could not be generated just now because the AI service did not "
    "respond. Your material was not checked, so please try again in a moment."
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


def _evidence_catalog(
    sources: list[RetrievedChunk],
) -> tuple[dict[str, tuple[int, str]], str]:
    """Create exact, server-owned evidence spans for Groq to reference by ID."""
    evidence: dict[str, tuple[int, str]] = {}
    rendered: list[str] = ["EVIDENCE PASSAGES"]
    for marker, source in enumerate(sources, start=1):
        parts = re.split(
            r"(?:\r?\n+|\s*▪\s*|(?<=[.!?])\s+)",
            source.content,
        )
        spans = [part.strip() for part in parts if part.strip()]
        if not spans:
            spans = [source.content.strip()]
        for index, quote in enumerate(spans, start=1):
            evidence_id = f"{marker}.{index}"
            evidence[evidence_id] = (marker, quote)
            rendered.append(f"{evidence_id}: {quote}")
    return evidence, "\n".join(rendered)


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
    history: str = "",
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

    # The instruction goes in system_instruction rather than being pasted on top
    # of the question. Prepending it would put the rules inside the same turn as
    # user-supplied text, where "ignore the above" is one sentence away.
    system_instruction = SYSTEM_INSTRUCTION

    if document_summary:
        system_instruction += "\n\n" + DOCUMENT_SUMMARY_INSTRUCTION

    user_turn = f"{history}SOURCES\n\n{context}\n\nQUESTION\n\n{question}"

    # Gemini first when both keys are set; Groq only when it is the sole key.
    if settings.llm_provider == "groq":
        evidence, evidence_block = _evidence_catalog(sources)
        return await _generate_groq(
            system_instruction,
            user_turn + "\n\n" + evidence_block,
            evidence,
        )
    return await _generate_gemini(system_instruction, user_turn)


async def _generate_groq(
    system_instruction: str,
    user_turn: str,
    evidence: dict[str, tuple[int, str]],
) -> LlmAnswer:
    """Groq's OpenAI-compatible chat completions, JSON-schema constrained.

    The free tier is token-per-minute limited, so a 429 is expected: honour
    `retry-after` (capped at 30 s) a bounded number of times.
    """
    payload: dict[str, Any] = {
        "model": settings.GROQ_MODEL_NAME,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": system_instruction + "\n\n" + _GROQ_CLAIM_INSTRUCTION,
            },
            {"role": "user", "content": user_turn},
        ],
        # Non-strict on purpose: `uncovered` must stay omittable (see
        # _RESPONSE_SCHEMA), which strict mode forbids. LlmAnswer validates.
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": False, "schema": _JSON_SCHEMA},
        },
        "reasoning_effort": "low",
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY.get_secret_value()}"}
    url = f"{settings.GROQ_API_BASE_URL}/chat/completions"

    protocol_retry = False
    async with httpx.AsyncClient(timeout=settings.GROQ_API_TIMEOUT_SECONDS) as client:
        while True:
            attempt = 0
            while True:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 429 or attempt >= settings.GROQ_MAX_RETRIES:
                    break
                attempt += 1
                try:
                    wait = float(response.headers.get("retry-after", "5"))
                except ValueError:
                    wait = 5.0
                await asyncio.sleep(min(max(wait, 1.0), 30.0))

            if response.status_code != 200:
                raise RuntimeError(f"Groq {response.status_code}: {response.text}")

            body = response.json()
            try:
                text = body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Groq returned no choice: {body}") from exc
            try:
                return GroqAnswer.model_validate(json.loads(text)).render(evidence)
            except ValueError as exc:
                if protocol_retry or "needs a source marker" not in str(exc):
                    raise
                protocol_retry = True
                payload["messages"].append({
                    "role": "user",
                    "content": (
                        "Your previous JSON was invalid. Every grounded claim "
                        "must include at least one valid source number in "
                        "markers. Return corrected JSON only."
                    ),
                })


async def _generate_gemini(system_instruction: str, user_turn: str) -> LlmAnswer:
    url = f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL_NAME}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        # `history` is render_history's block, or "" on a first question.
        "contents": [{"parts": [{"text": user_turn}]}],
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
