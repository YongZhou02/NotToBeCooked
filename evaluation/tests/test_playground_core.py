"""Playground core: frozen chunk versions, in-memory retrieval, and the run loop.

No database, no model and no gitignored runs are needed.
"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playground import make_chunks, run  # noqa: E402
from playground.toolkit import chunks as chunk_store  # noqa: E402
from playground.toolkit import embeddings  # noqa: E402
from playground.toolkit.chunks import ChunkVersionError, load_chunks, write_version  # noqa: E402
from playground.toolkit.kit import Toolkit  # noqa: E402
from playground.toolkit.retrieval import BM25, rrf  # noqa: E402
from playground.toolkit.trace import Trace  # noqa: E402

CHUNKS = [
    {"id": "b", "document_id": "doc2", "chunk_index": 0, "page_start": 1, "page_end": 1, "heading": None,
     "content": "Parsers build syntax trees from tokens.", "token_count": 7},
    {"id": "a1", "document_id": "doc1", "chunk_index": 1, "page_start": 2, "page_end": 2, "heading": None,
     "content": "A compiler translates source code into machine code.", "token_count": 9},
    {"id": "a0", "document_id": "doc1", "chunk_index": 0, "page_start": 1, "page_end": 1, "heading": "Intro",
     "content": "Lexical analysis splits text into tokens.", "token_count": 7},
]


def freeze(root: Path, version: str = "t1") -> dict:
    return write_version(version, CHUNKS, {"git_commit": "abc"}, root)


# --- chunk versions -------------------------------------------------------

def test_frozen_chunks_are_sorted_and_verified(tmp_path):
    manifest = freeze(tmp_path)
    loaded = load_chunks("t1", tmp_path)
    assert [c["id"] for c in loaded] == ["a0", "a1", "b"]
    assert manifest["chunk_count"] == 3 and len(manifest["chunks_sha256"]) == 64


def test_changed_chunks_file_is_refused(tmp_path):
    freeze(tmp_path)
    path = tmp_path / "t1" / "chunks.jsonl"
    path.write_bytes(path.read_bytes().replace(b"compiler", b"Compiler"))
    with pytest.raises(ChunkVersionError, match="has been changed"):
        load_chunks("t1", tmp_path)


def test_crlf_checkout_still_verifies(tmp_path):
    freeze(tmp_path)
    path = tmp_path / "t1" / "chunks.jsonl"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert len(load_chunks("t1", tmp_path)) == 3


def test_a_version_is_never_overwritten(tmp_path):
    freeze(tmp_path)
    with pytest.raises(ChunkVersionError, match="already exists"):
        freeze(tmp_path)


def test_make_chunks_refuses_to_overwrite_and_keeps_ids(tmp_path):
    run_folder = tmp_path / "20260101T000000Z"
    run_folder.mkdir()
    (run_folder / "chunks.json").write_text(json.dumps(CHUNKS), encoding="utf-8")
    (run_folder / "config.json").write_text(
        json.dumps({"git_commit": "deadbeef", "git_dirty": False, "embedding_model": "m", "corpus": {}}),
        encoding="utf-8",
    )
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "dataset.json").write_text(json.dumps(
        {"chunk_max_tokens": 350, "ocr": True, "chart_extraction": False, "top_k": 5, "candidate_limit": 50, "rrf_k": 60}
    ), encoding="utf-8")
    (dataset / "sources.json").write_text(json.dumps({"documents": [{"id": "doc1", "sha256": "x"}]}), encoding="utf-8")
    root = tmp_path / "chunks"
    manifest = make_chunks.freeze_from_run(run_folder, "v9", root, dataset)
    assert manifest["source_run_id"] == "20260101T000000Z" and manifest["git_commit"] == "deadbeef"
    assert manifest["chunker"]["settings"]["chunk_max_tokens"] == 350
    assert [c["id"] for c in load_chunks("v9", root)] == ["a0", "a1", "b"]
    with pytest.raises(ChunkVersionError):
        make_chunks.freeze_from_run(run_folder, "v9", root, dataset)
    with pytest.raises(ChunkVersionError):
        make_chunks.freeze_from_ingestion("v9", root, dataset)


def test_real_v1_matches_its_manifest():
    chunks = load_chunks("v1")
    assert len(chunks) == chunk_store.read_manifest("v1")["chunk_count"] == 198
    assert chunks == sorted(chunks, key=lambda c: (c["document_id"], c["chunk_index"]))


# --- in-memory retrieval --------------------------------------------------

def make_toolkit(tmp_path, vectors: np.ndarray, monkeypatch) -> Toolkit:
    manifest = freeze(tmp_path)
    manifest["chunker"] = {"settings": {"chunk_max_tokens": 350}}
    manifest["retrieval_settings"] = {"top_k": 5, "candidate_limit": 50, "rrf_k": 60}
    tk = Toolkit("t1", load_chunks("t1", tmp_path), manifest)
    tk._chunk_vectors = {"prod": vectors}
    tk._query_vectors = {}
    monkeypatch.setattr(embeddings, "resolve_model", lambda model="prod": "fake")
    return tk


def test_bm25_ranks_the_chunk_with_the_rare_word_first():
    index = BM25([c["content"] for c in CHUNKS])
    scores = index.scores("compiler translates code")
    assert int(np.argmax(scores)) == 1 and scores[0] == 0 and scores[2] == 0


def test_bm25_returns_only_matching_chunks(tmp_path, monkeypatch):
    tk = make_toolkit(tmp_path, np.eye(3, dtype=np.float32), monkeypatch)
    hits = tk.bm25("tokens", k=5)
    assert {h["chunk_id"] for h in hits} == {"a0", "b"}
    assert [h["rank"] for h in hits] == [1, 2]
    assert tk.bm25("zebra", k=5) == []


def test_dense_orders_by_cosine_and_keeps_the_shared_result_shape(tmp_path, monkeypatch):
    tk = make_toolkit(tmp_path, np.eye(3, dtype=np.float32), monkeypatch)  # chunk order: a0, a1, b
    tk._query_vectors[("prod", "q")] = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    hits = tk.dense("q", k=2)
    assert [h["chunk_id"] for h in hits] == ["a1", "a0"]
    assert set(hits[0]) == {"chunk_id", "document_id", "page_start", "page_end", "content", "score", "rank"}
    assert hits[0]["score"] == pytest.approx(0.9)


def result(chunk_id: str, rank: int) -> dict:
    return {"chunk_id": chunk_id, "document_id": "d", "page_start": 1, "page_end": 1,
            "content": chunk_id, "score": 0.0, "rank": rank}


def test_rrf_rewards_chunks_found_by_both_lists():
    first = [result("x", 1), result("y", 2), result("z", 3)]
    second = [result("y", 1), result("w", 2)]
    fused = rrf([first, second], k=3, rrf_k=60)
    assert [f["chunk_id"] for f in fused] == ["y", "x", "w"]
    assert fused[0]["score"] == pytest.approx(1 / 62 + 1 / 61)
    assert [f["rank"] for f in fused] == [1, 2, 3]


def test_rrf_ties_keep_first_appearance_order():
    fused = rrf([[result("p", 1)], [result("q", 1)]], k=2)
    assert [f["chunk_id"] for f in fused] == ["p", "q"]


def test_retrieval_calls_are_traced(tmp_path, monkeypatch):
    tk = make_toolkit(tmp_path, np.eye(3, dtype=np.float32), monkeypatch)
    with Trace() as trace:
        tk.bm25("tokens")
    assert [s["step"] for s in trace.steps] == ["retrieval.bm25"]


# --- embedding cache ------------------------------------------------------

def test_embedding_cache_means_a_second_call_embeds_nothing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(embeddings, "resolve_model", lambda model="prod": "org/fake-model")
    monkeypatch.setattr(embeddings, "_embed_documents", lambda texts, model: calls.append(len(texts)) or np.ones((len(texts), 4), np.float32))
    monkeypatch.setattr(embeddings, "_embed_query", lambda text, model: calls.append(1) or np.full(4, 0.5, np.float32))
    first = embeddings.embed_chunks(CHUNKS, "t1", root=tmp_path)
    second = embeddings.embed_chunks(CHUNKS, "t1", root=tmp_path)
    q1 = embeddings.embed_queries(["a", "b"], "t1", root=tmp_path)
    q2 = embeddings.embed_queries(["b", "a"], "t1", root=tmp_path)
    assert calls == [3, 1, 1] and np.array_equal(first, second) and np.array_equal(q1["a"], q2["a"])
    assert (tmp_path / "t1" / "org__fake-model" / "chunks.npy").exists()


def test_changed_chunk_text_invalidates_the_embedding_cache(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(embeddings, "resolve_model", lambda model="prod": "fake")
    monkeypatch.setattr(embeddings, "_embed_documents", lambda texts, model: calls.append(1) or np.ones((len(texts), 2), np.float32))
    embeddings.embed_chunks(CHUNKS, "t1", root=tmp_path)
    embeddings.embed_chunks([{**CHUNKS[0], "content": "different"}, *CHUNKS[1:]], "t1", root=tmp_path)
    assert len(calls) == 2


# --- the run loop ---------------------------------------------------------

def question(qid: str, split: str, answerable: bool = True, quote: str = "tokens") -> dict:
    groups = [{"id": f"{qid}-e1", "alternatives": [{"document_id": "doc1", "pdf_page": 1, "quote": quote}]}]
    return {"id": qid, "question": f"question {qid}", "category": "definition", "split": split,
            "origin": "synthetic", "answerable": answerable, "verified": True, "author": "me",
            "evidence_groups": groups if answerable else []}


def write_dataset(folder: Path, rows: list[dict]) -> None:
    folder.mkdir()
    (folder / "questions.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def fake_pipeline(tmp_path: Path) -> SimpleNamespace:
    file = tmp_path / "fake.py"
    file.write_text("# fake", encoding="utf-8")

    async def answer(q, tk):
        from playground.toolkit.trace import traced

        @traced("retrieval.fake")
        def search():
            return [{"chunk_id": "c", "document_id": "doc1", "page_start": 1, "page_end": 1,
                     "content": "Lexical analysis splits text into tokens.", "score": 1.0, "rank": 1}]

        return {"sources": search(), "columns": {"answer.shown": True, "answer.n_citations": 2}}

    return SimpleNamespace(NAME="fake", DESCRIPTION="test", answer=answer, __file__=str(file))


def test_read_questions_filters_like_run_eval(tmp_path):
    ineligible = {**question("q3", "dev"), "label_review": {"strict_retrieval_eligible": False}}
    write_dataset(tmp_path / "d", [question("q1", "dev"), question("q2", "test"), ineligible])
    assert [q["id"] for q in run.read_questions(tmp_path / "d")] == ["q1", "q2"]
    assert [q["id"] for q in run.read_questions(tmp_path / "d", ["test"])] == ["q2"]
    assert [q["id"] for q in run.read_questions(tmp_path / "d", limit=1)] == ["q1"]


def test_run_writes_readme_column_order_and_run_folder(tmp_path):
    questions = [question("q1", "dev"), question("q2", "test", answerable=False), question("q3", "dev", quote="absent")]
    config = {"chunks": {"version": "t1", "sha256": "s"}, "git_commit": "abc", "git_dirty": False}
    out, rows = asyncio.run(run.run_pipeline(fake_pipeline(tmp_path), questions, None, tmp_path / "runs", config))
    assert sorted(p.name for p in out.iterdir()) == ["config.json", "results.csv", "trace.jsonl"]
    with (out / "results.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        table = list(reader)
        header = reader.fieldnames
    assert header[:11] == ["run_id", "pipeline", "chunks_version", "question_id", "split", "category",
                           "origin", "answerable", "verified", "is_hard_case", "author"]
    assert header[11:18] == ["retrieval.hit@1", "retrieval.hit@3", "retrieval.hit@5", "retrieval.evidence_recall@5",
                             "retrieval.complete_evidence@5", "retrieval.mrr@5", "retrieval.ms"]
    assert header[18:] == ["answer.shown", "answer.n_citations"]
    assert [r["retrieval.hit@1"] for r in table] == ["1.0", "", "0.0"]  # unanswerable = not measured = empty
    assert table[0]["retrieval.ms"] != "" and table[1]["answer.shown"] == "1"
    assert table[0]["pipeline"] == "fake" and table[0]["chunks_version"] == "t1" and out.name == table[0]["run_id"]
    config_out = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config_out["pipeline"]["name"] == "fake" and len(config_out["pipeline"]["sha256"]) == 64
    trace_lines = [json.loads(line) for line in (out / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [t["question_id"] for t in trace_lines] == ["q1", "q2", "q3"]
    assert trace_lines[0]["steps"][0]["step"] == "retrieval.fake"


def test_a_failing_pipeline_is_recorded_and_the_run_continues(tmp_path):
    module = fake_pipeline(tmp_path)

    async def broken(q, tk):
        raise ValueError("boom")

    module.answer = broken
    config = {"chunks": {"version": "t1", "sha256": "s"}}
    out, rows = asyncio.run(run.run_pipeline(module, [question("q1", "dev")], None, tmp_path / "runs", config))
    assert rows[0]["question_id"] == "q1" and "retrieval.hit@1" not in rows[0]
    assert "boom" in (out / "trace.jsonl").read_text(encoding="utf-8")


def test_summary_averages_by_split(tmp_path):
    rows = [
        {"split": "dev", "retrieval.hit@1": 1.0, "retrieval.hit@3": 1.0, "retrieval.hit@5": 1.0,
         "retrieval.evidence_recall@5": 1.0, "retrieval.complete_evidence@5": 1.0, "retrieval.mrr@5": 1.0, "retrieval.ms": 2.0},
        {"split": "test", "retrieval.hit@1": 0.0, "retrieval.hit@3": 0.0, "retrieval.hit@5": 0.0,
         "retrieval.evidence_recall@5": 0.0, "retrieval.complete_evidence@5": 0.0, "retrieval.mrr@5": 0.0, "retrieval.ms": 4.0},
        {"split": "test"},
    ]
    summary = run.summarise_rows(rows)
    assert summary["all"]["retrieval.hit@1"] == 0.5 and summary["all"]["scored"] == 2
    assert summary["dev"]["retrieval.hit@1"] == 1.0 and "stress" not in summary
