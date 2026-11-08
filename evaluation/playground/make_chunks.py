"""Freeze a new chunk version.

From a finished run_eval.py run (the chunks it scored, ids unchanged):
    uv run --project apps/api python evaluation/playground/make_chunks.py v1 --from-run 20261108T004258996111Z

From a fresh run of the production ingestion code (slow: parses the PDFs):
    uv run --project apps/api python evaluation/playground/make_chunks.py v2 --ingest

Refuses to overwrite an existing version.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playground.toolkit import EVALUATION, ROOT  # noqa: E402
from playground.toolkit.chunks import CHUNKS_ROOT, ChunkVersionError, version_dir, write_version  # noqa: E402

DATASET = EVALUATION / "datasets/cpt316/all"
PRODUCTION_CHUNKER = "apps/api production ingestion (app.services.ingestion: Docling extract_text + create_chunk)"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_output(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def refuse_existing(version: str, root: Path) -> None:
    """Checked before any slow work, and again by write_version."""
    if version_dir(version, root).exists():
        raise ChunkVersionError(f"Chunk version {version!r} already exists; versions are never overwritten.")


def chunker_info(dataset: Path) -> dict[str, Any]:
    """Settings and PDF fingerprints from the dataset the chunks were made for."""
    settings = read(dataset / "dataset.json")
    sources = read(dataset / "sources.json")
    return {
        "chunker": {
            "description": PRODUCTION_CHUNKER,
            "settings": {
                key: settings[key] for key in ("chunk_max_tokens", "ocr", "chart_extraction")
            },
        },
        "retrieval_settings": {key: settings[key] for key in ("top_k", "candidate_limit", "rrf_k")},
        "documents": sources["documents"],
    }


def freeze_from_run(
    run: str | Path, version: str, root: Path = CHUNKS_ROOT, dataset: Path = DATASET
) -> dict[str, Any]:
    """Freeze the chunks a run_eval.py run scored. `run` is a run id or a folder."""
    folder = Path(run)
    if not folder.is_absolute() and not folder.exists():
        folder = EVALUATION / "runs" / str(run)
    refuse_existing(version, root)
    config = read(folder / "config.json")
    info = chunker_info(dataset)
    return write_version(
        version,
        read(folder / "chunks.json"),
        {
            "source_run_id": folder.name,
            "git_commit": config["git_commit"],
            "git_dirty": config["git_dirty"],
            **info,
            "source_run_embedding_model": config.get("embedding_model"),
            "source_run_pdfs_match_dataset": config.get("corpus", {}).get("documents") == info["documents"],
        },
        root,
    )


def freeze_from_ingestion(version: str, root: Path = CHUNKS_ROOT, dataset: Path = DATASET) -> dict[str, Any]:
    """Run the production ingestion code on the dataset PDFs and freeze the result."""
    from unittest.mock import patch
    from uuid import uuid4

    from app.core.config import settings
    from app.services.ingestion import create_chunk, extract_text, ingest_document

    refuse_existing(version, root)
    info = chunker_info(dataset)
    budget = info["chunker"]["settings"]["chunk_max_tokens"]
    chunks: list[dict[str, Any]] = []
    with patch.object(settings, "CHART_EXTRACTION_ENABLED", info["chunker"]["settings"]["chart_extraction"]):
        for source in info["documents"]:
            parsed = ingest_document(str((dataset / source["path"]).resolve()))
            items = extract_text(parsed)
            for chunk in create_chunk(items, uuid4(), budget):
                chunks.append({"id": uuid4(), "document_id": source["id"], **chunk.model_dump(exclude={"file_id"})})
            print(f"Chunked {source['id']}", flush=True)
    return write_version(
        version,
        chunks,
        {
            "source_run_id": None,
            "git_commit": git_output("rev-parse", "HEAD"),
            "git_dirty": bool(git_output("status", "--porcelain")),
            **info,
        },
        root,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="new version name, e.g. v2")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-run", help="run_eval.py run id (or folder) whose chunks.json to freeze")
    source.add_argument("--ingest", action="store_true", help="re-run production ingestion on the PDFs")
    args = parser.parse_args()
    try:
        manifest = freeze_from_run(args.from_run, args.version) if args.from_run else freeze_from_ingestion(args.version)
    except ChunkVersionError as error:
        raise SystemExit(str(error)) from error
    print(f"Froze {manifest['version']}: {manifest['chunk_count']} chunks, sha256 {manifest['chunks_sha256'][:12]}")


if __name__ == "__main__":
    main()
