import fs from "node:fs";
import path from "node:path";

const root = path.resolve("evaluation/datasets/cpt316/topic1");
const questionsPath = path.join(root, "questions.jsonl");
const datasetPath = path.join(root, "dataset.json");

const verdictGroups = {
  PASS: ["t1-001", "t1-002", "t1-003", "t1-005", "t1-006", "t1-007", "t1-008", "t1-012", "t1-014", "t1-015", "t1-016", "t1-018", "t1-019", "t1-020", "t1-021", "t1-024", "t1-029", "t1-040", "t1-046", "t1-047"],
  "PASS - PARAPHRASE": ["t1-004"],
  "PASS - VISUAL": ["t1-009", "t1-011", "t1-017", "t1-028", "t1-030", "t1-031", "t1-032", "t1-033", "t1-034", "t1-035", "t1-038", "t1-039", "t1-044"],
  "REVISE ANSWER": ["t1-010"],
  "REVISE QUESTION": ["t1-013"],
  "PASS - INFERENCE": ["t1-022", "t1-026", "t1-037"],
  "UNSUPPORTED BY ORIGINAL": ["t1-023", "t1-048"],
  "WRONG PAGE + REVISE": ["t1-025"],
  "LOW-VALUE VISUAL INFERENCE": ["t1-027"],
  "REVISE GOLD QUOTE": ["t1-036"],
  "PASS - SYNTHESIS": ["t1-041", "t1-042", "t1-043", "t1-045", "t1-049", "t1-050"],
};

const verdictById = Object.fromEntries(
  Object.entries(verdictGroups).flatMap(([verdict, ids]) => ids.map((id) => [id, verdict])),
);
const evidenceTypeByVerdict = {
  PASS: "text",
  "PASS - PARAPHRASE": "paraphrase",
  "PASS - VISUAL": "visual",
  "PASS - INFERENCE": "inference",
  "PASS - SYNTHESIS": "synthesis",
  "REVISE ANSWER": "text",
  "REVISE QUESTION": "visual",
  "UNSUPPORTED BY ORIGINAL": "revised_to_original_source",
  "WRONG PAGE + REVISE": "text",
  "LOW-VALUE VISUAL INFERENCE": "visual_inference",
  "REVISE GOLD QUOTE": "visual_relationship",
};

const revisions = {
  "t1-010": {
    reference_answer: "A compiler that compiles the source program in one pass.",
    required_facts: ["A one-pass compiler compiles the source program in one pass."],
  },
  "t1-013": {
    question: "Why is the integer literal 60 converted to real before multiplication by id3?",
    reference_answer: "Because 60 is an integer literal while id3 is real-valued, so semantic analysis converts 60 to real before multiplication.",
  },
  "t1-023": {
    category: "visual",
    question: "According to the diagram, does the interpreter process the source program line by line?",
    reference_answer: "Yes. The diagram says the interpreter handles the source program line by line.",
    required_facts: ["The phrase line by line qualifies how the interpreter handles source code."],
    evidence_groups: [{
      id: "t1-023-e1",
      alternatives: [{
        document_id: "topic1",
        pdf_page: 6,
        quote: "The phrase \"line by line\" appears OVER the rightward processing connection. It qualifies how the interpreter handles source code.",
      }],
    }],
  },
  "t1-025": {
    required_facts: ["Code generation translates optimized intermediate code into a machine-like instruction sequence."],
    evidence_groups: [{
      id: "t1-025-e1",
      alternatives: [{
        document_id: "topic1",
        pdf_page: 23,
        quote: "CODE GENERATION / INSTRUCTION DEPENDENCIES",
      }],
    }],
  },
  "t1-036": {
    question: "What transformation do the arrows on page 21 represent?",
    reference_answer: "They represent intermediate code passing through code optimization to become optimized intermediate code.",
    required_facts: ["Intermediate code passes through code optimization and becomes optimized intermediate code."],
    evidence_groups: [{
      id: "t1-036-e1",
      alternatives: [{
        document_id: "topic1",
        pdf_page: 21,
        quote: "CODE OPTIMIZATION / BEFORE -> AFTER",
      }],
    }],
  },
  "t1-048": {
    category: "exact",
    question: "According to the lecture comparison on page 26, does the interpreter generate intermediate code?",
    reference_answer: "No. According to the lecture comparison, the interpreter does not generate intermediate code.",
    required_facts: ["Interpreter: does not generate intermediate code."],
    evidence_groups: [{
      id: "t1-048-e1",
      alternatives: [{
        document_id: "topic1",
        pdf_page: 26,
        quote: "Interpreter: does not generate intermediate code.",
      }],
    }],
  },
};

const rows = fs.readFileSync(questionsPath, "utf8").trim().split(/\r?\n/).map(JSON.parse);
for (const row of rows) {
  if (!verdictById[row.id]) throw new Error(`Missing review verdict for ${row.id}`);
  Object.assign(row, revisions[row.id] ?? {});
  row.origin ??= "synthetic";
  row.verified = true;
  row.label_review = {
    status: row.id === "t1-027" ? "verified_excluded_from_strict" : "verified",
    original_verdict: verdictById[row.id],
    evidence_type: evidenceTypeByVerdict[verdictById[row.id]],
    strict_retrieval_eligible: row.id !== "t1-027",
    reviewed_against_original: true,
  };
}
fs.writeFileSync(questionsPath, `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`);

const dataset = JSON.parse(fs.readFileSync(datasetPath, "utf8"));
dataset.version = 3;
dataset.annotation_status = "finalized: 50/50 labels individually reviewed; 49 strict retrieval eligible";
dataset.label_review = {
  total_labels: 50,
  verified_labels: 50,
  strict_retrieval_labels: 49,
  excluded_from_strict: ["t1-027"],
  source_audit: "reviews/NTBC_Topic1_50_Labels_Individually_Verified.xlsx",
};
fs.writeFileSync(datasetPath, `${JSON.stringify(dataset, null, 2)}\n`);

const review = {
  schema_version: 1,
  reviewed_on: "2026-11-08",
  source_workbook: "reviews/NTBC_Topic1_50_Labels_Individually_Verified.xlsx",
  source_workbook_sha256: "db16f6370a76fe4d17dd615ddf16f84ab67c305e894d89742ff4d8bd42ca581d",
  total_labels: 50,
  verified_after_revision: 50,
  strict_retrieval_eligible: 49,
  excluded_from_strict: {
    "t1-027": "Low-value visual inference; retained for audit and UI review but excluded from strict retrieval scoring.",
  },
  applied_revisions: Object.keys(revisions),
  original_verdict_groups: verdictGroups,
};
fs.writeFileSync(path.join(root, "label_review.json"), `${JSON.stringify(review, null, 2)}\n`);
