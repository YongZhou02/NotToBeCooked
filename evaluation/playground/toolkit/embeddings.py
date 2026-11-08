"""Embeddings of chunks and queries, cached on disk so a second run embeds nothing.

    vectors = embed_chunks(chunks, "v1")           # numpy (n_chunks, dim), row order = chunks
    vector = embed_query("what is a pass?", "v1")  # numpy (dim,)

Production embedding is the only model implemented: it calls the same
`embed_text` / `embed_query` the app and run_eval.py use. Another model plugs in
by adding a branch to `_embed_documents` / `_embed_query`; the `model` argument
and the per-model cache folder are already in place.

Cache layout (gitignored):
    cache/embeddings/<chunks_version>/<model slug>/chunks.npy + chunks.json
    cache/embeddings/<chunks_version>/<model slug>/queries.jsonl
`chunks.json` records the chunk ids and the sha256 of every chunk's text, so a
cache made for different text is never reused.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from . import PLAYGROUND

CACHE = PLAYGROUND / "cache" / "embeddings"
PROD = "prod"


def resolve_model(model: str = PROD) -> str:
    """The real model name. "prod" means whatever the app is configured to use."""
    if model == PROD:
        from app.core.config import settings

        return settings.MODEL_TYPE
    raise NotImplementedError(
        f"Embedding model {model!r} is not implemented yet; only 'prod' (the app's own model) is."
    )


def model_slug(model: str = PROD) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", resolve_model(model))


def cache_dir(chunks_version: str, model: str = PROD, root: Path = CACHE) -> Path:
    return root / chunks_version / model_slug(model)


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_documents(texts: list[str], model: str) -> np.ndarray:
    resolve_model(model)
    from app.services.embeddings import embed_text

    return np.asarray(embed_text(texts), dtype=np.float32)


def _embed_query(text: str, model: str) -> np.ndarray:
    resolve_model(model)
    from app.services.embeddings import embed_query

    return np.asarray(embed_query(text), dtype=np.float32)


def embed_chunks(
    chunks: list[dict[str, Any]], chunks_version: str, model: str = PROD, root: Path = CACHE
) -> np.ndarray:
    """One vector per chunk, in the order of `chunks`. Embeds only on a cache miss."""
    folder = cache_dir(chunks_version, model, root)
    fingerprint = {"ids": [c["id"] for c in chunks], "text_sha256": [text_key(c["content"]) for c in chunks]}
    matrix_path, meta_path = folder / "chunks.npy", folder / "chunks.json"
    if matrix_path.exists() and meta_path.exists():
        if json.loads(meta_path.read_text(encoding="utf-8")) == fingerprint:
            return np.load(matrix_path)
    matrix = _embed_documents([c["content"] for c in chunks], model)
    if matrix.shape[0] != len(chunks):
        raise ValueError("The embedder returned a different number of vectors than chunks")
    folder.mkdir(parents=True, exist_ok=True)
    np.save(matrix_path, matrix)
    meta_path.write_text(json.dumps(fingerprint), encoding="utf-8")
    return matrix


def _load_queries(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {row["key"]: row["vector"] for row in rows}


def embed_queries(
    texts: list[str], chunks_version: str, model: str = PROD, root: Path = CACHE
) -> dict[str, np.ndarray]:
    """Vectors for many queries, embedding only the ones not cached. Keyed by query text."""
    path = cache_dir(chunks_version, model, root) / "queries.jsonl"
    known = _load_queries(path)
    missing = [t for t in dict.fromkeys(texts) if text_key(t) not in known]
    if missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for text in missing:
                vector = _embed_query(text, model).tolist()
                known[text_key(text)] = vector
                handle.write(json.dumps({"key": text_key(text), "text": text, "vector": vector}) + "\n")
    return {t: np.asarray(known[text_key(t)], dtype=np.float32) for t in texts}


def embed_query(text: str, chunks_version: str, model: str = PROD, root: Path = CACHE) -> np.ndarray:
    return embed_queries([text], chunks_version, model, root)[text]
