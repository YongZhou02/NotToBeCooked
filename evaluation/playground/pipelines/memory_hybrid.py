"""Dense + BM25 fused with RRF, entirely in memory. Needs no database; a model for a radical pipeline."""

NAME = "memory_hybrid"
DESCRIPTION = "In-memory hybrid: dense (cached Jina embeddings) + BM25, 50 candidates each, RRF (k=60), top 5. No database."


async def answer(question: dict, tk) -> dict:
    text = question["question"]
    fused = tk.rrf([tk.dense(text, k=50), tk.bm25(text, k=50)], k=5, rrf_k=60)
    return {"sources": fused}
