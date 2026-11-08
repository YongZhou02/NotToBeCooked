import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = Path(r"D:\Downloads\NTBC_Topic2_50_Questions_Only.csv")
PDF_PATH = ROOT / "evaluation/datasets/cpt316/documents/CPT316_Topic2_Lexical_Semantic_Text.pdf"
LABELS_PATH = ROOT / "outputs/topic2_eval/ai_labels.json"
OUT = ROOT / "evaluation/datasets/cpt316/topic2"

QUOTE_FIXES = {
    "t2-001": [
        (5, "Input source characters -> group into lexemes -> produce a sequence of tokens.")
    ],
    "t2-008": [
        (39, "An alphabet ∑ is a set of characters"),
        (39, "A string over ∑ is a finite sequence of elements from ∑"),
    ],
    "t2-010": [
        (25, "This concurrent processing and reading ensure a steady stream of characters and minimizes wait times."),
    ],
    "t2-011": [
        (49, "(a|b)(a |b) : Denotes {aa, ab, ba, bb}, the language of all strings of length 2 over the alphabet ∑."),
    ],
    "t2-014": [(11, "A pair consisting of token name and an optional attribute value.")],
    "t2-017": [
        (8, "The specialized buffering techniques for reading input characters can speed up the compiler’s efficiency.")
    ],
    "t2-018": [
        (27, "rather than using one system call per character.")
    ],
    "t2-022": [
        (15, "<id, pointer to symbol table entry for E>"),
        (15, "<id, pointer ……….. For M>"),
        (15, "<id, pointer……… for C>"),
    ],
    "t2-026": [
        (9, "e.g. deletion of comments and compaction of consecutive whitespace characters into one."),
        (9, "produces tokens from the output of the scanner."),
    ],
    "t2-027": [
        (28, "lexemeBegin – marks the beginning of the current lexeme."),
        (28, "forward – scans ahead until a pattern match is found."),
    ],
    "t2-029": [
        (60, "Each state represents a condition that could occur during the process of scanning the input looking for a lexeme that matches one of several patterns"),
        (60, "Each edge is labeled by a symbol or set of symbols."),
        (63, "switch (state) {"),
    ],
    "t2-040": [
        (19, "Since fi is a valid lexeme for the token id, the lexical analyzer must return the token id to the parser")
    ],
    "t2-041": [
        (47, "Zero or more occurrences of r (kleen closure)"),
        (47, "One or more occurrences of r (Positive Closure)"),
    ],
    "t2-047": [
        (47, "Zero or more occurrences of r (kleen closure)"),
        (47, "One or more occurrences of r (Positive Closure)"),
    ],
    "t2-050": [
        (11, "An informal description of a form that lexemes of a token may take."),
        (11, "It is an actual stream of characters (in the source program) that matches the pattern"),
    ],
}


def main() -> None:
    questions = {row["Question ID"]: row["Question"] for row in csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline=""))}
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in labels}
    for question_id, evidence in QUOTE_FIXES.items():
        by_id[question_id]["evidence"] = [
            {"pdf_page": page, "quote": quote} for page, quote in evidence
        ]

    by_id["t2-045"].update(
        answerable=True,
        reference_answer=(
            "The three endings represent an integer, a decimal floating-point number, "
            "and a floating-point number with an exponent."
        ),
        required_facts=[
            "Digits alone end as an integer.",
            "A decimal fraction ends as a float.",
            "An exponent suffix ends as a float with exponent notation.",
        ],
        evidence=[
            {
                "pdf_page": 66,
                "quote": "Accepting integer Accepting float e.g. 12.31 Accepting float e.g. 12.31E4 e.g. 12",
            }
        ],
        reason="The page labels all three successful outcomes, although exact transition labels remain visually unverified.",
    )
    by_id["t2-048"].update(
        reference_answer=(
            "No. An eof sentinel at a buffer-half boundary can signal that the other "
            "buffer must be refilled; eof away from that boundary indicates true end-of-input."
        ),
        required_facts=[
            "A sentinel marks the end of a buffer half and can trigger refill.",
            "An eof away from the buffer end means the input is finished.",
        ],
        evidence=[
            {
                "pdf_page": 30,
                "quote": "Sentinel marks the end of a buffer half; when encountered, check whether to refill or terminate.",
            },
            {
                "pdf_page": 31,
                "quote": "Any eof that appears other than at the end of buffer means that the input is at an end.",
            },
        ],
    )

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, question_id in enumerate(questions):
        label = by_id[question_id]
        answerable = bool(label["answerable"])
        evidence_groups = [
            {
                "id": f"{question_id}-e{group_index}",
                "alternatives": [
                    {
                        "document_id": "topic2",
                        "pdf_page": evidence["pdf_page"],
                        "quote": evidence["quote"],
                    }
                ],
            }
            for group_index, evidence in enumerate(label["evidence"], 1)
        ]
        rows.append(
            {
                "id": question_id,
                "category": "unanswerable" if not answerable else "challenge",
                "split": "test",
                "generation_review": True,
                "origin": "ai_assisted",
                "verified": False,
                "answerable": answerable,
                "question": questions[question_id],
                "reference_answer": label["reference_answer"],
                "required_facts": label["required_facts"],
                "evidence_groups": evidence_groups,
                "label_review": {
                    "status": "candidate_source_checked",
                    "strict_retrieval_eligible": answerable,
                    "human_verified": False,
                    "reason": label["reason"],
                },
            }
        )
    (OUT / "questions.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    (OUT / "dataset.json").write_text(
        json.dumps(
            {
                "version": 1,
                "name": "CPT316 Topic 2 blind challenge set",
                "annotation_status": "candidate: AI-assisted answer/evidence labels; exact quotes checked; human review pending",
                "scope": "single supplied Topic 2 semantic-text PDF",
                "chart_extraction": False,
                "ocr": True,
                "chunk_max_tokens": 350,
                "top_k": 5,
                "candidate_limit": 50,
                "rrf_k": 60,
                "label_counts": {
                    "total": len(rows),
                    "answerable": sum(row["answerable"] for row in rows),
                    "unanswerable": sum(not row["answerable"] for row in rows),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "sources.json").write_text(
        json.dumps(
            {
                "version": 1,
                "documents": [
                    {
                        "id": "topic2",
                        "path": "../documents/CPT316_Topic2_Lexical_Semantic_Text.pdf",
                        "sha256": hashlib.sha256(PDF_PATH.read_bytes()).hexdigest(),
                        "pages": 67,
                        "coverage": "PDF pages 1-67",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_dir = OUT / "reviews"
    review_dir.mkdir(exist_ok=True)
    shutil.copy2(CSV_PATH, review_dir / CSV_PATH.name)
    print(
        f"wrote {len(rows)} rows: {sum(row['answerable'] for row in rows)} answerable, "
        f"{sum(not row['answerable'] for row in rows)} unanswerable"
    )


if __name__ == "__main__":
    main()
