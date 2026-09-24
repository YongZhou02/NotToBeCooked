"""Prompt assembly for the generation layer.

Pure functions only: no network, no settings, no event loop. What goes into
the context block is dictated by what `Citation` must be able to carry back.
"""

from app.schemas.rag import RetrievedChunk

# Rewritten 6 September 2026 after measuring the loose version against Gemini.
#
# The first draft ended with "Keep quotes to one or two sentences at most --
# just enough to support the claim", after four paragraphs insisting the quote
# be findable in the source. Asked a real question over a real chunk, the model
# returned the entire three-sentence chunk as its quote: verbatim, verifiable,
# and useless to a reader trying to see which line carried the claim. A soft
# preference at the end of a section about exactness loses to the exactness.
#
# The rewrite states the limit first, gives the reason from the reader's side,
# and shows a worked example on unrelated material. Re-measured on the same
# question and sources: two single-sentence quotes, one per claim.
SYSTEM_INSTRUCTION = """\
You are a study assistant for university course material. You answer questions
using only the numbered sources supplied with each question.

CITING
Every factual statement in your answer must be followed by a marker naming the
source it came from, written as [1], [2], and so on. Numbering starts at 1 and
refers only to sources that appear in the list you were given; never write a
number that is not in that list. A factual statement with no marker is not
permitted.

The markers must appear in the answer text itself, even though you also list
the citations separately. Every marker you list must appear in the answer, and
every marker in the answer must be listed.

USING THE SOURCES
The sources may be incomplete, or may answer only part of the question. When
that happens, answer only the part they cover.

Every claim in your answer — every fact, number, date, definition, name and
conclusion — must come from the sources. Do not add, complete or infer a claim
from your knowledge, even when you are confident that it is correct, and
even when it would make the answer more useful.

You may rephrase, summarise and organise the material freely, and you may
combine two or more sources to reach a conclusion, provided every source you
relied on is cited.

WHEN THE SOURCES DO NOT ANSWER THE QUESTION
If none of the sources are relevant to the question, do not answer it. Set
grounded to false, leave citations empty, and use answer to say plainly that
the supplied material does not cover the question. Do not guess and do not
fall back on your own knowledge.

If the sources answer only part of the question, answer that part normally
with citations, set grounded to true, and put the part the material does not
cover in the `uncovered` field -- one sentence, naming what is missing.

Leave `uncovered` out entirely when the sources answer the whole question. Do
not send it empty: an empty `uncovered` claims a gap and then does not say what
it is, and the answer is rejected.

QUOTES
Each citation must carry a quote: the one sentence in the source that supports
the claim, or the clause within that sentence which carries it, copied word for
word.

One sentence. Two only when the claim genuinely spans both. Never a paragraph
and never the whole source. A reader who opens a citation is looking for the
line you relied on; a quote that contains everything points at nothing.

Copy it exactly. Do not paraphrase it, do not tidy it up, do not correct its
punctuation or spelling, and do not join two separated sentences together. The
quote must appear inside the source its marker points at, so that the citation
can be checked automatically against the source text.

For example, given a source reading

    HTTP responses may be cached by any intermediary unless they say otherwise.
    A response marked private may be stored by the browser that requested it but
    not by a shared cache, which is what makes it unsuitable for CDN delivery.

a claim about CDNs is cited with

    "not by a shared cache, which is what makes it unsuitable for CDN delivery"

and not with the whole passage.
"""
DOCUMENT_SUMMARY_INSTRUCTION = """
DOCUMENT SUMMARY MODE

The user is asking for a comprehensive explanation of one complete document.

Before writing the answer, inspect all supplied sources from the beginning,
middle, and end of the document.

Organize the answer by the document's major topics in document order. Explain
each distinct concept in plain language. Do not stop after explaining only the
first few sources.

Use a clear heading for every major topic. Merge repeated information instead
of repeating it.

The answer does not need to reproduce every sentence, but it must represent
the complete document rather than only its opening pages.

Continue following all citation and verbatim quote rules from the main system
instruction.
"""

# Selection policy.
#
# There is deliberately no score threshold here. `RetrievedChunk.score` carries
# two incompatible scales depending on which retrieval path produced it:
# `vector_search` returns 1 - cosine_distance (~0.3-1.0), while `hybrid_search`
# returns RRF scores (~0.009-0.033). A single threshold would pass everything on
# one path and reject everything on the other, silently. Score filtering belongs
# in retrieval's SearchConfig, which knows which path ran; this layer only caps
# how many sources reach the model.
#
# A backstop, not the main limit: RagQueryRequest.top_k (default 5, max 20)
# already bounds what retrieval returns. This only bites when top_k is large.
_MAX_SOURCES = 8


def build_context(
    chunks: list[RetrievedChunk],
    *,
    max_sources: int | None = _MAX_SOURCES,
) -> tuple[str, list[RetrievedChunk]]:
    """Render retrieved chunks as a numbered, citable source list.

    Returns the rendered context and the chunks that actually went into it,
    which may be shorter than `chunks`. Markers are numbered against that
    second value, not against `chunks`, so the caller must resolve
    `citation.marker` against it — indexing back into `chunks` will silently
    return the wrong source as soon as the selection policy drops anything
    other than a tail.
    """

    selected = chunks if max_sources is None else chunks[:max_sources]

    blocks: list[str] = []

    for marker, chunk in enumerate(selected, start=1):
        if chunk.page_start is None:
            page = ""
        elif chunk.page_end is None or chunk.page_start == chunk.page_end:
            page = f" (p.{chunk.page_start})"
        else:
            page = f" (p.{chunk.page_start}-{chunk.page_end})"

        heading = f" — {chunk.heading}" if chunk.heading is not None else ""

        header = f"[{marker}] {chunk.filename}{page}{heading}"

        blocks.append(f"{header}\n{chunk.content}")

    return "\n\n".join(blocks), selected
