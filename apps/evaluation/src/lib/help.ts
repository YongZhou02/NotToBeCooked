/** The text behind each question-mark button. */

export const phaseHelp: Record<string, string[]> = {
  extraction: [
    "Extraction: what the parser read out of the PDF",
    "Score: how much of the expected evidence was kept, out of 100.",
    "Fuzzy match of 0.88 or more: similar text; a hint only, not scored.",
    "Bar: the score as a percentage.",
  ],
  chunking: [
    "Chunking: splitting the text into pieces for search",
    "Score: how often the evidence stayed whole inside one piece, out of 100.",
    "Over budget: pieces longer than the size limit.",
    "Bar: the share of evidence kept whole.",
  ],
  retrieval: [
    "Embedding and retrieval: finding the right pieces",
    "Score: hybrid evidence Recall@5 on the test split, out of 100.",
    "Recall@5: the needed evidence was found in the top five results.",
    "MRR: how early the first useful result appears.",
    "Bar: the hybrid recall percentage.",
  ],
  context: [
    "Context: choosing which pieces go to the answer step",
    "Score: all needed evidence was in the top five, out of 100.",
    "This borrows the retrieval result for now; there is no separate scorer yet.",
    "Bar: the share of questions with all evidence present.",
  ],
  citation: [
    "Citation: linking claims to their sources",
    "Score: how well the citations back up the answer, from 0-2 scaled to 0-100.",
    "2 of 2: the citation supports the claim. Reviews not done yet do not count.",
    "Bar: the reviewed support percentage.",
  ],
  generation: [
    "Generation: writing the final answer",
    "Score: faithfulness, correctness and completeness together, out of 100.",
    "Assistant review: only answers that were reviewed are counted.",
    "Bar: the reviewed answer-quality percentage.",
  ],
}

export const traceHelp: Record<string, string[]> = {
  "Gold evidence": [
    "Gold evidence: the facts the answer must rest on",
    "document_id: the source PDF.",
    "pdf_page: the page.",
    "quote: the expected text.",
  ],
  Extraction: [
    "Extraction: what the parser kept",
    "exact / fuzzy_pass: whether the quote was found.",
    "fuzzy_score: how close the nearest match was.",
    "matches: where it was found.",
  ],
  Chunking: [
    "Chunking: whether the evidence stays in one piece",
    "intact: yes or no.",
    "matches: which pieces hold it.",
  ],
  "Retrieval ranks": [
    "Retrieval ranks: where each search method found the evidence",
    "vector, keyword, hybrid_rrf: the three methods.",
    "found: whether the evidence turned up.",
    "ranks: its position in the results.",
  ],
  Context: [
    "Context: the pieces handed to the answer step",
    "filename: the source file.",
    "page_start, page_end: the pages.",
    "score: how well it matched; rank: its order; content: the text.",
  ],
  "Citation + generation": [
    "Citation and generation: the answer and its source links",
    "citations: the sources cited.",
    "answer: what the model wrote.",
    "review: the assistant's scores.",
  ],
}

export const concernsHelp = [
  "Concerns: what a student would run into",
  "Each card describes one problem in everyday terms.",
  "Measured: we have a number for it. Not measured: we know it matters but have no number yet.",
  "Click an example to read that question next to its PDF.",
]
