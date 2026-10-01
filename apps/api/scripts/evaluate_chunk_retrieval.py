import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings
from app.db.database import async_session_maker
from app.db.vector_ops import SearchConfig, hybrid_search
from app.schemas.chunk import Chunk, ChunkCreate
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.schemas.user import User
from app.services.embeddings import embed_query, embed_text
from app.services.ingestion import create_chunk, extract_text, ingest_document

SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
DATASET_PATH = API_DIR / "evaluation" / "controlled_chunk_retrieval_questions.json"


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(questions, list):
        raise ValueError("Evaluation dataset must be a list")

    quantity = len(questions)
    if not 15 <= quantity <= 20:
        raise ValueError("Question quantity must be between 15 and 20")

    required_fields = {
        "id",
        "question",
        "expected_pages",
        "acceptable_evidence",
    }
    seen_ids = set()

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise ValueError(f"Question at index {index} must be object")

        missing_fields = required_fields - question.keys()

        if missing_fields:
            raise ValueError(
                f"Question at index {index} is missing fields: {sorted(missing_fields)}"
            )

        question_id = question["id"]
        question_text = question["question"]

        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Question in index {index} must have a non-empty id")
        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError(f"Question in index {index} must have a non-empty question-text ")
        if question_id in seen_ids:
            raise ValueError(f"Duplicate question id: {question_id!r}")
        seen_ids.add(question_id)

        expected_pages = question["expected_pages"]
        acceptable_evidence = question["acceptable_evidence"]

        if (
            not isinstance(expected_pages, list)
            or not expected_pages
            or not all(type(page) is int and page > 0 for page in expected_pages)
        ):
            raise ValueError(f"Question {question_id!r} must have positive integer expected_pages")

        if (
            not isinstance(acceptable_evidence, list)
            or not acceptable_evidence
            or not all(
                isinstance(evidence, str) and evidence.strip() for evidence in acceptable_evidence
            )
        ):
            raise ValueError(f"Question {question_id!r} must have non-empty acceptable_evidence")

    return questions


def build_database_chunks(
    chunk_creates: list[ChunkCreate],
    embeddings: list[list[float]],
    course_id: UUID,
    ingestion_run_id: UUID,
) -> list[Chunk]:
    database_chunks = []

    for chunk_create, embedding in zip(
        chunk_creates,
        embeddings,
        strict=True,
    ):
        database_chunk = Chunk(
            file_id=chunk_create.file_id,
            course_id=course_id,
            ingestion_run_id=ingestion_run_id,
            chunk_index=chunk_create.chunk_index,
            page_start=chunk_create.page_start,
            page_end=chunk_create.page_end,
            heading=chunk_create.heading,
            content=chunk_create.content,
            token_count=chunk_create.token_count,
            embedding=embedding,
        )
        database_chunks.append(database_chunk)

    return database_chunks


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    args = parser.parse_args()

    return args


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


# check if the page number and "at least one" evidence are matched
def is_relevant_chunk(chunk, question: dict) -> bool:
    expected_pages = question["expected_pages"]
    acceptable_evidence = question["acceptable_evidence"]

    page_matches = (
        chunk.page_start is not None
        and chunk.page_end is not None
        and any(chunk.page_start <= page <= chunk.page_end for page in expected_pages)
    )

    content = normalize_text(chunk.content)
    evidence_matches = any(normalize_text(evidence) in content for evidence in acceptable_evidence)
    return page_matches and evidence_matches


# rank of the first relevant chunk, counted from 1; None when none was retrieved
def first_relevant_rank(results, question: dict) -> int | None:
    for rank, chunk in enumerate(results, start=1):
        if is_relevant_chunk(chunk, question):
            return rank
    return None


# Hit@k and Recall@1 are yes/no per question; MRR gives rank 1 -> 1, rank 2 -> 1/2, ...
# and a miss -> 0, so it still separates two configurations that tie on both
def summarize_ranks(ranks: list[int | None]) -> dict[str, float]:
    total = len(ranks)
    return {
        "hit_at_k": sum(rank is not None for rank in ranks) / total,
        "recall_at_1": sum(rank == 1 for rank in ranks) / total,
        "mrr": sum(1 / rank for rank in ranks if rank is not None) / total,
    }


async def evaluate_configuration(
    label: str,
    questions: list[dict],
    query_vectors: dict[str, list[float]],
    course_id: UUID,
    evaluation_file_id: UUID,
    session,
    config: SearchConfig,
) -> list[int | None]:
    ranks = []

    for question in questions:
        results = await hybrid_search(
            query_text=question["question"],
            query_vector=query_vectors[question["id"]],
            course_id=course_id,
            session=session,
            file_ids=[evaluation_file_id],
            config=config,
        )
        rank = first_relevant_rank(results, question)
        ranks.append(rank)
        print(f"{label} {question['id']}: {'MISS' if rank is None else f'rank {rank}'}")

    k = config.final_limit
    total = len(ranks)
    hits = sum(rank is not None for rank in ranks)
    top_ranks = sum(rank == 1 for rank in ranks)
    metrics = summarize_ranks(ranks)
    print(f"{label} Hit@{k}: {hits}/{total}={metrics['hit_at_k']:.1%}")
    print(f"{label} Recall@1: {top_ranks}/{total}={metrics['recall_at_1']:.1%}")
    # ranks past k are never seen, so this is MRR@k; equal to full MRR when Hit@k is 100%
    print(f"{label} MRR@{k}: {metrics['mrr']:.3f}")

    return ranks


def print_comparison(questions: list[dict], ranks_350, ranks_500, k: int) -> None:
    metrics_350 = summarize_ranks(ranks_350)
    metrics_500 = summarize_ranks(ranks_500)

    print("\nComparison (350 vs 500):")
    print(f"  Hit@{k}:    {metrics_350['hit_at_k']:.1%} vs {metrics_500['hit_at_k']:.1%}")
    print(f"  Recall@1: {metrics_350['recall_at_1']:.1%} vs {metrics_500['recall_at_1']:.1%}")
    print(f"  MRR@{k}:    {metrics_350['mrr']:.3f} vs {metrics_500['mrr']:.3f}")

    differing = [
        (question["id"], rank_350, rank_500)
        for question, rank_350, rank_500 in zip(questions, ranks_350, ranks_500, strict=True)
        if rank_350 != rank_500
    ]
    print(f"Questions ranked differently: {len(differing)}/{len(questions)}")
    for question_id, rank_350, rank_500 in differing:
        print(f"  {question_id}: 350 rank {rank_350}, 500 rank {rank_500}")

    recall_tied = metrics_350["recall_at_1"] == metrics_500["recall_at_1"]
    mrr_tied = math.isclose(metrics_350["mrr"], metrics_500["mrr"])
    if recall_tied and mrr_tied:
        print("Recall@1 and MRR both tie: the corpus is too easy to separate the configurations")


async def main() -> None:
    args = parse_args()
    pdf_path = args.pdf_path
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("PDF file must have a .pdf extension")
    print(f"PDF path: {pdf_path}")

    questions = load_questions(DATASET_PATH)
    print(f"Loaded {len(questions)} evaluation questions")

    query_vectors = {}

    for question in questions:
        question_id = question["id"]
        question_text = question["question"]

        vector = embed_query(question_text)

        query_vectors[question_id] = vector

    document = ingest_document(pdf_path)
    items = extract_text(document)
    if not items:
        raise ValueError("No text were extracted")
    print(f"Extracted {len(items)} items")
    page_count = max(item["page_end"] for item in items)
    evaluation_file_id = uuid4()
    chunks_350 = create_chunk(
        items,
        evaluation_file_id,
        max_token=350,
    )
    chunks_500 = create_chunk(
        items,
        evaluation_file_id,
        max_token=500,
    )
    print(f"Size 350 produced {len(chunks_350)} chunks")
    print(f"Size 500 produced {len(chunks_500)} chunks")

    texts_350 = [item.content for item in chunks_350]
    texts_500 = [item.content for item in chunks_500]

    print("\nChecking whether every question has a valid gold chunk...")

    invalid_questions = []

    for question in questions:
        gold_350 = [chunk for chunk in chunks_350 if is_relevant_chunk(chunk, question)]
        gold_500 = [chunk for chunk in chunks_500 if is_relevant_chunk(chunk, question)]

        print(f"{question['id']}: gold_350={len(gold_350)}, gold_500={len(gold_500)}")

        if not gold_350 or not gold_500:
            invalid_questions.append(question["id"])

    print(f"Invalid questions: {invalid_questions}")

    if invalid_questions:
        raise ValueError(
            f"Questions have no valid gold chunk in one or both configurations: {invalid_questions}"
        )
    # Temporary: stop before the slow embedding and database steps.

    embeddings_350 = embed_text(texts_350)
    embeddings_500 = embed_text(texts_500)

    print(f"350 embeddings: {len(embeddings_350)}")
    print(f"500 embeddings: {len(embeddings_500)}")
    print(f"Embedding dimension: {len(embeddings_350[0])}")
    assert len(chunks_350) == len(embeddings_350)
    assert len(chunks_500) == len(embeddings_500)

    course_id = uuid4()
    run_350_id = uuid4()
    run_500_id = uuid4()

    database_chunks_350 = build_database_chunks(
        chunks_350,
        embeddings_350,
        course_id,
        run_350_id,
    )
    database_chunks_500 = build_database_chunks(chunks_500, embeddings_500, course_id, run_500_id)

    print(f"350 database chunks: {len(database_chunks_350)}")
    print(f"500 database chunks: {len(database_chunks_500)}")
    assert all(chunk.file_id == evaluation_file_id for chunk in database_chunks_350)
    assert all(chunk.file_id == evaluation_file_id for chunk in database_chunks_500)
    assert all(chunk.course_id == course_id for chunk in database_chunks_350 + database_chunks_500)
    assert all(chunk.ingestion_run_id == run_350_id for chunk in database_chunks_350)
    assert all(chunk.ingestion_run_id == run_500_id for chunk in database_chunks_500)

    async with async_session_maker() as session:
        try:
            print("Database evaluation session opened")
            evaluation_user_id = uuid4()

            evaluation_user = User(
                id=evaluation_user_id,
                email=f"chunk-evaluation-{evaluation_user_id}@example.invalid",
                display_name="Chunk Retrieval Evaluation",
                hashed_password="not-a-real-password",
            )
            session.add(evaluation_user)
            await session.flush()

            evaluation_course = Course(
                id=course_id,  # who i am
                user_id=evaluation_user_id,  # i belong to whom?
                code="EVAL",
                name="Chunk Retrieval Evaluation",
                year=2026,
                sem=1,
            )
            session.add(evaluation_course)
            await session.flush()

            evaluation_folder_id = uuid4()
            evaluation_folder = Folder(
                id=evaluation_folder_id,  # answer who is this folder
                course_id=course_id,  # answer this folder is under which course
                parent_folder_id=None,
                name="Evaluation",
                is_root=True,
                sort_order=0,
            )
            session.add(evaluation_folder)
            await session.flush()

            evaluation_file = FileRow(
                id=evaluation_file_id,
                course_id=course_id,
                folder_id=evaluation_folder_id,
                filename=pdf_path.name,
                storage_key=f"evaluation/{evaluation_file_id}.pdf",
                sha256="evaluation-only",
                mime_type="application/pdf",
                size_bytes=pdf_path.stat().st_size,
                page_count=page_count,
                status=FileStatus.READY,
                error_message=None,
                uploaded_at=datetime.now(UTC),
                indexed_at=datetime.now(UTC),
            )
            session.add(evaluation_file)
            await session.flush()

            run_350 = IngestionRun(
                id=run_350_id,
                file_id=evaluation_file_id,
                status=IngestionRunStatus.READY,
                chunker_version="max-token-350",
                embedding_model=settings.MODEL_TYPE,
                embedding_dim=settings.EMBEDDINGS_DIM,
                is_active=True,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            run_500 = IngestionRun(
                id=run_500_id,
                file_id=evaluation_file_id,
                status=IngestionRunStatus.READY,
                chunker_version="max-token-500",
                embedding_model=settings.MODEL_TYPE,
                embedding_dim=settings.EMBEDDINGS_DIM,
                is_active=False,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            session.add_all([run_350, run_500])
            await session.flush()

            session.add_all(database_chunks_350)
            session.add_all(database_chunks_500)
            await session.flush()
            print(
                f"Inserted {len(database_chunks_350)}+{len(database_chunks_500)} evaluation_chunks"
            )

            config = SearchConfig(final_limit=5)
            ranks_350 = await evaluate_configuration(
                "350",
                questions,
                query_vectors,
                course_id,
                evaluation_file_id,
                session,
                config,
            )
            # Deactivate before activate, flushed separately: ix_ingestion_run_one_active
            # allows one active run per file, and a single flush orders the two
            # UPDATEs by the (random) primary key, so it failed about half the time.
            run_350.is_active = False
            await session.flush()
            run_500.is_active = True
            await session.flush()
            assert not run_350.is_active
            assert run_500.is_active

            print("Switched active ingestion run from 350 to 500")
            ranks_500 = await evaluate_configuration(
                "500",
                questions,
                query_vectors,
                course_id,
                evaluation_file_id,
                session,
                config,
            )

            print_comparison(questions, ranks_350, ranks_500, config.final_limit)
        finally:
            await session.rollback()
            print("Database evaluation rolled back")


if __name__ == "__main__":
    asyncio.run(main())
