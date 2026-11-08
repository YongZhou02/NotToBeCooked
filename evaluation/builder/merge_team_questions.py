"""Merge the original questions and every teammate's file into datasets/cpt316/all.

Each teammate saves one file in datasets/cpt316/team/, so git never has to merge
two people's edits. Every quote is checked against the PDF page it points at; a
bad row is skipped and listed in merge_report.json, never dropped silently.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION))

from scorers.retrieval import normalize

CORPUS = EVALUATION / "datasets/cpt316"
SPLITS = ("dev", "test", "stress")
# What a human edit may change on an original question.
EDITABLE = ("question", "reference_answer", "category", "split", "required_facts")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_pdf_pages(path: Path) -> list[str]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    pages = []
    for index in range(len(document)):
        page = document[index]
        textpage = page.get_textpage()
        pages.append(normalize(textpage.get_text_range()))
        textpage.close()
        page.close()
    document.close()
    return pages


class Pdfs:
    """Reads each PDF once, the first time one of its quotes is checked."""

    def __init__(self, folder: Path, sources: dict, reader: Callable | None = None):
        self.paths = {d["id"]: folder / d["path"] for d in sources["documents"]}
        self.reader, self.cache = reader or read_pdf_pages, {}

    def page(self, document_id: str, number: int) -> str | None:
        if document_id not in self.cache:
            self.cache[document_id] = self.reader(self.paths[document_id])
        pages = self.cache[document_id]
        return pages[number - 1] if 1 <= number <= len(pages) else None


def check_evidence(groups, pdfs: Pdfs) -> str | None:
    """Return the reason the evidence is bad, or None when every quote is on its page."""
    for group in groups:
        alternatives = group.get("alternatives") if isinstance(group, dict) else None
        if not alternatives or not isinstance(alternatives, list):
            return "an evidence group has no alternatives"
        for alt in alternatives:
            if not isinstance(alt, dict):
                return "an evidence alternative is not an object"
            document, number, quote = (
                alt.get(k) for k in ("document_id", "pdf_page", "quote")
            )
            if document not in pdfs.paths:
                return f"document_id {document!r} is not in sources.json"
            if type(number) is not int:
                return f"pdf_page {number!r} is not a whole number"
            if not isinstance(quote, str) or not normalize(quote):
                return "an evidence quote is empty"
            text = pdfs.page(document, number)
            if text is None:
                return f"{document} has no page {number}"
            if normalize(quote) not in text:
                return f"quote not found on {document} page {number}: {quote[:60]!r}"
    return None


def clean_row(
    row: dict, row_id: str, author: str, pdfs: Pdfs
) -> tuple[dict | None, str]:
    """Apply defaults and checks. Returns (row, "") or (None, reason)."""
    category = row.get("category") or "general"
    answerable = row.get("answerable", category != "unanswerable")
    for key in ("question", "reference_answer"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            return None, f"missing {key}"
    split = row.get("split") or "test"
    if split not in SPLITS:
        return None, f"split {split!r} must be one of {', '.join(SPLITS)}"
    groups = row.get("evidence_groups") or []
    if not isinstance(groups, list):
        return None, "evidence_groups must be a list"
    if answerable and not groups:
        return None, "an answerable question needs at least one evidence group"
    if reason := check_evidence(groups, pdfs):
        return None, reason
    groups = [
        {
            **group,
            "id": group["id"]
            if str(group.get("id", "")).startswith(row_id + "-")
            else f"{row_id}-e{n}",
        }
        for n, group in enumerate(groups, 1)
    ]
    facts = row.get("required_facts")
    if not isinstance(facts, list):
        facts = [row["reference_answer"]] if answerable else []
    cleaned = {
        "id": row_id,
        "category": category,
        "split": split,
        "generation_review": row.get("generation_review", True),
        "question": row["question"].strip(),
        "reference_answer": row["reference_answer"].strip(),
        "required_facts": facts,
        "evidence_groups": groups,
        "answerable": bool(answerable),
        "origin": row.get("origin") or "human",
        "verified": bool(row.get("verified", False)),
        "author": author,
        "label_review": {"status": "team", "strict_retrieval_eligible": True},
    }
    if row.get("is_hard_case"):
        cleaned["is_hard_case"] = True
    return cleaned, ""


def changed_fields(original: dict, edit: dict) -> list[str]:
    fields = [*EDITABLE, "evidence_groups", "answerable", "verified"]
    return [f for f in fields if original.get(f) != edit.get(f)]


def merge(
    originals: list[dict], team_files: list[tuple[str, object]], pdfs: Pdfs
) -> tuple[list[dict], dict]:
    """originals: rows in order. team_files: (file stem, parsed JSON), sorted by name."""
    rows = []
    for row in originals:
        rows.append(
            {
                **row,
                "answerable": row.get("answerable", True),
                "origin": row.get("origin", "synthetic"),
                "verified": row.get("verified", False),
                "author": row.get("author", "original"),
            }
        )
    index = {row["id"]: i for i, row in enumerate(rows)}
    skipped, files, edits, unchanged = [], [], {}, 0
    seen_ids = set(index)

    def skip(file, row_id, reason):
        skipped.append({"file": file, "id": row_id, "reason": reason})

    new_rows = []
    for stem, content in team_files:
        name = f"{stem}.json"
        questions = content.get("questions") if isinstance(content, dict) else content
        if not isinstance(questions, list):
            skip(
                name,
                None,
                content
                if isinstance(content, str)
                else "expected a list of rows or an object with a 'questions' list",
            )
            files.append(
                {"file": name, "rows": 0, "added": 0, "edited": 0, "skipped": 1}
            )
            continue
        counts = Counter()
        file_ids = set()
        for row in questions:
            row_id = row.get("id") if isinstance(row, dict) else None
            if not isinstance(row_id, str) or not row_id.strip():
                skip(name, None, "row has no id")
                counts["skipped"] += 1
                continue
            if row_id in file_ids:
                skip(name, row_id, "id appears twice in this file")
                counts["skipped"] += 1
                continue
            file_ids.add(row_id)
            is_edit = row_id in index
            new_id = (
                row_id
                if is_edit or row_id.startswith(f"{stem}-")
                else f"{stem}-{row_id}"
            )
            if not is_edit and new_id in seen_ids:
                skip(name, new_id, "id is already used by another question")
                counts["skipped"] += 1
                continue
            cleaned, reason = clean_row(row, new_id, stem, pdfs)
            if cleaned is None:
                skip(name, new_id, reason)
                counts["skipped"] += 1
            elif is_edit:
                original = rows[index[new_id]]
                if "verified" not in row:
                    cleaned["verified"] = original.get("verified", False)
                fields = changed_fields(original, cleaned)
                if fields:
                    edits.setdefault(new_id, []).append((stem, cleaned, fields))
                    counts["edited"] += 1
                else:
                    unchanged += 1
            else:
                seen_ids.add(new_id)
                new_rows.append(cleaned)
                counts["added"] += 1
        files.append(
            {
                "file": name,
                "rows": len(questions),
                **{k: counts[k] for k in ("added", "edited", "skipped")},
            }
        )

    edited, conflicts = [], []
    for row_id, versions in edits.items():
        authors = [stem for stem, _, _ in versions]
        if len(authors) > 1:
            conflicts.append({"id": row_id, "authors": authors, "kept": "original"})
            continue
        stem, cleaned, fields = versions[0]
        original = rows[index[row_id]]
        rows[index[row_id]] = {
            **original,
            **{f: cleaned[f] for f in fields},
            "evidence_groups": cleaned["evidence_groups"],
            "edited_by": stem,
            "label_review": cleaned["label_review"],
        }
        edited.append({"id": row_id, "by": stem, "fields": fields})
    rows += new_rows

    by_text: dict[str, list[str]] = {}
    for row in rows:
        by_text.setdefault(normalize(row["question"]), []).append(row["id"])
    warnings = [
        {"kind": "duplicate_question", "ids": ids}
        for ids in by_text.values()
        if len(ids) > 1
    ]
    report = {
        "total_rows": len(rows),
        "by_origin": dict(sorted(Counter(r["origin"] for r in rows).items())),
        "by_split": dict(sorted(Counter(r["split"] for r in rows).items())),
        "by_category": dict(sorted(Counter(r["category"] for r in rows).items())),
        "verified": sum(r["verified"] for r in rows),
        "unanswerable": sum(not r["answerable"] for r in rows),
        "team_files": files,
        "edited_originals": edited,
        "unchanged_edits": unchanged,
        "conflicts": conflicts,
        "skipped": skipped,
        "warnings": warnings,
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 if any row was skipped"
    )
    args = parser.parse_args()
    corpus, out = args.corpus, args.corpus / "all"
    originals = read_rows(corpus / "topic1/questions.jsonl")
    originals += read_rows(corpus / "topic1_stress/questions.jsonl")
    team_files = []
    for path in sorted((corpus / "team").glob("*.json")):
        try:
            team_files.append((path.stem, read_json(path)))
        except ValueError as error:
            team_files.append((path.stem, f"unreadable JSON: {error}"))
    ids = Counter(row["id"] for row in originals)
    if repeated := [i for i, n in ids.items() if n > 1]:
        raise SystemExit(f"Original questions repeat these ids: {repeated}")
    pdfs = Pdfs(out, read_json(out / "sources.json"))
    rows, report = merge(originals, team_files, pdfs)
    (out / "questions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out / "merge_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(rows)} questions to {out / 'questions.jsonl'} | "
        f"{len(report['skipped'])} skipped, {len(report['conflicts'])} conflicts, "
        f"{len(report['warnings'])} warnings"
    )
    for item in report["skipped"]:
        print(f"  skipped {item['file']} {item['id']}: {item['reason']}")
    if args.strict and report["skipped"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
