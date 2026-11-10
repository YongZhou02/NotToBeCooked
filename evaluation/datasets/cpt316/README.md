# CPT316 corpus — 2026-11-07

This folder now keeps all four CPT316 semantic-text PDFs together. Topic 1 is the
corpus used by the frozen benchmark; the other three are preserved byte-for-byte,
with SHA256 values recorded in [candidate_sources.json](candidate_sources.json),
but remain candidate sources. Existing gold labels and run results are unchanged.
The scored Topic 1 dataset lives under `topic1/`; PDFs live under `documents/`.

## Intake findings

| Source | Pages | Pages with native text | Pages containing uncertainty markers |
|---|---:|---:|---|
| Topic 1 | 38 | 38 | See the frozen Topic 1 benchmark audit |
| Topic 2 Lexical | 67 | 67 | 61, 62, 66 |
| Topic 3 Student | 77 | 77 | 26, 70, 75 |
| Topic 3 Updated | 65 | 65 | 1, 13, 27, 46, 54, 65 |

All 209 pages expose some native text. This does **not** mean that all relationships
were converted correctly. Twelve pages contain explicit unverified-content markers;
other unmarked mistakes may still exist. Absence of a marker is not validation.

Visual checks of Topic 2 p61, Topic 3 Student p26, and Topic 3 Updated p13 confirm
that these are warnings in the supplied PDF itself, not text lost by NTBC:

- Topic 2 p61: relational-operator state IDs/edges/accepting states need verification.
- Topic 2 p62: identifier-recognition transitions and retract conditions need verification.
- Topic 2 p66: numeric-token transition labels need verification.
- Topic 3 Student p26: exact parse-tree branch layout is not fully reconstructed.
- Topic 3 Updated p13: B-to-A curved-edge label and C self-loop symbols are uncertain.

Do not replace uncertain arrows, grammar symbols, or states with plausible guesses.
For questions about those details, inspect the original lecture slide first and
record a corrected, source-verified reference. Other source content can be reviewed
independently; whole pages do not automatically need to be excluded.

The two Topic 3 files have different page counts and remain distinct document IDs.
The word “Updated” does not establish which is authoritative. No equivalence,
supersession, or duplicate-content percentage has been established yet.

## Inspect the generated artifacts

Local diagnostic files are under
`output/pdf/cpt316-additional-preflight/` (ignored by Git):

- `summary.json`: document hashes, page counts, and flagged pages.
- `<document stem>/native_pages.json`: full page-by-page text and flags.
- `<document stem>/audit.json`: per-document audit metadata.
- `<document stem>/page-NNN.png`: rendered inspection samples.

Reproduce from the repository root:

```powershell
uv run --project apps/api python evaluation/builder/audit_semantic_pdfs.py evaluation/datasets/cpt316/documents/CPT316_Topic2_Lexical_Semantic_Text.pdf evaluation/datasets/cpt316/documents/CPT316_Topic3_Student_Semantic_Text.pdf evaluation/datasets/cpt316/documents/CPT316_Topic3_Updated_Semantic_Text.pdf --output output/pdf/cpt316-additional-preflight
```

This step checks the native text layer only. It has **not** run Docling extraction,
chunking, PostgreSQL/pgvector insertion, retrieval, question generation, or answer
scoring for these three PDFs. Those stages need their own run artifacts and reviewed
labels before any performance claim. Source PDFs have not been rewritten, and no
database records or prior benchmark manifests have been modified.
