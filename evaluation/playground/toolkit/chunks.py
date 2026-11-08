"""Frozen chunk versions: `chunks/<version>/chunks.jsonl` plus `manifest.json`.

    chunks = load_chunks("v1")          # list of dicts, sorted by document and chunk_index

A version never changes after it is made. Chunk ids are part of the version,
so a run that names `v1` always scores the same text under the same ids.
`load_chunks` recomputes the sha256 recorded in the manifest and refuses a file
that no longer matches, so an accidental edit cannot silently change a result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PLAYGROUND

CHUNKS_ROOT = PLAYGROUND / "chunks"
CHUNK_FIELDS = (
    "id", "document_id", "chunk_index", "page_start", "page_end", "heading", "content", "token_count",
)


class ChunkVersionError(RuntimeError):
    """The chunk version is missing, tampered with, or would be overwritten."""


def version_dir(version: str, root: Path = CHUNKS_ROOT) -> Path:
    return root / version


def sha256_of(path: Path) -> str:
    """Hash with line endings normalised, so a git checkout with CRLF still verifies."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_manifest(version: str, root: Path = CHUNKS_ROOT) -> dict[str, Any]:
    path = version_dir(version, root) / "manifest.json"
    if not path.exists():
        raise ChunkVersionError(f"Chunk version {version!r} not found at {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks(version: str, root: Path = CHUNKS_ROOT) -> list[dict[str, Any]]:
    """The chunks of a version, after checking the file against the manifest."""
    manifest = read_manifest(version, root)
    path = version_dir(version, root) / manifest.get("chunks_file", "chunks.jsonl")
    if not path.exists():
        raise ChunkVersionError(f"{path} is missing")
    actual = sha256_of(path)
    if actual != manifest["chunks_sha256"]:
        raise ChunkVersionError(
            f"Chunk version {version!r} has been changed: chunks.jsonl hashes to {actual[:12]}, "
            f"manifest says {manifest['chunks_sha256'][:12]}. A version is never edited; "
            "make a new version instead."
        )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalise(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fixed field set and order, sorted by document then chunk_index, ids as text."""
    rows = [{**{key: chunk.get(key) for key in CHUNK_FIELDS}, "id": str(chunk["id"])} for chunk in chunks]
    rows.sort(key=lambda row: (row["document_id"], row["chunk_index"]))
    return rows


def write_version(
    version: str,
    chunks: list[dict[str, Any]],
    info: dict[str, Any],
    root: Path = CHUNKS_ROOT,
) -> dict[str, Any]:
    """Freeze `chunks` as `version`. `info` is merged into the manifest.

    Refuses when the folder already exists: a frozen version is never replaced.
    Files are written as bytes with LF endings so the sha256 is the same on every OS.
    """
    folder = version_dir(version, root)
    if folder.exists():
        raise ChunkVersionError(
            f"Chunk version {version!r} already exists at {folder}. Versions are never "
            "overwritten; pick a new name."
        )
    rows = normalise(chunks)
    folder.mkdir(parents=True)
    path = folder / "chunks.jsonl"
    path.write_bytes(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    )
    manifest = {
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        **info,
        "chunk_count": len(rows),
        "chunks_file": "chunks.jsonl",
        "chunks_sha256": sha256_of(path),
    }
    (folder / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return manifest
