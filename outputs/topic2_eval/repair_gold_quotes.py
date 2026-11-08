import json
from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "outputs/topic2_eval/workbook_gold_evidence.json"
PDF = ROOT / "evaluation/datasets/cpt316/documents/CPT316_Topic2_Lexical_Semantic_Text.pdf"


def compact(text: str) -> str:
    return " ".join(text.split())


def closest_exact_span(target: str, page: str) -> tuple[str, float]:
    target_words = compact(target).split()
    page_words = compact(page).split()
    best_span, best_score = "", -1.0
    target_len = max(1, len(target_words))
    for width in range(max(2, target_len - 6), target_len + 7):
        for start in range(0, max(1, len(page_words) - width + 1)):
            span = " ".join(page_words[start : start + width])
            score = SequenceMatcher(None, compact(target), span).ratio()
            if score > best_score:
                best_span, best_score = span, score
    return best_span, best_score


def main() -> None:
    rows = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    pdf = PdfReader(PDF)
    repairs = []
    for row in rows:
        for evidence in row["evidence"]:
            page = pdf.pages[evidence["pdf_page"] - 1].extract_text() or ""
            if compact(evidence["quote"]) in compact(page):
                continue
            old = evidence["quote"]
            evidence["quote"], score = closest_exact_span(old, page)
            repairs.append(
                {
                    "id": row["id"],
                    "page": evidence["pdf_page"],
                    "similarity": round(score, 4),
                    "old": old,
                    "new": evidence["quote"],
                }
            )
    EVIDENCE.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = ROOT / "outputs/topic2_eval/quote_repairs.json"
    report.write_text(
        json.dumps(repairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"repaired {len(repairs)} quotes; minimum similarity={min(r['similarity'] for r in repairs):.4f}")


if __name__ == "__main__":
    main()
