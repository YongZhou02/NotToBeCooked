import threading

import torch
from sentence_transformers import SentenceTransformer

from app.core.config import settings

_active_model: SentenceTransformer | None = None

"""Design decision of embeddings
Jina embeddings only support text. The project may explore Image and Audio
embeddings as see fit in the future. It may implement flash attention for
faster embeds.

Jina model at 32k embedding window allows:
1. see big picture via document-level embedding, that is embed entire document
at once to see document-level similarity
2. late chunking by feeding 10k tokens at once, forward pass once, then slice
it into 500 tokens
"""


def _load_model():
    is_cuda = torch.cuda.is_available()
    device = "cuda" if is_cuda else "cpu"

    model_kwargs = {}
    config_kwargs = {}

    if is_cuda:
        model_kwargs["dtype"] = torch.bfloat16
        try:
            import flash_attn  # type: ignore # noqa: F401

            config_kwargs["_attn_implementation"] = "flash_attention_2"
        except ImportError:
            pass

    return SentenceTransformer(
        settings.MODEL_TYPE,
        trust_remote_code=True,
        device=device,
        model_kwargs=model_kwargs,
        config_kwargs=config_kwargs,
    )


# Held only while the model is first loaded. Two ingestions that start in the
# same second both reach `_get_model` from worker threads (processing.py runs
# parse, chunk and embed through `asyncio.to_thread`). Without the lock each
# loads its own copy at the same moment, and loading is not thread-safe:
# transformers switches torch's process-wide default dtype while it builds the
# model. Measured 24 September 2026 -- one of two concurrent loads came back
# with 290 of its 310 base weights in float32 instead of bfloat16, and every
# `encode` on it raised "expected m1 and m2 to have the same dtype". The broken
# copy is the one that stays, so every later ingestion failed until restart.
_model_lock = threading.Lock()


# global singleton lazy loading model
def _get_model():
    global _active_model
    if _active_model is None:
        with _model_lock:
            # Checked again: the thread that waited here must not load a second
            # copy once the first thread has finished.
            if _active_model is None:
                _active_model = _load_model()
    return _active_model


def embed_query(query: str) -> list[float]:
    """Used to vectorise a user's query"""
    return (
        _get_model()
        .encode(
            [query],
            show_progress_bar=False,
            normalize_embeddings=True,
            task="retrieval",
            prompt_name="query",
        )[0]
        .tolist()
    )


def embed_text(texts: list[str]) -> list[list[float]]:
    """Used to build vector db with batch embeddings"""
    return (
        _get_model()
        .encode(
            texts,
            batch_size=settings.BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,
            task="retrieval",
            prompt_name="document",
        )
        .tolist()
    )


def get_tokenizer():
    model = _get_model()
    tokenizer = model.tokenizer
    return tokenizer


def count_token(text):
    tokenizer = get_tokenizer()
    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False,
    )
    return len(token_ids)


if __name__ == "__main__":
    """Try running this file directly to ensure embeddings work locally"""
    print("Query Embedding:", embed_query("Hello world"))
    print("Text Embedding:", embed_text(["First document text", "Second document text"]))
