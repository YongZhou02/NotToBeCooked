"""Single entry point for the NTBC evaluation harness.

Run from the repository root:
uv run --project apps/api python evaluation/run_eval.py [--generate]
"""

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import json
import platform
import random
import statistics
import subprocess
import sys
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = Path(__file__).resolve().parent
API = ROOT / "apps/api"
sys.path.insert(0, str(API))
sys.path.insert(0, str(EVALUATION))

import numpy as np
import pypdfium2 as pdfium
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import engine
from app.db.vector_ops import SearchConfig, hybrid_search, keyword_search, vector_search
from app.routers import rag as rag_route
from app.schemas.chat import ChatRole, Message
from app.schemas.chunk import Chunk
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.schemas.rag import RagQueryRequest, RetrievedChunk
from app.schemas.user import User
from app.services.embeddings import embed_query, embed_text
from app.services.ingestion import create_chunk, extract_text, ingest_document
from scorers.pipeline import token_fidelity, vector_valid
from scorers.retrieval import covered_groups, normalize, retrieval_metrics
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

DATASET = EVALUATION / "datasets/cpt316/all"
METHODS = ("vector", "keyword", "hybrid_rrf")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def traced_generation(trace: dict) -> ExitStack:
    """Record what the route only logs: the model's draft and why it was rejected."""
    real_generate, real_check = rag_route.generate_answer, rag_route.check_grounding

    async def generate(**kwargs: Any) -> Any:
        try:
            draft = await real_generate(**kwargs)
        except Exception as error:
            trace["generation_error"] = repr(error)[:500]
            raise
        trace["draft"] = draft.model_dump(mode="json")
        return draft

    def check(*args: Any, **kwargs: Any) -> Any:
        report = real_check(*args, **kwargs)
        trace["grounding_ok"] = report.ok
        trace["grounding_problems"] = report.problems
        return report

    stack = ExitStack()
    stack.enter_context(patch.object(rag_route, "generate_answer", generate))
    stack.enter_context(patch.object(rag_route, "check_grounding", check))
    return stack


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def load_dataset(folder: Path) -> tuple[dict, list[dict], dict, dict]:
    manifest = {**read(folder / "dataset.json"), **read(folder / "sources.json")}
    all_rows = [
        json.loads(line)
        for line in (folder / "questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    rows = [
        row
        for row in all_rows
        if row.get("label_review", {}).get("strict_retrieval_eligible", True)
    ]
    questions = [
        {
            **{
                key: row[key]
                for key in ("id", "category", "split", "generation_review", "question")
            },
            "origin": row.get("origin", "synthetic"),
            "answerable": row.get("answerable", True),
        }
        for row in rows
    ]
    answers = {
        row["id"]: {
            "reference_answer": row["reference_answer"],
            "required_facts": row["required_facts"],
        }
        for row in rows
    }
    evidence = {row["id"]: {"groups": row["evidence_groups"]} for row in rows}
    if manifest["top_k"] != 5 or manifest["chunk_max_tokens"] < 1:
        raise ValueError(
            "This version scores top-5 and requires a positive chunk budget"
        )
    if manifest["ocr"] is not True or manifest["chart_extraction"] is not False:
        raise ValueError(
            "This text-only benchmark requires OCR on and chart extraction off"
        )
    ids = [q["id"] for q in questions]
    if (
        len(set(ids)) != len(ids)
        or set(ids) != set(answers)
        or set(ids) != set(evidence)
    ):
        raise ValueError(
            "Question/answer/evidence IDs must match exactly and be unique"
        )
    if any(q["split"] not in ("dev", "test", "stress") for q in questions):
        raise ValueError("Invalid development/test split")
    for question in questions:
        groups = evidence[question["id"]]["groups"]
        if not groups and not question["answerable"]:
            continue
        if not groups or len({g["id"] for g in groups}) != len(groups):
            raise ValueError(f"Missing/duplicate evidence groups: {question['id']}")
        if any(not g["alternatives"] for g in groups):
            raise ValueError(
                "Every evidence group needs at least one acceptable source"
            )
        for group in groups:
            for alternative in group["alternatives"]:
                if not normalize(alternative["quote"]) or alternative["pdf_page"] < 1:
                    raise ValueError(
                        "Evidence quotes must be nonblank and pages positive"
                    )
    return manifest, questions, answers, evidence


def parse_corpus(
    folder: Path, manifest: dict, out: Path
) -> tuple[list[dict], list[dict]]:
    """Independent PDFium text is a fidelity reference, not Docling's own output."""
    reference, items = [], []
    for source in manifest["documents"]:
        path = folder / source["path"]
        if sha(path) != source["sha256"]:
            raise ValueError(f"Corpus checksum changed: {source['path']}")
        document = pdfium.PdfDocument(str(path))
        if len(document) != source["pages"]:
            raise ValueError("Corpus page count changed")
        for i in range(len(document)):
            page = document[i]
            textpage = page.get_textpage()
            reference.append(
                {
                    "document_id": source["id"],
                    "page_start": i + 1,
                    "page_end": i + 1,
                    "content": textpage.get_text_range(),
                }
            )
            textpage.close()
            page.close()
        document.close()
        started = perf_counter()
        parsed = ingest_document(str(path))
        write(
            out / f"docling_structure_{source['id']}.json",
            [
                {
                    "label": getattr(getattr(item, "label", None), "value", "unknown"),
                    "content_layer": getattr(
                        getattr(item, "content_layer", None), "value", "body"
                    ),
                    "pages": [prov.page_no for prov in getattr(item, "prov", [])],
                    "text": getattr(item, "text", ""),
                }
                for item, _ in parsed.iterate_items()
            ],
        )
        for item in extract_text(parsed):
            items.append({**item, "document_id": source["id"]})
        print(f"Parsed {source['path']} in {perf_counter() - started:.1f}s", flush=True)
    write(out / "reference_pages.json", reference)
    write(out / "extracted_items.json", items)
    return reference, items


def fidelity_checks(
    reference: list[dict], items: list[dict], chunks: list[dict], evidence: dict
) -> dict:
    checks = []
    for page in reference:
        actual = " ".join(
            i["content"]
            for i in items
            if i["document_id"] == page["document_id"]
            and i["page_start"] <= page["page_start"] <= i["page_end"]
        )
        checks.append(
            {
                "document_id": page["document_id"],
                "pdf_page": page["page_start"],
                **token_fidelity(page["content"], actual),
            }
        )
    groups = [g for value in evidence.values() for g in value["groups"]]
    valid = covered_groups(reference, groups)
    if len(valid) != len(groups):
        raise ValueError(
            f"Answer key quotes are not in the supplied PDF: {sorted({g['id'] for g in groups} - valid)}"
        )
    # Same-page concatenation allows normal paragraph extraction boundaries.
    pages = [
        {
            **p,
            "content": " ".join(
                i["content"]
                for i in items
                if i["document_id"] == p["document_id"]
                and i["page_start"] <= p["page_start"] <= i["page_end"]
            ),
        }
        for p in reference
    ]
    extracted = covered_groups(pages, groups)
    chunked = covered_groups(chunks, groups)
    return {
        "pages": checks,
        "required_evidence_groups": len(groups),
        "extraction_evidence_coverage": len(extracted) / len(groups),
        "chunk_evidence_coverage": len(chunked) / len(groups),
        "missing_after_extraction": sorted(valid - extracted),
        "not_intact_in_any_chunk": sorted(valid - chunked),
        "note": "Token overlap does not prove relationship preservation. Evidence anchors test explicit supplied relationships; no original-image accuracy is measured.",
    }


async def seed(
    session: AsyncSession,
    manifest: dict,
    chunk_records: list[dict],
    vectors: list[list[float]],
) -> tuple[Any, Any, dict]:
    owner = User(
        email=f"pipeline-eval-{uuid4()}@example.invalid", hashed_password="not-a-login"
    )
    session.add(owner)
    await session.flush()
    assert owner.id is not None
    course = Course(
        user_id=owner.id,
        code="EVAL",
        name="Temporary pipeline evaluation",
        year=2026,
        sem=1,
    )
    session.add(course)
    await session.flush()
    assert course.id is not None
    folder = Folder(
        course_id=course.id, name="Temporary evaluation", is_root=True, sort_order=0
    )
    session.add(folder)
    await session.flush()
    assert folder.id is not None
    files = {}
    runs = {}
    for source in manifest["documents"]:
        file = FileRow(
            id=uuid4(),
            course_id=course.id,
            folder_id=folder.id,
            filename=Path(source["path"]).name,
            storage_key=f"evaluation/{uuid4()}.pdf",
            sha256=source["sha256"],
            mime_type="application/pdf",
            size_bytes=1,
            uploaded_at=datetime.now(UTC),
            status=FileStatus.READY,
            page_count=source["pages"],
        )
        session.add(file)
        await session.flush()
        assert file.id is not None
        run = IngestionRun(
            id=uuid4(),
            file_id=file.id,
            status=IngestionRunStatus.READY,
            is_active=True,
            chunker_version=f"eval-max-{manifest['chunk_max_tokens']}",
            embedding_model=settings.MODEL_TYPE,
            embedding_dim=settings.EMBEDDINGS_DIM,
        )
        session.add(run)
        await session.flush()
        files[source["id"]] = file
        runs[source["id"]] = run
    for record, vector in zip(chunk_records, vectors, strict=True):
        file = files[record["document_id"]]
        session.add(
            Chunk(
                id=record["id"],
                file_id=file.id,
                course_id=course.id,
                ingestion_run_id=runs[record["document_id"]].id,
                chunk_index=record["chunk_index"],
                page_start=record["page_start"],
                page_end=record["page_end"],
                heading=record["heading"],
                content=record["content"],
                token_count=record["token_count"],
                embedding=vector,
            )
        )
    await session.flush()
    return owner, course, files


async def search(
    method: str,
    text: str,
    vector: list[float],
    course_id: Any,
    file_ids: list,
    session: AsyncSession,
    manifest: dict,
) -> list[RetrievedChunk]:
    if not file_ids:
        raise ValueError("Evaluation scope must never be empty")
    if method == "vector":
        return await vector_search(
            vector, session, course_id, file_ids, top_k=manifest["top_k"]
        )
    if method == "keyword":
        rows = await keyword_search(
            text, session, course_id, file_ids, top_k=manifest["top_k"]
        )
        return [
            RetrievedChunk(
                chunk_id=c.id,
                file_id=c.file_id,
                course_id=c.course_id,
                filename=f.filename,
                page_start=c.page_start,
                page_end=c.page_end,
                heading=c.heading,
                content=c.content,
                score=float(score),
            )
            for c, f, score in rows
        ]
    return await hybrid_search(
        text,
        vector,
        course_id,
        session,
        file_ids,
        SearchConfig(
            final_limit=manifest["top_k"],
            vector_limit=manifest["candidate_limit"],
            keyword_limit=manifest["candidate_limit"],
            rrf_k=manifest["rrf_k"],
        ),
    )


def summary(rows: list[dict], checks: dict, out: Path) -> None:
    aggregates = []
    rows = [r for r in rows if r["metrics"]]
    for split in ("dev", "test", "stress"):
        for category in ("all", *sorted({r["category"] for r in rows})):
            for method in METHODS:
                selected = [
                    r
                    for r in rows
                    if r["split"] == split
                    and r["method"] == method
                    and (category == "all" or r["category"] == category)
                ]
                if not selected:
                    continue
                values = {
                    key: statistics.mean(r["metrics"][key] for r in selected)
                    for key in selected[0]["metrics"]
                }
                timings = [t for r in selected for t in r["retrieval_ms"]]
                aggregates.append(
                    {
                        "split": split,
                        "category": category,
                        "method": method,
                        "questions": len(selected),
                        **values,
                        "retrieval_median_ms": statistics.median(timings),
                        "retrieval_p95_ms": float(np.percentile(timings, 95)),
                    }
                )
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregates[0]))
        writer.writeheader()
        writer.writerows(aggregates)
    write(
        out / "summary.json",
        {
            "extraction": {
                "evidence_coverage": checks["extraction_evidence_coverage"],
                "chunk_evidence_coverage": checks["chunk_evidence_coverage"],
                "database_roundtrip": checks.get("database_roundtrip"),
            },
            "retrieval": aggregates,
            "limitations": [
                "Review status varies by question; see origin and verified on each row",
                "Text-transcribed PDFs; not original-image understanding",
                "DB retrieval latency excludes embedding, generation, HTTP, and UI",
            ],
        },
    )
    lines = [
        "# NTBC pipeline evaluation",
        "",
        "Source-labelled benchmark on text-transcribed PDFs, not a general RAG accuracy claim. Check each question's origin and review status.",
        "",
        "## Extraction and storage",
        "",
        f"Extraction evidence coverage: {checks['extraction_evidence_coverage']:.1%}",
        f"Evidence intact in a chunk: {checks['chunk_evidence_coverage']:.1%}",
        f"Database round-trip: {checks.get('database_roundtrip', 'not run')}",
        "",
        "## Retrieval",
        "",
        "| Split | Method | N | Hit@1 | Hit@5 | Evidence Recall@5 | Complete@5 | MRR@5 | Median ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregates:
        if row["category"] == "all":
            lines.append(
                f"| {row['split']} | {row['method']} | {row['questions']} | {row['hit@1']:.3f} | {row['hit@5']:.3f} | {row['evidence_recall@5']:.3f} | {row['complete_evidence@5']:.3f} | {row['mrr@5']:.3f} | {row['retrieval_median_ms']:.1f} |"
            )
    lines += [
        "",
        "Scores use fixed quote-and-page evidence groups, not semantic relevance judgments. See traces for false negatives / alternative passages to review. Query embedding and model load are excluded from DB retrieval timings and recorded separately. Repeated latency measurements do not increase the question count.",
        "",
        "Generation reviews are intentionally unscored until a reviewer supplies ratings. Citation quote matching is not semantic faithfulness or correctness.",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main(args: argparse.Namespace) -> None:
    folder = args.dataset.resolve()
    manifest, questions, answers, evidence = load_dataset(folder)
    if args.generate and (settings.LLM_FAKE_MODE or settings.llm_provider is None):
        raise ValueError(
            "Real generation requires LLM_FAKE_MODE=false and a GEMINI_API_KEY "
            "or GROQ_API_KEY"
        )
    if args.repeats < 1:
        raise ValueError("--repeats must be positive")
    if args.extract_only and args.generate:
        raise ValueError("Choose --extract-only or --generate, not both")
    out = EVALUATION / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    versions = {
        name: importlib.metadata.version(name)
        for name in (
            "docling",
            "docling-core",
            "torch",
            "sentence-transformers",
            "pypdfium2",
        )
    }
    git_commit, git_status = await asyncio.gather(
        asyncio.to_thread(git_output, "rev-parse", "HEAD"),
        asyncio.to_thread(git_output, "status", "--porcelain"),
    )
    run_config = {
        "created_at": datetime.now(UTC),
        "corpus": manifest,
        "git_commit": git_commit,
        "git_dirty": bool(git_status),
        "dataset_hashes": {
            name: sha(folder / name)
            for name in ("dataset.json", "sources.json", "questions.jsonl")
        },
        "source_hashes": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                Path(__file__),
                EVALUATION / "scorers/retrieval.py",
                EVALUATION / "scorers/pipeline.py",
                EVALUATION / "scorers/answer_quality.py",
                ROOT / "apps/api/app/services/ingestion.py",
                ROOT / "apps/api/app/services/embeddings.py",
                ROOT / "apps/api/app/db/vector_ops.py",
                ROOT / "apps/api/app/services/prompt.py",
                ROOT / "apps/api/app/services/llm.py",
                ROOT / "apps/api/app/routers/rag.py",
            ]
        },
        "versions": versions,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "embedding_model": settings.MODEL_TYPE,
        "embedding_dimension": settings.EMBEDDINGS_DIM,
        "generation_model": settings.llm_model_name if args.generate else None,
        "generation_method": args.generation_method,
        "repeats": args.repeats,
        "seed": 37,
        "scope": "single-turn, file-scoped production query; no HTTP/auth or original-image benchmark",
    }
    write(out / "config.json", run_config)
    print(f"Run directory: {out}", flush=True)
    # Scoped in this standalone process; production configuration is not edited.
    with patch.object(
        settings, "CHART_EXTRACTION_ENABLED", manifest["chart_extraction"]
    ):
        reference, items = await asyncio.to_thread(parse_corpus, folder, manifest, out)
    chunks = []
    for source in manifest["documents"]:
        own_items = [i for i in items if i["document_id"] == source["id"]]
        produced = await asyncio.to_thread(
            create_chunk, own_items, uuid4(), manifest["chunk_max_tokens"]
        )
        chunks.extend(
            {
                "id": uuid4(),
                "document_id": source["id"],
                **c.model_dump(exclude={"file_id"}),
            }
            for c in produced
        )
    write(out / "chunks.json", chunks)
    checks = fidelity_checks(reference, items, chunks, evidence)
    checks["over_budget_chunks"] = [
        str(c["id"]) for c in chunks if c["token_count"] > manifest["chunk_max_tokens"]
    ]
    write(out / "checks.json", checks)
    if args.extract_only:
        print(
            f"Extraction checks saved: {checks['extraction_evidence_coverage']:.1%}",
            flush=True,
        )
        return
    started = perf_counter()
    vectors = await asyncio.to_thread(embed_text, [c["content"] for c in chunks])
    run_config["document_embedding_seconds"] = perf_counter() - started
    if len(vectors) != len(chunks) or not all(
        vector_valid(v, settings.EMBEDDINGS_DIM) for v in vectors
    ):
        raise ValueError("Invalid document embeddings")
    # Public questions ONLY; no expected answers/evidence supplied to embedding or retrieval.
    queries = {}
    for q in questions:
        started = perf_counter()
        queries[q["id"]] = await asyncio.to_thread(embed_query, q["question"])
        q["embedding_ms"] = (perf_counter() - started) * 1000
        if not vector_valid(queries[q["id"]], settings.EMBEDDINGS_DIM):
            raise ValueError("Invalid query embedding")
    rows, reviews, generated_answers = [], [], []
    # Savepoints contain route-level commits; the outer transaction ALWAYS rolls back.
    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as session:
                owner, course, files = await seed(session, manifest, chunks, vectors)
                file_ids = [f.id for f in files.values()]
                reverse_files = {f.id: key for key, f in files.items()}
                stored = (
                    await session.exec(
                        select(Chunk).where(col(Chunk.file_id).in_(file_ids))
                    )
                ).all()
                expected = {
                    c["id"]: (c, v) for c, v in zip(chunks, vectors, strict=True)
                }
                checks["database_roundtrip"] = len(stored) == len(expected) and all(
                    c.content == expected[c.id][0]["content"]
                    and c.page_start == expected[c.id][0]["page_start"]
                    and c.page_end == expected[c.id][0]["page_end"]
                    and c.token_count == expected[c.id][0]["token_count"]
                    and np.allclose(c.embedding, expected[c.id][1], rtol=0, atol=1e-6)
                    and c.content_tsv is not None
                    for c in stored
                )
                if not checks["database_roundtrip"]:
                    raise ValueError("Database text/metadata/vector round-trip failed")
                write(out / "checks.json", checks)
                rng = random.Random(37)
                # Warm every retrieval path outside latency scoring.
                for method in METHODS:
                    await search(
                        method,
                        questions[0]["question"],
                        queries[questions[0]["id"]],
                        course.id,
                        file_ids,
                        session,
                        manifest,
                    )
                for q in questions:
                    methods = list(METHODS)
                    rng.shuffle(methods)
                    for method in methods:
                        timings, sources = [], []
                        for _ in range(args.repeats):
                            started = perf_counter()
                            sources = await search(
                                method,
                                q["question"],
                                queries[q["id"]],
                                course.id,
                                file_ids,
                                session,
                                manifest,
                            )
                            timings.append((perf_counter() - started) * 1000)
                        trace = [
                            {
                                **c.model_dump(mode="json"),
                                "document_id": reverse_files[c.file_id],
                                "rank": rank,
                            }
                            for rank, c in enumerate(sources, 1)
                        ]
                        if any(c.file_id not in file_ids for c in sources):
                            raise ValueError("Retrieval escaped evaluation file scope")
                        row = {
                            "question_id": q["id"],
                            "question": q["question"],
                            "category": q["category"],
                            "split": q["split"],
                            "method": method,
                            "query_embedding_ms": q["embedding_ms"],
                            "retrieval_ms": timings,
                            "sources": trace,
                            "origin": q["origin"],
                            "answerable": q["answerable"],
                            "metrics": retrieval_metrics(
                                trace, evidence[q["id"]]["groups"]
                            )
                            if q["answerable"]
                            else None,
                        }
                        if (
                            args.generate
                            and (args.generate_all or q["generation_review"])
                            and method == args.generation_method
                        ):
                            started = perf_counter()
                            # Standalone adapter swaps ONLY retrieval results. The production
                            # route assembles context, calls Gemini, verifies citations and stores messages.
                            trace_record: dict[str, Any] = {}
                            with (
                                patch.object(
                                    rag_route,
                                    "_retrieve",
                                    AsyncMock(return_value=sources),
                                ),
                                traced_generation(trace_record),
                            ):
                                result = await rag_route.query(
                                    RagQueryRequest(
                                        question=q["question"],
                                        course_id=course.id,
                                        file_ids=file_ids,
                                    ),
                                    session,
                                    {"sub": str(owner.id)},
                                )
                            row["generation_ms"] = (perf_counter() - started) * 1000
                            row["response"] = result.model_dump(mode="json")
                            row["generation_trace"] = trace_record
                            messages = (
                                await session.exec(
                                    select(Message).where(
                                        col(Message.conversation_id)
                                        == result.conversation_id,
                                        col(Message.role) == ChatRole.ASSISTANT,
                                    )
                                )
                            ).all()
                            row["scope_snapshots"] = [
                                m.scope_snapshot for m in messages
                            ]
                            generated_answers.append(
                                {
                                    "question_id": q["id"],
                                    "method": method,
                                    "category": q["category"],
                                    "split": q["split"],
                                    "origin": q["origin"],
                                    "answerable": q["answerable"],
                                    "sources": trace,
                                    "response": row["response"],
                                    "generation_ms": row["generation_ms"],
                                    "scope_snapshots": row["scope_snapshots"],
                                    "generation_trace": trace_record,
                                }
                            )
                            write(out / "generation_answers.json", generated_answers)
                            reviews.append(
                                {
                                    "question_id": q["id"],
                                    "method": method,
                                    "question": q["question"],
                                    "answer": result.answer,
                                    "reference_answer": answers[q["id"]][
                                        "reference_answer"
                                    ],
                                    "required_facts": answers[q["id"]][
                                        "required_facts"
                                    ],
                                    "sources": trace,
                                    "citations": row["response"]["citations"],
                                    "reviewer": None,
                                    "faithfulness": None,
                                    "correctness": None,
                                    "completeness": None,
                                    "citation_support": None,
                                    "notes": "",
                                }
                            )
                            write(out / "generation_reviews.json", reviews)
                        rows.append(row)
                        # Incremental files survive a later model/network failure.
                        with (out / "results.jsonl").open(
                            "a", encoding="utf-8"
                        ) as handle:
                            handle.write(
                                json.dumps(row, ensure_ascii=False, default=str) + "\n"
                            )
                    print(f"Evaluated {q['id']} ({q['split']})", flush=True)
        finally:
            await outer.rollback()
    # Confirm the route's commits did not leak the temporary evaluation user.
    async with AsyncSession(engine) as session:
        checks["rollback_verified"] = await session.get(User, owner.id) is None
    write(out / "checks.json", checks)
    write(out / "config.json", run_config)
    write(out / "generation_reviews.json", reviews)
    write(out / "generation_answers.json", generated_answers)
    summary(rows, checks, out)
    if not checks["rollback_verified"]:
        raise RuntimeError("Evaluation database rollback verification failed")
    print(f"Completed; database rolled back. Report: {out / 'report.md'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Call the configured real model for the 15 review questions",
    )
    parser.add_argument(
        "--generate-all",
        action="store_true",
        help="With --generate, answer every question, not only the review set",
    )
    parser.add_argument("--generation-method", choices=METHODS, default="hybrid_rrf")
    parser.add_argument("--repeats", type=int, default=3)
    configure_logging()
    asyncio.run(main(parser.parse_args()))
