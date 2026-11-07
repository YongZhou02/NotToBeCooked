"""Audit supplied semantic PDFs without changing them or inventing gold labels.

Outputs are diagnostic artifacts, not retrieval or answer-quality scores.
"""

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium


def inspect_text(text):
    flags = []
    if not text.strip():
        flags.append("no_native_text")
    if "\ufffd" in text:
        flags.append("unicode_replacement_character")
    if re.search(
        r"unverified|could not be reliably|cannot be reliably|not reconstructed",
        text,
        re.IGNORECASE,
    ):
        flags.append("unverified_content_marker")
    return flags


def audit(path, out):
    doc_out = out / path.stem
    doc_out.mkdir(parents=True, exist_ok=True)
    pages = []
    with pdfium.PdfDocument(str(path)) as document:
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            pages.append(
                {
                    "pdf_page": index + 1,
                    "content": text,
                    "characters": len(text),
                    "flags": inspect_text(text),
                }
            )
            textpage.close()
            page.close()
        flagged = [p["pdf_page"] for p in pages if p["flags"]]
        samples = sorted({1, len(document), *(flagged[:2])})
        for page_no in samples:
            page = document[page_no - 1]
            bitmap = page.render(scale=1.1)
            bitmap.to_pil().save(doc_out / f"page-{page_no:03}.png")
            bitmap.close()
            page.close()
    result = {
        "source": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "pages": len(pages),
        "native_text_pages": sum(bool(p["content"].strip()) for p in pages),
        "flagged_pages": [
            {"pdf_page": p["pdf_page"], "flags": p["flags"]}
            for p in pages
            if p["flags"]
        ],
        "scope": "Native text/preflight only; not Docling, chunk, DB, retrieval or semantic accuracy",
        "rendered_samples": samples,
    }
    (doc_out / "native_pages.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (doc_out / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = [audit(path, args.output) for path in args.inputs]
    summary = {"created_at": datetime.now(UTC).isoformat(), "documents": results}
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Additional CPT316 semantic PDF preflight",
        "",
        "Native text presence is not proof of faithful diagram transcription. Original slides are needed for semantic verification.",
        "",
        "No golden dataset, prior run, or PDF was modified. Topic 3 variants remain separate.",
        "",
    ]
    for item in results:
        lines += [
            f"## {Path(item['source']).name}",
            "",
            f"- Pages with native text: {item['native_text_pages']}/{item['pages']}",
            f"- SHA256: `{item['sha256']}`",
            f"- Flagged pages: {json.dumps(item['flagged_pages'])}",
            "",
        ]
    lines += [
        "## Next gate",
        "",
        "Review replacement characters against the rendered PDF; they may indicate symbol loss or text-map issues.",
        "Do not treat unverified visual-relationship placeholders as known facts or gold evidence.",
        "Compare Topic 3 content and original source provenance before deciding whether to include both in retrieval.",
        "Docling extraction/chunk/DB checks and independently reviewed question labels are separate subsequent work.",
    ]
    (args.output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
