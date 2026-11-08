"""Search over the frozen chunks. Every search returns the same list of dicts:

    {"chunk_id", "document_id", "page_start", "page_end", "content", "score", "rank"}

`rank` starts at 1. Two families:

* `prod_vector`, `prod_keyword`, `prod_hybrid` call the real apps/api search
  (pgvector cosine, Postgres full-text, weighted RRF) over the chunks seeded
  into the Postgres test database. They measure what students get.
* `dense`, `bm25`, `rrf` run in memory over the cached embeddings. No database,
  so a pipeline built from them runs anywhere. They are NOT the production
  search; `bm25` in particular is not Postgres `ts_rank`.

All are wrapped with `@traced`, so every call shows up in the run's trace.
`Retrieval` is the mixin the `Toolkit` (kit.py) is built on.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from typing import Any
from uuid import UUID

import numpy as np

from .embeddings import PROD, embed_chunks, embed_query
from .trace import traced

STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were what when "
    "where which who why with how do does did can".split()
)


def result(chunk: dict[str, Any], score: float, rank: int) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk["id"]),
        "document_id": chunk["document_id"],
        "page_start": chunk["page_start"],
        "page_end": chunk["page_end"],
        "content": chunk["content"],
        "score": float(score),
        "rank": rank,
    }


def tokenize(text: str) -> list[str]:
    """Lowercase words without stopwords. No stemming, to keep BM25 easy to reason about."""
    return [w for w in re.findall(r"\w+", text.casefold()) if w not in STOPWORDS]


class BM25:
    """Okapi BM25 over a fixed list of documents (k1=1.5, b=0.75)."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.counts = [Counter(tokenize(d)) for d in documents]
        self.lengths = np.array([sum(c.values()) for c in self.counts], dtype=float)
        self.average = float(self.lengths.mean()) if len(documents) else 0.0
        frequency = Counter(term for c in self.counts for term in c)
        n = len(documents)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in frequency.items()}

    def scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.counts))
        for term in set(tokenize(query)):
            if term not in self.idf:
                continue
            tf = np.array([c.get(term, 0) for c in self.counts], dtype=float)
            norm = self.k1 * (1 - self.b + self.b * self.lengths / (self.average or 1.0))
            scores += self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
        return scores


def top_k(scores: np.ndarray, k: int, positive_only: bool = False) -> list[int]:
    """Indexes of the k best scores. Ties keep chunk order, so results are repeatable."""
    order = np.argsort(-scores, kind="stable")
    return [int(i) for i in order[:k] if not positive_only or scores[i] > 0]


@traced("retrieval.rrf")
def rrf(result_lists: list[list[dict]], k: int = 5, rrf_k: int = 60) -> list[dict]:
    """Reciprocal rank fusion: score = sum of 1 / (rrf_k + rank) over the lists a chunk is in.

    Ties keep the order of first appearance, the same as the production fusion.
    """
    scores: dict[str, float] = {}
    first: dict[str, dict] = {}
    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            scores[item["chunk_id"]] = scores.get(item["chunk_id"], 0.0) + 1 / (rrf_k + rank)
            first.setdefault(item["chunk_id"], item)
    best = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:k]
    return [{**first[cid], "score": scores[cid], "rank": rank} for rank, cid in enumerate(best, start=1)]


class ProdDatabase:
    """The chunks seeded once into the Postgres test database, searched with the real app code.

    Mirrors run_eval.py: everything happens inside one outer transaction that is
    always rolled back on close, so nothing is left behind.
    """

    def __init__(self, manifest: dict[str, Any], top_k: int, candidate_limit: int, rrf_k: int) -> None:
        self.manifest = manifest
        self.settings = {"top_k": top_k, "candidate_limit": candidate_limit, "rrf_k": rrf_k}
        self.lock = asyncio.Lock()

    async def open(self, chunks: list[dict], vectors: np.ndarray) -> "ProdDatabase":
        import run_eval  # reuse its seed() and search() so this cannot drift from the old harness
        from app.db.database import engine
        from sqlmodel.ext.asyncio.session import AsyncSession

        self.run_eval, self.engine = run_eval, engine
        try:
            self.connection = await engine.connect()
        except Exception as error:
            raise RuntimeError(
                f"Postgres is not reachable ({error!r}). The prod_* searches need the test database "
                "from apps/api/.env; start it, or use the in-memory dense/bm25/rrf instead."
            ) from error
        self.outer = await self.connection.begin()
        self.session = AsyncSession(
            bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        # Insert in the dataset's document order (sources.json), as run_eval.py did. Postgres returns equal
        # ts_rank scores in physical row order, so a different insert order changes keyword and hybrid results.
        position = {d["id"]: i for i, d in enumerate(self.manifest["documents"])}
        ordered = sorted(range(len(chunks)), key=lambda i: (position[chunks[i]["document_id"]], chunks[i]["chunk_index"]))
        records = [{**chunks[i], "id": UUID(chunks[i]["id"])} for i in ordered]
        vectors = vectors[ordered]
        self.owner, self.course, self.files = await run_eval.seed(
            self.session, self.manifest, records, vectors.tolist()
        )
        self.file_ids = [f.id for f in self.files.values()]
        self.document_of = {f.id: key for key, f in self.files.items()}
        for method in ("vector", "keyword", "hybrid_rrf"):  # warm each path, as run_eval does
            await self.search(method, chunks[0]["content"][:200], vectors[0], 1)
        return self

    async def search(self, method: str, text: str, vector: np.ndarray, k: int) -> list[dict]:
        settings = {**self.settings, "top_k": k}
        async with self.lock:
            found = await self.run_eval.search(
                method, text, vector.tolist(), self.course.id, self.file_ids, self.session, settings
            )
        return [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": self.document_of[c.file_id],
                "page_start": c.page_start,
                "page_end": c.page_end,
                "content": c.content,
                "score": float(c.score),
                "rank": rank,
            }
            for rank, c in enumerate(found, start=1)
        ]

    async def close(self) -> bool:
        """Roll everything back. True when the temporary user is confirmed gone."""
        from app.schemas.user import User
        from sqlmodel.ext.asyncio.session import AsyncSession

        await self.session.close()
        await self.outer.rollback()
        await self.connection.close()
        async with AsyncSession(self.engine) as session:
            return await session.get(User, self.owner.id) is None


class Retrieval:
    """Search methods for the Toolkit. Needs: chunks_version, chunks, dataset_settings, model."""

    chunks_version: str
    chunks: list[dict[str, Any]]
    manifest: dict[str, Any]
    dataset_settings: dict[str, Any]
    model: str
    database: ProdDatabase | None = None

    # In-memory state, built on first use.
    def _vectors(self, model: str) -> np.ndarray:
        cache = self.__dict__.setdefault("_chunk_vectors", {})
        if model not in cache:
            cache[model] = embed_chunks(self.chunks, self.chunks_version, model)
        return cache[model]

    def _query_vector(self, query: str, model: str) -> np.ndarray:
        cache = self.__dict__.setdefault("_query_vectors", {})
        if (model, query) not in cache:
            cache[(model, query)] = embed_query(query, self.chunks_version, model)
        return cache[(model, query)]

    def _bm25_index(self) -> BM25:
        if "_bm25" not in self.__dict__:
            self._bm25 = BM25([c["content"] for c in self.chunks])
        return self._bm25

    async def open_database(self) -> ProdDatabase:
        """Seed the test database once. Called by the runner before timing, or lazily on first use."""
        if self.database is None:
            d = self.dataset_settings
            database = ProdDatabase(
                {"documents": self.manifest["documents"], "chunk_max_tokens": d["chunk_max_tokens"]},
                d["top_k"], d["candidate_limit"], d["rrf_k"],
            )
            self.database = await database.open(self.chunks, self._vectors(self.model))
        return self.database

    # Production search ---------------------------------------------------
    @traced("retrieval.prod_vector")
    async def prod_vector(self, query: str, k: int = 5) -> list[dict]:
        database = await self.open_database()
        return await database.search("vector", query, self._query_vector(query, self.model), k)

    @traced("retrieval.prod_keyword")
    async def prod_keyword(self, query: str, k: int = 5) -> list[dict]:
        database = await self.open_database()
        return await database.search("keyword", query, self._query_vector(query, self.model), k)

    @traced("retrieval.prod_hybrid")
    async def prod_hybrid(self, query: str, k: int = 5) -> list[dict]:
        database = await self.open_database()
        return await database.search("hybrid_rrf", query, self._query_vector(query, self.model), k)

    # In-memory search ----------------------------------------------------
    @traced("retrieval.dense")
    def dense(self, query: str, k: int = 5, model: str = PROD) -> list[dict]:
        """Cosine similarity against the cached chunk embeddings (vectors are unit length)."""
        scores = self._vectors(model) @ self._query_vector(query, model)
        return [result(self.chunks[i], scores[i], r) for r, i in enumerate(top_k(scores, k), start=1)]

    @traced("retrieval.bm25")
    def bm25(self, query: str, k: int = 5) -> list[dict]:
        """Okapi BM25 over chunk text. Only chunks sharing a word with the query are returned."""
        scores = self._bm25_index().scores(query)
        return [
            result(self.chunks[i], scores[i], r)
            for r, i in enumerate(top_k(scores, k, positive_only=True), start=1)
        ]

    rrf = staticmethod(rrf)
