import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROWS_PATH = ROOT / "outputs/topic2_eval/workbook_gold_rows.json"
EVIDENCE_PATH = ROOT / "outputs/topic2_eval/workbook_gold_evidence.json"
PDF_PATH = ROOT / "evaluation/datasets/cpt316/documents/CPT316_Topic2_Lexical_Semantic_Text.pdf"
WORKBOOK_PATH = Path(r"D:\Downloads\NTBC_Topic2_50_Paraphrased_Gold_Labels.xlsx")
OUT = ROOT / "evaluation/datasets/cpt316/topic2"

OVERRIDES = {
    "t2-001": [(5, "Input source characters -> group into lexemes -> produce a sequence of tokens.")],
    "t2-002": [(23, "Lexical Analyzer often needs to look one or more characters beyond the next lexeme before we can be sure we have the right lexeme."), (27, "rather than using one system call per character.")],
    "t2-005": [(11, "A pair consisting of token name and an optional attribute value."), (12, "score id"), (17, "<id, pointer to entry for pi>")],
    "t2-006": [(19, "Since fi is a valid lexeme for the token id, the lexical analyzer must return the token id to the parser"), (58, "An identifier is treated differently than a keyword")],
    "t2-008": [(39, "An alphabet ∑ is a set of characters"), (39, "A string over ∑ is a finite sequence of elements from ∑")],
    "t2-009": [(8, "This separation leads to simpler design of parser as unnecessary tokens (comments & whitespaces) are eliminated by the scanner already."), (9, "e.g. deletion of comments and compaction of consecutive whitespace characters into one.")],
    "t2-010": [(25, "This concurrent processing and reading ensure a steady stream of characters and minimizes wait times.")],
    "t2-012": [(61, "return(relop,LE)"), (61, "return(relop,NE)"), (61, "return(relop,GE)")],
    "t2-014": [(11, "It is an actual stream of characters (in the source program) that matches the pattern"), (12, "score id"), (17, "<id, pointer to entry for pi>")],
    "t2-016": [(36, "The empty string denoted by ‘ɛ’ has Zero length.")],
    "t2-017": [(8, "The specialized buffering techniques for reading input characters can speed up the compiler’s efficiency.")],
    "t2-018": [(27, "Size of each buffer is usually N, where N is the size of a disk block."), (27, "rather than using one system call per character.")],
    "t2-021": [(62, "ID = letter(letter | digit) *"), (63, "retract(1); insert(id); return;")],
    "t2-022": [(15, "<id, pointer to symbol table entry for E>"), (15, "<id, pointer ……….. For M>"), (15, "<id, pointer……… for C>")],
    "t2-024": [(36, "A string over an alphabet is a finite sequence of symbols drawn from that alphabet."), (38, "A countable set of strings over some fixed alphabet.")],
    "t2-026": [(9, "e.g. deletion of comments and compaction of consecutive whitespace characters into one."), (9, "produces tokens from the output of the scanner.")],
    "t2-028": [(50, "RE will be: ( a | c ) b* or ( a + c ) b*")],
    "t2-029": [(60, "Each state represents a condition that could occur during the process of scanning the input looking for a lexeme that matches one of several patterns"), (60, "Each edge is labeled by a symbol or set of symbols."), (63, "switch (state) {")],
    "t2-038": [(65, "Install the reserved words in the symbol table initially."), (65, "A field of the symbol-table entry indicates that these strings are never ordinary identifiers, and tells which token they represent.")],
    "t2-039": [(11, "A pair consisting of token name and an optional attribute value."), (17, "<number, floating point 3.1416>")],
    "t2-041": [(43, "Let L be the set of letters"), (43, "let D be the set of digits"), (47, "Zero or more occurrences of r (kleen closure)"), (47, "One or more occurrences of r (Positive Closure)")],
    "t2-042": [(30, "The buffer end test can be combined with the test for the current character if we extend each buffer to hold a sentinel character at the end.")],
    "t2-045": [(66, "Accepting integer Accepting float e.g. 12.31 Accepting float e.g. 12.31E4")],
    "t2-046": [(58, "An identifier is treated differently than a keyword"), (65, "Install the reserved words in the symbol table initially."), (65, "A field of the symbol-table entry indicates that these strings are never ordinary identifiers, and tells which token they represent.")],
    "t2-047": [(47, "Zero or more occurrences of r (kleen closure)"), (47, "One or more occurrences of r (Positive Closure)")],
    "t2-050": [(11, "An informal description of a form that lexemes of a token may take."), (11, "It is an actual stream of characters (in the source program) that matches the pattern")],
}


def main() -> None:
    rows = json.loads(ROWS_PATH.read_text(encoding="utf-8"))
    evidence_rows = {
        row["id"]: row["evidence"]
        for row in json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    }
    output = []
    for row in rows:
        question_id = row["Question ID"]
        answerable = row["Evidence Status"] == "Supported"
        evidence = (
            [{"pdf_page": page, "quote": quote} for page, quote in OVERRIDES[question_id]]
            if question_id in OVERRIDES
            else evidence_rows[question_id]
        )
        if not answerable:
            evidence = []
        output.append(
            {
                "id": question_id,
                "category": row["Category"].casefold(),
                "split": row["Split"].casefold(),
                "generation_review": True,
                "origin": "ai_assisted",
                "verified": False,
                "answerable": answerable,
                "question": row["Question (Paraphrased)"],
                "reference_answer": row["Gold Answer / Expected Refusal"],
                "required_facts": [row["Gold Answer / Expected Refusal"]],
                "evidence_groups": [
                    {
                        "id": f"{question_id}-e{index}",
                        "alternatives": [{"document_id": "topic2", **item}],
                    }
                    for index, item in enumerate(evidence, 1)
                ],
                "label_review": {
                    "status": row["Validation"].casefold().replace(" ", "_"),
                    "human_verified": False,
                    "strict_retrieval_eligible": answerable,
                    "evidence_basis": row["Evidence Basis / Quote Anchor"],
                    "source_pages": row["Source Pages (Original PDF)"],
                    "challenge_design": row["Challenge Design"],
                },
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "questions.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in output) + "\n",
        encoding="utf-8",
    )
    (OUT / "dataset.json").write_text(
        json.dumps(
            {
                "version": 1,
                "name": "CPT316 Topic 2 paraphrased challenge set",
                "annotation_status": "provided gold answers; source-grounded draft; exact evidence spans machine-checked; human span review pending",
                "scope": "single supplied Topic 2 semantic-text PDF",
                "chart_extraction": False,
                "ocr": True,
                "chunk_max_tokens": 350,
                "top_k": 5,
                "candidate_limit": 50,
                "rrf_k": 60,
                "label_counts": {"total": 50, "answerable": 42, "unanswerable": 8, "dev": 15, "test": 35},
                "gold_workbook": {
                    "path": "reviews/NTBC_Topic2_50_Paraphrased_Gold_Labels.xlsx",
                    "sha256": hashlib.sha256(WORKBOOK_PATH.read_bytes()).hexdigest(),
                },
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (OUT / "sources.json").write_text(
        json.dumps(
            {
                "version": 1,
                "documents": [{"id": "topic2", "path": "../documents/CPT316_Topic2_Lexical_Semantic_Text.pdf", "sha256": hashlib.sha256(PDF_PATH.read_bytes()).hexdigest(), "pages": 67, "coverage": "PDF pages 1-67"}],
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    reviews = OUT / "reviews"
    reviews.mkdir(exist_ok=True)
    shutil.copy2(WORKBOOK_PATH, reviews / WORKBOOK_PATH.name)
    print(f"wrote {len(output)} workbook-backed labels")


if __name__ == "__main__":
    main()
