"""The object a pipeline receives as `tk`.

    async with Toolkit.open("v1") as tk:
        hits = await tk.prod_hybrid("what is a pass?")     # production search, Postgres
        hits = tk.dense("what is a pass?", k=50)           # in memory, no database
        fused = tk.rrf([tk.dense(q, 50), tk.bm25(q, 50)], k=5)

It holds the frozen chunks and the handles the toolkit parts share, so a part
is a method call instead of a pile of arguments. The test database is only
opened when a `prod_*` search needs it, and is always rolled back on exit.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .chunks import CHUNKS_ROOT, load_chunks, read_manifest
from .embeddings import PROD, embed_chunks, embed_queries, resolve_model
from .retrieval import Retrieval


class Toolkit(Retrieval):
    def __init__(
        self,
        chunks_version: str,
        chunks: list[dict[str, Any]],
        manifest: dict[str, Any],
        model: str = PROD,
        dataset_settings: dict[str, Any] | None = None,
    ) -> None:
        self.chunks_version = chunks_version
        self.chunks = chunks
        self.manifest = manifest
        self.model = model
        self.dataset_settings = dataset_settings or {
            "chunk_max_tokens": manifest["chunker"]["settings"]["chunk_max_tokens"],
            **manifest["retrieval_settings"],
        }
        self.database = None

    @classmethod
    def open(cls, chunks_version: str, model: str = PROD, root: Path = CHUNKS_ROOT) -> "Toolkit":
        """Load a chunk version (verifying its sha256). Use as `async with Toolkit.open("v1") as tk`."""
        return cls(chunks_version, load_chunks(chunks_version, root), read_manifest(chunks_version, root), model)

    @property
    def embedding_model(self) -> str:
        return resolve_model(self.model)

    async def prepare(self, queries: list[str], database: bool = False) -> None:
        """Do the slow, cacheable work up front so it is not counted in per-question timings."""
        await asyncio.to_thread(embed_chunks, self.chunks, self.chunks_version, self.model)
        vectors = await asyncio.to_thread(embed_queries, queries, self.chunks_version, self.model)
        self.__dict__.setdefault("_query_vectors", {}).update({(self.model, q): v for q, v in vectors.items()})
        if database:
            await self.open_database()

    async def close(self) -> None:
        if self.database is not None:
            confirmed = await self.database.close()
            self.database = None
            if not confirmed:
                raise RuntimeError("Evaluation database rollback verification failed")

    async def __aenter__(self) -> "Toolkit":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
