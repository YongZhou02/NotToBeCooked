const REVIEW_KEY = "ntbc-evaluation-human-reviews-v1";
const VERIFICATION_KEY = "ntbc-evaluation-answer-verifications-v1";
const ANSWER_EDITS_KEY = "ntbc-evaluation-answer-edits-v1";
const CUSTOM_QUESTIONS_KEY = "ntbc-evaluation-custom-questions-v1";
const QUESTION_EDITS_KEY = "ntbc-evaluation-question-edits-v1";

function defaultFilters() {
  // Show all questions by default
  return { search: "", split: "all", origin: "all", source: "all", verification: "all", difficulty: "all" };
}

const state = {
  data: null,
  runId: null,
  questionId: null,
  visQuestionId: null,
  reviews: {},
  verifications: {},
  answerEdits: {},
  customQuestions: [],
  questionEdits: {}, // per question, only the fields changed from the original
  filters: defaultFilters(),
  editor: null, // { mode: "new" | "edit", id, draft, message } while the editor is open
  exportSelection: new Set(),
  exportHumanOnly: false,
  exportSelectionBeforeHumanOnly: null, // restored when "Human-written only" is turned off
  activeEvidenceIndex: 0,
  pdfSyncKey: null, // which question+evidence the PDF was last pointed at
  currentPdfState: {
    docId: "topic1",
    page: 1,
    quoteText: "",
  },
};

const $ = (id) => document.getElementById(id);
const percent = (value) => (value == null ? "—" : `${(value * 100).toFixed(1)}%`);
const scoreValue = (value) => (value == null ? "—" : `${value.toFixed(1)}`);
const methodLabel = (method) =>
  ({ vector: "Vector", keyword: "Keyword", hybrid_rrf: "Hybrid + RRF" })[method] || method;
const runShort = (id) => `${id.slice(0, 8)} · ${id.slice(9, 15)}`;

const documentFilenameMap = {
  topic1: "CPT316_Topic1_Semantic_Text_Only.pdf",
  "cpt316-topic1": "CPT316_Topic1_Semantic_Text_Only.pdf",
  "cpt316_topic1": "CPT316_Topic1_Semantic_Text_Only.pdf",
  "cpt316_topic1_semantic_text_only.pdf": "CPT316_Topic1_Semantic_Text_Only.pdf",
  "cpt316 topic 1": "CPT316_Topic1_Semantic_Text_Only.pdf",
  "cpt316_topic1_semantic_text_only": "CPT316_Topic1_Semantic_Text_Only.pdf",
  topic2: "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  "cpt316-topic2": "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  "cpt316_topic2": "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  "cpt316-topic2-lexical": "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  "cpt316_topic2_lexical_semantic_text.pdf": "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  "cpt316 topic 2": "CPT316_Topic2_Lexical_Semantic_Text.pdf",
  topic3: "CPT316_Topic3_Updated_Semantic_Text.pdf",
  "cpt316-topic3": "CPT316_Topic3_Updated_Semantic_Text.pdf",
  "cpt316_topic3": "CPT316_Topic3_Updated_Semantic_Text.pdf",
  "cpt316-topic3-updated": "CPT316_Topic3_Updated_Semantic_Text.pdf",
  "cpt316_topic3_updated_semantic_text.pdf": "CPT316_Topic3_Updated_Semantic_Text.pdf",
  "cpt316-topic3-student": "CPT316_Topic3_Student_Semantic_Text.pdf",
  "cpt316_topic3_student_semantic_text.pdf": "CPT316_Topic3_Student_Semantic_Text.pdf",
  "cpt316 topic 3": "CPT316_Topic3_Updated_Semantic_Text.pdf",
};

// The four source PDFs. `id` is the document_id written into new questions, and
// matches datasets/cpt316/candidate_sources.json for the candidate documents.
const SOURCE_DOCUMENTS = [
  { id: "topic1", file: "CPT316_Topic1_Semantic_Text_Only.pdf", label: "Topic 1" },
  { id: "cpt316-topic2-lexical", file: "CPT316_Topic2_Lexical_Semantic_Text.pdf", label: "Topic 2" },
  { id: "cpt316-topic3-updated", file: "CPT316_Topic3_Updated_Semantic_Text.pdf", label: "Topic 3 (Updated)" },
  { id: "cpt316-topic3-student", file: "CPT316_Topic3_Student_Semantic_Text.pdf", label: "Topic 3 (Student)" },
];

function getDocumentPdf(docId) {
  if (!docId) return "CPT316_Topic1_Semantic_Text_Only.pdf";
  const clean = String(docId).trim();
  const lower = clean.toLowerCase();
  if (documentFilenameMap[lower]) return documentFilenameMap[lower];
  if (documentFilenameMap[clean]) return documentFilenameMap[clean];
  if (lower.endsWith(".pdf")) {
    const matched = Object.values(documentFilenameMap).find(
      (fn) => fn.toLowerCase() === lower || fn.toLowerCase().endsWith(lower)
    );
    if (matched) return matched;
    return clean;
  }
  const doc = (state.data?.dataset?.documents || []).find((d) => d.id === docId);
  if (doc && doc.path) {
    const parts = doc.path.split(/[/\\]/);
    return parts[parts.length - 1];
  }
  return "CPT316_Topic1_Semantic_Text_Only.pdf";
}

const phaseHelp = {
  extraction: [
    "Extraction · parser output from the PDF",
    "Score: gold evidence preserved, out of 100.",
    "Fuzzy ≥ 0.88: similar text match; diagnostic only.",
    "Bar: the score percentage.",
  ],
  chunking: [
    "Chunking · splitting extracted text for search",
    "Score: evidence kept intact in a chunk, out of 100.",
    "Over budget: chunks above the token limit.",
    "Bar: the intact-evidence percentage.",
  ],
  retrieval: [
    "Embedding + retrieval · finding relevant chunks",
    "Score: hybrid evidence Recall@5 on test split, out of 100.",
    "Recall@5: required evidence found in the top five.",
    "MRR: how early the first relevant result appears.",
    "Bar: the hybrid recall percentage.",
  ],
  context: [
    "Context assembly · selecting chunks for the answer",
    "Score: complete evidence in the top five, out of 100.",
    "Retrieval proxy: not yet a dedicated context scorer.",
    "Bar: the complete-evidence percentage.",
  ],
  citation: [
    "Citation · linking claims to sources",
    "Score: citation support review, normalized from 0–2 to 0–100.",
    "2/2: citation supports the claim; pending reviews are not verified.",
    "Bar: the reviewed support percentage.",
  ],
  generation: [
    "Generation · producing the final answer",
    "Score: faithfulness + correctness + completeness, out of 100.",
    "Assistant review: only reviewed answers are included.",
    "Bar: the reviewed answer-quality percentage.",
  ],
};

const traceHelp = {
  "Gold evidence": [
    "Gold evidence · expected benchmark facts",
    "document_id: source PDF.",
    "pdf_page: source page.",
    "quote: expected text.",
  ],
  Extraction: [
    "Extraction · what the parser retained",
    "exact/fuzzy_pass: match result.",
    "fuzzy_score: similarity score.",
    "matches: extracted locations.",
  ],
  Chunking: [
    "Chunking · whether evidence stays together",
    "intact: pass/fail.",
    "matches: matching chunk locations.",
  ],
  "Retrieval ranks": [
    "Retrieval ranks · where each search method found evidence",
    "vector/keyword/hybrid_rrf: ranked methods.",
    "found: evidence appears or not.",
    "ranks: result positions.",
  ],
  Context: [
    "Context · chunks assembled for the answer",
    "filename: source file.",
    "page_start/page_end: source pages.",
    "score: retrieval score; rank: order; content: chunk text.",
  ],
  "Citation + generation": [
    "Citation + generation · answer and source links",
    "citations: cited sources.",
    "answer: generated response.",
    "review: assistant review scores.",
  ],
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text;
  return element;
}

function tooltip(lines) {
  const tip = node("span", "tooltip");
  const list = document.createElement("ul");
  lines.forEach((line) => list.append(node("li", "", line)));
  tip.append(list);
  return tip;
}

function currentRun() {
  return state.data.runs.find((run) => run.id === state.runId) || state.data.runs[0];
}

function currentQuestion() {
  return (
    state.data.questions.find((question) => question.id === state.questionId) ||
    state.data.questions[0]
  );
}

// dashboard_data.json keeps each question's gold evidence inside its per-run
// traces (traces[runId].groups), not at the top level. Gold evidence is the same
// in every run of a dataset, so the first trace is enough.
function evidenceGroupsFromTraces(q) {
  const trace = Object.values(q.traces || {})[0];
  return (trace?.groups || []).map((g) => ({ id: g.id, alternatives: g.alternatives || [] }));
}

const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

// The original question with the reviewer's changes laid over it. The originals are
// never rewritten, so an edit that is put back simply stops being an edit.
function resolveQuestion(original, defaultOrigin) {
  const q = { ...original, ...(state.questionEdits[original.id] || {}) };
  const answerEdited = hasOwn(state.answerEdits, q.id);
  return {
    ...q,
    origin: q.origin || defaultOrigin,
    is_hard_case: Boolean(state.reviews[q.id]?.hard_case ?? q.is_hard_case),
    reference_answer: answerEdited ? state.answerEdits[q.id] : q.reference_answer,
    is_edited: answerEdited || hasOwn(state.questionEdits, q.id),
    verified: hasOwn(state.verifications, q.id) ? Boolean(state.verifications[q.id]) : Boolean(q.verified),
    evidence_groups: q.evidence_groups || evidenceGroupsFromTraces(q),
    required_facts: q.required_facts || [],
    traces: q.traces || {},
  };
}

function getAllQuestions() {
  return [
    ...(state.data?.questions || []).map((q) => resolveQuestion(q, "synthetic")),
    ...state.customQuestions.map((q) => resolveQuestion(q, "human")),
  ];
}

function originalQuestion(id) {
  return state.data.questions.find((q) => q.id === id) || state.customQuestions.find((q) => q.id === id);
}

const EDITABLE_FIELDS = ["question", "category", "split", "required_facts", "evidence_groups", "source_document"];

function originalValue(original, field) {
  if (field === "evidence_groups") return original.evidence_groups || evidenceGroupsFromTraces(original);
  if (field === "required_facts") return original.required_facts || [];
  return original[field];
}

// Stores only what differs from the original, for edits and imports alike.
function storeQuestionChanges(id, values) {
  const original = originalQuestion(id);
  const patch = {};
  EDITABLE_FIELDS.forEach((field) => {
    if (values[field] === undefined) return;
    if (JSON.stringify(values[field]) !== JSON.stringify(originalValue(original, field))) {
      patch[field] = values[field];
    }
  });

  if (Object.keys(patch).length > 0) state.questionEdits[id] = patch;
  else delete state.questionEdits[id];

  if (values.reference_answer !== undefined) {
    if (values.reference_answer !== original.reference_answer) state.answerEdits[id] = values.reference_answer;
    else delete state.answerEdits[id];
  }

  saveQuestionEdits();
  saveAnswerEdits();
}

// A question's sources are the PDFs its evidence points at, plus the document it
// was written against (a human question may have no gold quote yet).
function questionSources(q) {
  const ids = (q.evidence_groups || []).flatMap((g) =>
    (g.alternatives || []).map((alt) => alt.document_id),
  );
  if (q.source_document) ids.push(q.source_document);
  return new Set(ids.map(getDocumentPdf));
}

function getFilteredQuestions() {
  const all = getAllQuestions();
  return all.filter((q) => {
    if (state.filters.split !== "all" && q.split !== state.filters.split) {
      return false;
    }
    if (state.filters.origin !== "all" && q.origin !== state.filters.origin) {
      return false;
    }
    if (state.filters.source !== "all" && !questionSources(q).has(state.filters.source)) {
      return false;
    }
    if (state.filters.difficulty === "hard" && !q.is_hard_case) {
      return false;
    }
    if (state.filters.verification === "verified" && !q.verified) {
      return false;
    }
    if (state.filters.verification === "unverified" && q.verified) {
      return false;
    }
    if (state.filters.search) {
      const query = state.filters.search.toLowerCase().trim();
      const matchId = (q.id || "").toLowerCase().includes(query);
      const matchQ = (q.question || "").toLowerCase().includes(query);
      const matchAns = (q.reference_answer || "").toLowerCase().includes(query);
      if (!matchId && !matchQ && !matchAns) return false;
    }
    return true;
  });
}

function activeVisQuestion() {
  const all = getAllQuestions();
  if (!all.length) return null;
  return all.find((q) => q.id === state.visQuestionId) || getFilteredQuestions()[0] || all[0];
}

function computeSplitMetrics() {
  const questions = getAllQuestions();
  const summary = {
    dev: {
      questions: 0,
      evidence_groups: 0,
      golden_quotes: 0,
      verified: 0,
      unverified: 0,
      synthetic: 0,
      human: 0,
      categories: {},
    },
    test: {
      questions: 0,
      evidence_groups: 0,
      golden_quotes: 0,
      verified: 0,
      unverified: 0,
      synthetic: 0,
      human: 0,
      categories: {},
    },
    total: {
      questions: questions.length,
      evidence_groups: 0,
      golden_quotes: 0,
      verified: 0,
      unverified: 0,
      synthetic: 0,
      human: 0,
      categories: {},
    },
  };

  questions.forEach((q) => {
    const splitKey = q.split === "dev" ? "dev" : "test";
    const groupCount = (q.evidence_groups || []).length;
    const quoteCount = (q.evidence_groups || []).reduce(
      (sum, group) => sum + (group.alternatives || []).length,
      0,
    );

    [summary[splitKey], summary.total].forEach((target) => {
      target.questions += target === summary.total ? 0 : 1;
      target.evidence_groups += groupCount;
      target.golden_quotes += quoteCount;
      if (q.verified) {
        target.verified += 1;
      } else {
        target.unverified += 1;
      }
      if (q.origin === "human") {
        target.human += 1;
      } else {
        target.synthetic += 1;
      }
      const cat = q.category || "general";
      target.categories[cat] = (target.categories[cat] || 0) + 1;
    });
  });

  return summary;
}

function saveReviews() {
  localStorage.setItem(REVIEW_KEY, JSON.stringify(state.reviews));
  renderBadgesAndProgress();
}

function saveVerifications() {
  localStorage.setItem(VERIFICATION_KEY, JSON.stringify(state.verifications));
  renderBadgesAndProgress();
}

function saveAnswerEdits() {
  localStorage.setItem(ANSWER_EDITS_KEY, JSON.stringify(state.answerEdits));
}

function saveQuestionEdits() {
  localStorage.setItem(QUESTION_EDITS_KEY, JSON.stringify(state.questionEdits));
}

function saveCustomQuestions() {
  localStorage.setItem(CUSTOM_QUESTIONS_KEY, JSON.stringify(state.customQuestions));
}

function setTab(name) {
  // The workbench locks the page to the viewport; other tabs scroll normally.
  document.body.classList.toggle("vis-mode", name === "visualization");
  if (name === "visualization") window.scrollTo(0, 0);
  document.querySelectorAll(".tab-button").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const active = panel.dataset.panel === name;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  if (name === "visualization" && pdfViewerState.currentDoc && pdfViewerState.currentPage) {
    setTimeout(() => {
      renderPdfPage(pdfViewerState.currentPage, pdfViewerState.currentQuote);
    }, 60);
  }
}

function renderHeader() {
  const run = currentRun();
  const metrics = computeSplitMetrics();
  $("datasetName").textContent = state.data.dataset.name;
  $("summaryMeta").replaceChildren(
    node(
      "span",
      "",
      `${metrics.total.questions} questions (${metrics.dev.questions} dev · ${metrics.test.questions} test) · ${metrics.total.golden_quotes} golden quotes · `,
    ),
    node("strong", "", `${run.same_source_run_count} runs on this source`),
  );
}

function renderPhases() {
  const fragment = document.createDocumentFragment();
  currentRun().phases.forEach((phase) => {
    const card = node("article", "phase-card");
    const cardTop = node("div", "phase-card-top");
    cardTop.append(node("span", "phase-number", phase.number));
    const help = node("button", "help-button", "?");
    help.type = "button";
    help.append(tooltip(phaseHelp[phase.id] || ["Score explanation."]));
    help.setAttribute("aria-label", `${phase.label}: what does this score mean?`);
    cardTop.append(help);
    card.append(cardTop, node("h3", "", phase.label));
    const score = node("p", "score", scoreValue(phase.value));
    if (phase.value != null) score.append(node("small", "", " / 100"));
    card.append(score, node("p", "metric", phase.metric));
    card.append(
      node(
        "p",
        `score-source ${phase.status}`,
        phase.status === "measured" ? "from run artifacts" : "not available for this run",
      ),
    );
    const bar = node("div", "bar");
    const fill = node("span");
    fill.style.width = `${Math.max(0, Math.min(100, phase.value || 0))}%`;
    bar.append(fill);
    card.append(bar, node("p", "secondary", phase.secondary));
    fragment.append(card);
  });
  $("phaseGrid").replaceChildren(fragment);
}

function renderDashboardGrid() {
  const run = currentRun();
  const metrics = computeSplitMetrics();

  const details = $("dashRunDetails");
  details.replaceChildren(
    node("p", "run-info-line", `Run ID: ${run.id}`),
    node("p", "run-info-line", `Execution Mode: ${run.mode}`),
    node("p", "run-info-line", `Created at: ${run.created_at || "Recorded artifact"}`),
    node("p", "run-info-line", `Questions evaluated in retrieval: ${run.questions_evaluated}`),
    node("p", "run-info-line", `Generated answers: ${run.generation_answers}`),
  );

  const splitBox = $("dashSplitOverview");
  const fragment = document.createDocumentFragment();

  const devCard = node("div", "split-summary-box dev-box");
  devCard.append(
    node("h4", "split-box-title", "Dev Split"),
    node("p", "split-stat-num", `${metrics.dev.questions} questions`),
    node("p", "split-stat-sub", `${metrics.dev.golden_quotes} golden quotes · ${metrics.dev.evidence_groups} evidence groups`),
    node("p", "split-purpose", "Purpose: Prompt iteration, tuning & local calibration"),
  );

  const testCard = node("div", "split-summary-box test-box");
  testCard.append(
    node("h4", "split-box-title", "Test Split"),
    node("p", "split-stat-num", `${metrics.test.questions} questions`),
    node("p", "split-stat-sub", `${metrics.test.golden_quotes} golden quotes · ${metrics.test.evidence_groups} evidence groups`),
    node("p", "split-purpose", "Purpose: Formal evaluation benchmark (Recall@5 & MRR)"),
  );

  fragment.append(devCard, testCard);
  splitBox.replaceChildren(fragment);
}

function renderRetrieval() {
  const body = $("retrievalBody");
  const methods = currentRun().retrieval_methods;
  if (!methods || !Object.keys(methods).length) {
    body.replaceChildren($("emptyRowTemplate").content.cloneNode(true));
    return;
  }
  const fragment = document.createDocumentFragment();
  ["vector", "keyword", "hybrid_rrf"].forEach((name) => {
    const item = methods[name];
    if (!item) return;
    const row = node("tr", name === "hybrid_rrf" ? "selected-row" : "");
    row.append(
      node("td", "method-name", methodLabel(name)),
      node("td", "", percent(item["evidence_recall@5"])),
      node("td", "", item["mrr@5"].toFixed(3)),
      node("td", "", percent(item["hit@1"])),
      node("td", "", percent(item["complete_evidence@5"])),
      node("td", "", `${item.median_retrieval_ms.toFixed(1)} ms`),
    );
    fragment.append(row);
  });
  body.replaceChildren(fragment);
}

function renderRunSplitStats() {
  const metrics = computeSplitMetrics();
  const container = $("runDatasetStats");
  if (!container) return;

  const fragment = document.createDocumentFragment();
  const grid = node("div", "split-card-grid");

  const devCard = node("div", "split-card dev-theme");
  devCard.append(
    node("div", "split-card-head", "Dev Split"),
    node("div", "split-metric-main", `${metrics.dev.questions} questions`),
    node("div", "split-metric-detail", `${metrics.dev.golden_quotes} golden quotes · ${metrics.dev.evidence_groups} evidence groups`),
    node(
      "div",
      "split-categories",
      Object.entries(metrics.dev.categories)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" | "),
    ),
    node("p", "split-desc", "Calibrated for prompt engineering and development checks."),
  );

  const testCard = node("div", "split-card test-theme");
  testCard.append(
    node("div", "split-card-head", "Test Split (Evaluated Benchmark)"),
    node("div", "split-metric-main", `${metrics.test.questions} questions`),
    node("div", "split-metric-detail", `${metrics.test.golden_quotes} golden quotes · ${metrics.test.evidence_groups} evidence groups`),
    node(
      "div",
      "split-categories",
      Object.entries(metrics.test.categories)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" | "),
    ),
    node("p", "split-desc", "Official benchmark split scored for Recall@5, MRR@5, Hit@1, and Complete@5."),
  );

  const totalCard = node("div", "split-card total-theme");
  totalCard.append(
    node("div", "split-card-head", "Corpus Overview"),
    node("div", "split-metric-main", `${metrics.total.questions} total items`),
    node("div", "split-metric-detail", `${metrics.total.golden_quotes} golden quotes across 38 pages of Topic 1 PDF`),
    node("div", "split-categories", `Synthetic: ${metrics.total.synthetic} · Human: ${metrics.total.human}`),
    node("p", "split-desc", "Single semantic-text PDF source: CPT316 Topic 1."),
  );

  grid.append(devCard, testCard, totalCard);
  fragment.append(grid);
  container.replaceChildren(fragment);
}

function renderHistory() {
  $("runCount").textContent = `${state.data.runs.length} total`;
  const fragment = document.createDocumentFragment();
  state.data.runs.forEach((run) => {
    const extraction = run.phases.find((phase) => phase.id === "extraction") || {};
    const retrieval = run.phases.find((phase) => phase.id === "retrieval") || {};
    const row = node("tr", run.id === state.runId ? "selected-row" : "");
    row.append(
      node("td", "method-name", runShort(run.id)),
      node("td", "", run.mode),
      node("td", "", `${run.same_source_run_count} runs`),
      node("td", "", extraction.value == null ? "—" : `${extraction.value.toFixed(1)}`),
      node("td", "", retrieval.value == null ? "—" : `${retrieval.value.toFixed(1)}`),
      node("td", "", String(run.generation_answers)),
    );
    row.addEventListener("click", () => {
      state.runId = run.id;
      $("runSelect").value = run.id;
      render();
    });
    fragment.append(row);
  });
  $("historyBody").replaceChildren(fragment);
}

function statusStep(number, label, pass, detail) {
  const card = node("div", `trace-step ${pass == null ? "na" : pass ? "pass" : "fail"}`);
  card.append(node("strong", "", `${number}. ${label}`), node("span", "", detail));
  return card;
}

function traceSummary(trace) {
  const groups = trace?.groups || [];
  const exact = groups.filter((group) => group.extraction?.exact).length;
  const intact = groups.filter((group) => group.chunking?.intact).length;
  const retrieved = groups.filter((group) => group.retrieval?.hybrid_rrf?.found).length;
  const total = groups.length;
  return [
    statusStep(1, "Extraction", total ? exact === total : null, total ? `${exact}/${total} exact` : "not run"),
    statusStep(2, "Chunking", total ? intact === total : null, total ? `${intact}/${total} intact` : "not run"),
    statusStep(
      3,
      "Retrieval",
      trace?.context?.metrics != null ? retrieved === total : null,
      trace?.context?.metrics != null ? `${retrieved}/${total} hybrid` : "not run",
    ),
    statusStep(
      4,
      "Context",
      trace?.context?.metrics != null ? trace.context.metrics["complete_evidence@5"] === 1 : null,
      trace?.context?.metrics != null ? `${trace.context.chunks.length} chunks` : "not run",
    ),
    statusStep(
      5,
      "Citation",
      trace?.generation != null ? trace.citation.length > 0 : null,
      trace?.generation != null ? `${trace.citation.length} citations` : "not run",
    ),
    statusStep(
      6,
      "Generation",
      trace?.generation == null ? null : trace.generation.grounded,
      trace?.generation != null ? (trace.generation.grounded ? "grounded" : "not grounded") : "not run",
    ),
  ];
}

function evidenceBlock(title, content) {
  const block = node("div", "evidence-block");
  const heading = node("div", "evidence-heading");
  heading.append(node("h3", "", title));
  const help = node("button", "help-button", "?");
  help.type = "button";
  help.append(tooltip(traceHelp[title] || ["Trace data for this stage."]));
  help.setAttribute("aria-label", `${title}: what does this section mean?`);
  heading.append(help);
  block.append(heading);
  const description = traceHelp[title]?.[0];
  if (description) block.append(node("p", "evidence-description", description));
  const pre = node("pre");
  pre.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
  block.append(pre);
  return block;
}

function renderTrace() {
  const question = currentQuestion();
  const trace = question.traces ? question.traces[state.runId] : null;
  $("questionSummary").replaceChildren(
    node("h3", "", `${question.id} · ${question.question}`),
    node("p", "", question.reference_answer),
  );
  const content = $("traceContent");
  const flow = node("div", "trace-flow");
  flow.append(...traceSummary(trace));
  const fragment = document.createDocumentFragment();
  fragment.append(flow);
  (trace?.groups || []).forEach((group) => {
    const details = document.createElement("details");
    const extractionStatus = group.extraction?.exact
      ? "exact"
      : group.extraction?.fuzzy_pass
        ? `fuzzy ${group.extraction.fuzzy_score.toFixed(2)}`
        : "missing";
    details.append(node("summary", "", `${group.id} · ${extractionStatus}`));
    const body = node("div", "evidence-body");
    body.append(
      evidenceBlock("Gold evidence", group.alternatives),
      evidenceBlock("Extraction", group.extraction),
      evidenceBlock("Chunking", group.chunking),
      evidenceBlock("Retrieval ranks", group.retrieval),
      evidenceBlock("Context", trace.context),
      evidenceBlock("Citation + generation", {
        citations: trace.citation,
        answer: trace.generation,
        review: trace.assistant_review,
      }),
    );
    details.append(body);
    fragment.append(details);
  });
  content.replaceChildren(fragment);
}

// ==========================================
// TAB 3: VISUALIZATION & HUMAN ANNOTATION
// Custom High-Fidelity Canvas PDF Viewer
// ==========================================

function quoteItemIndices(items, quote) {
  if (!items || !items.length || !quote) return [];
  const chars = [...quote.replace(/\s+/g, "")];
  if (chars.length === 0) return [];

  let joined = "";
  const spans = [];
  for (const item of items) {
    const start = joined.length;
    joined += item;
    spans.push({ start, end: joined.length });
    joined += " ";
  }

  const escaped = chars.map((c) => c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const match = new RegExp(escaped.join("\\s*"), "i").exec(joined);
  if (!match) return [];
  const from = match.index;
  const to = from + match[0].length;

  const hits = [];
  spans.forEach((span, index) => {
    if (span.end > from && span.start < to && span.end > span.start) {
      hits.push(index);
    }
  });
  return hits;
}

const pdfViewerState = {
  lib: null,
  docCache: new Map(),
  currentDoc: null,
  currentFilename: "",
  currentPage: 1,
  totalPages: 1,
  currentQuote: "",
  zoomLevel: 1.0,
  renderTask: null,
  textLayerTask: null,
  lastRenderWidth: 0,
  renderToken: 0, // newest renderPdfPage call wins
  viewRequest: 0, // newest updatePdfViewer call wins
  renderedKey: "", // file+page currently on screen
  evidence: null, // { docId, page, quote } the active gold evidence
};

async function getPdfLib() {
  if (pdfViewerState.lib) return pdfViewerState.lib;
  try {
    const lib = await import("./vendor/pdfjs/pdf.min.mjs");
    try {
      lib.GlobalWorkerOptions.workerSrc = "./vendor/pdfjs/pdf.worker.min.mjs";
    } catch (_) {}
    pdfViewerState.lib = lib;
    return lib;
  } catch (err) {
    console.error("Failed to load PDF.js module:", err);
    throw err;
  }
}

function showPdfLoading(message = "Loading PDF...") {
  const overlay = $("pdfLoadingOverlay");
  const text = $("pdfLoadingText");
  const errOverlay = $("pdfErrorOverlay");
  if (errOverlay) errOverlay.hidden = true;
  if (text) text.textContent = message;
  if (overlay) overlay.hidden = false;
}

function hidePdfLoading() {
  const overlay = $("pdfLoadingOverlay");
  if (overlay) overlay.hidden = true;
}

function showPdfError(message) {
  hidePdfLoading();
  const overlay = $("pdfErrorOverlay");
  const text = $("pdfErrorText");
  if (text) text.textContent = message;
  if (overlay) overlay.hidden = false;
}

async function loadPdfDocument(filename) {
  if (pdfViewerState.docCache.has(filename)) {
    return pdfViewerState.docCache.get(filename);
  }

  showPdfLoading(`Opening ${filename}...`);
  const lib = await getPdfLib();
  const loadingTask = lib.getDocument({
    url: `../datasets/cpt316/documents/${filename}`,
  });

  const doc = await loadingTask.promise;
  pdfViewerState.docCache.set(filename, doc);
  return doc;
}

// Everything is drawn off-screen first and swapped in one synchronous step, so the
// previous page stays visible until the next is ready: no blank canvas, no spinner
// on a fast render, and the page arrives already scrolled to its quote.
async function renderPdfPage(pageNumber, quoteText) {
  const doc = pdfViewerState.currentDoc;
  if (!doc) return;
  const targetPage = Math.max(1, Math.min(doc.numPages, parseInt(pageNumber, 10) || 1));
  pdfViewerState.currentPage = targetPage;
  pdfViewerState.currentQuote = quoteText || "";

  const token = ++pdfViewerState.renderToken;
  const isStale = () => token !== pdfViewerState.renderToken;

  // Cancel any running render task
  if (pdfViewerState.renderTask) {
    try { pdfViewerState.renderTask.cancel(); } catch (_) {}
    pdfViewerState.renderTask = null;
  }
  if (pdfViewerState.textLayerTask) {
    try { pdfViewerState.textLayerTask.cancel(); } catch (_) {}
    pdfViewerState.textLayerTask = null;
  }

  const viewportBox = $("pdfViewport");
  const pageWrapper = $("pdfPageWrapper");
  // A hidden tab has no width to fit; setTab renders again when it is shown.
  if (!viewportBox || !pageWrapper || !viewportBox.clientWidth) return;

  const slowRender = setTimeout(() => {
    if (!isStale()) showPdfLoading(`Rendering page ${targetPage}...`);
  }, 250);
  let stagedText = null;

  try {
    const page = await doc.getPage(targetPage);
    if (isStale()) return;

    // Viewport width calculation
    const containerWidth = Math.max(260, viewportBox.clientWidth - 20);
    pdfViewerState.lastRenderWidth = viewportBox.clientWidth;
    const baseViewport = page.getViewport({ scale: 1.0 });
    const fitScale = containerWidth / baseViewport.width;
    const effectiveScale = fitScale * pdfViewerState.zoomLevel;
    const viewport = page.getViewport({ scale: effectiveScale });
    const cssWidth = `${Math.floor(viewport.width)}px`;
    const cssHeight = `${Math.floor(viewport.height)}px`;

    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const stagedCanvas = document.createElement("canvas");
    stagedCanvas.className = "pdf-canvas";
    stagedCanvas.width = Math.floor(viewport.width * dpr);
    stagedCanvas.height = Math.floor(viewport.height * dpr);
    stagedCanvas.style.width = cssWidth;
    stagedCanvas.style.height = cssHeight;

    const ctx = stagedCanvas.getContext("2d", { alpha: false });
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";

    const renderTask = page.render({
      canvasContext: ctx,
      viewport,
      transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0],
    });
    pdfViewerState.renderTask = renderTask;
    await renderTask.promise;
    pdfViewerState.renderTask = null;
    if (isStale()) return;

    // Text layer for selection and gold evidence highlight
    let textLayer = null;
    if (pdfViewerState.lib?.TextLayer) {
      stagedText = document.createElement("div");
      stagedText.className = "textLayer";
      stagedText.style.visibility = "hidden";
      pageWrapper.append(stagedText);

      const textContent = await page.getTextContent();
      if (isStale()) return;
      textLayer = new pdfViewerState.lib.TextLayer({
        textContentSource: textContent,
        container: stagedText,
        viewport,
      });
      pdfViewerState.textLayerTask = textLayer;
      await textLayer.render();
      pdfViewerState.textLayerTask = null;
      if (isStale()) return;
    }

    // Commit: nothing below awaits, so the browser paints it as one frame.
    pageWrapper.style.width = cssWidth;
    pageWrapper.style.height = cssHeight;
    pageWrapper.style.setProperty("--scale-factor", String(viewport.scale));

    $("pdfCanvas").replaceWith(stagedCanvas);
    stagedCanvas.id = "pdfCanvas";

    if (stagedText) {
      $("pdfTextLayer").remove();
      stagedText.id = "pdfTextLayer";
      stagedText.style.visibility = "";
      stagedText = null;
    }

    const renderedKey = `${pdfViewerState.currentFilename}#${targetPage}`;
    const pageChanged = renderedKey !== pdfViewerState.renderedKey;
    pdfViewerState.renderedKey = renderedKey;

    const highlighted = applyQuoteHighlight(textLayer, quoteText);
    if (highlighted.length > 0) {
      centerInPdfViewport(highlighted);
    } else if (pageChanged) {
      viewportBox.scrollTop = 0;
    }
    updateQuoteStatus(highlighted.length > 0);

    hidePdfLoading();
  } catch (err) {
    if (isStale() || err?.name === "RenderingCancelledException" || err?.name === "AbortException") {
      return;
    }
    console.error("PDF render failed:", err);
    showPdfError(`Could not render page ${targetPage}: ${err.message}`);
  } finally {
    clearTimeout(slowRender);
    if (stagedText) stagedText.remove();
  }
}

function applyQuoteHighlight(textLayer, quoteText) {
  if (!textLayer || !quoteText || !quoteText.trim()) return [];
  const items = textLayer.textContentItemsStr;
  const divs = textLayer.textDivs;
  if (!items || !divs || !items.length) return [];

  const hits = quoteItemIndices(items, quoteText).map((idx) => divs[idx]).filter(Boolean);
  hits.forEach((div) => div.classList.add("ntbc-quote"));
  return hits;
}

// Scrolls the PDF pane only. Element.scrollIntoView would also scroll every
// ancestor, which is what used to drag the whole page down on each question.
function centerInPdfViewport(elements, behavior = "auto") {
  const box = $("pdfViewport");
  if (!box || !elements.length) return;
  const frame = box.getBoundingClientRect();
  const rects = elements.map((el) => el.getBoundingClientRect());
  const top = Math.min(...rects.map((r) => r.top));
  const bottom = Math.max(...rects.map((r) => r.bottom));
  const left = Math.min(...rects.map((r) => r.left));
  box.scrollTo({
    top: box.scrollTop + top - frame.top - (box.clientHeight - (bottom - top)) / 2,
    left: box.scrollLeft + left - frame.left - 12,
    behavior,
  });
}

// Says so when the gold quote could not be found on its own page, rather than
// leaving the reader to wonder why nothing is highlighted.
function updateQuoteStatus(found) {
  const status = $("pdfQuoteStatus");
  if (!status) return;
  const ev = pdfViewerState.evidence;
  const onEvidencePage =
    ev &&
    ev.quote &&
    getDocumentPdf(ev.docId) === pdfViewerState.currentFilename &&
    ev.page === pdfViewerState.currentPage;
  status.hidden = found || !onEvidencePage;
}

function locateCurrentQuote() {
  const ev = pdfViewerState.evidence;
  if (!ev || !ev.quote) return;

  const onEvidencePage =
    getDocumentPdf(ev.docId) === pdfViewerState.currentFilename &&
    ev.page === pdfViewerState.currentPage;
  if (!onEvidencePage) {
    updatePdfViewer(ev.docId, ev.page, ev.quote);
    return;
  }

  const highlighted = [...($("pdfTextLayer")?.querySelectorAll(".ntbc-quote") || [])];
  if (highlighted.length > 0) {
    centerInPdfViewport(highlighted, "smooth");
  }
}

// Points the PDF at a piece of gold evidence (or at a plain page when there is none).
function showEvidence(ev, fallbackDocId = "topic1") {
  pdfViewerState.evidence = ev ? { docId: ev.documentId, page: ev.page, quote: ev.quote } : null;
  if ($("pdfHighlightBtn")) $("pdfHighlightBtn").disabled = !ev;
  if (ev) {
    updatePdfViewer(ev.documentId, ev.page, ev.quote);
  } else {
    updatePdfViewer(fallbackDocId, 1, "");
  }
}

async function updatePdfViewer(docId, pageNumber, quoteText) {
  const filename = getDocumentPdf(docId);
  const requestedPage = Math.max(1, parseInt(pageNumber, 10) || 1);
  const request = ++pdfViewerState.viewRequest;

  if ($("pdfDocSelect")) $("pdfDocSelect").value = filename;

  try {
    const doc = await loadPdfDocument(filename);
    if (request !== pdfViewerState.viewRequest) return;

    pdfViewerState.currentDoc = doc;
    pdfViewerState.currentFilename = filename;
    pdfViewerState.totalPages = doc.numPages;

    const page = Math.min(requestedPage, doc.numPages);
    state.currentPdfState = {
      docId: docId || "topic1",
      page,
      quoteText: quoteText || "",
    };

    if ($("pdfPageInput")) {
      $("pdfPageInput").value = page;
      $("pdfPageInput").max = doc.numPages;
    }
    if ($("pdfTotalPages")) $("pdfTotalPages").textContent = `/ ${doc.numPages}`;
    if ($("pdfOpenTab")) {
      $("pdfOpenTab").href = `../datasets/cpt316/documents/${filename}#page=${page}&view=FitH`;
    }

    await renderPdfPage(page, quoteText);
  } catch (err) {
    if (request !== pdfViewerState.viewRequest) return;
    console.error("Failed to load PDF:", err);
    showPdfError(`Could not load ${filename}: ${err.message}`);
    const frame = $("pdfFrame");
    if (frame) {
      frame.src = `../datasets/cpt316/documents/${filename}#page=${requestedPage}&view=FitH`;
      frame.style.display = "block";
    }
  }
}

function changePdfPage(delta) {
  const current = state.currentPdfState || { docId: "topic1", page: 1, quoteText: "" };
  const total = pdfViewerState.totalPages || 38;
  const newPage = Math.max(1, Math.min(total, current.page + delta));
  updatePdfViewer(current.docId, newPage, current.quoteText);
}

function setPdfZoom(factor) {
  if (factor === 0) {
    pdfViewerState.zoomLevel = 1.0;
    if ($("pdfZoomLevel")) $("pdfZoomLevel").textContent = "Fit";
  } else {
    pdfViewerState.zoomLevel = Math.max(0.6, Math.min(2.5, pdfViewerState.zoomLevel + factor));
    if ($("pdfZoomLevel")) $("pdfZoomLevel").textContent = `${Math.round(pdfViewerState.zoomLevel * 100)}%`;
  }
  if (pdfViewerState.currentDoc && pdfViewerState.currentPage) {
    renderPdfPage(pdfViewerState.currentPage, pdfViewerState.currentQuote);
  }
}

function renderBadgesAndProgress() {
  const metrics = computeSplitMetrics();
  const allQs = getAllQuestions();
  const reviewedCount = Object.values(state.reviews).filter((r) => r.decision).length;

  $("visVerifiedProgress").textContent = `${metrics.total.verified} / ${allQs.length} verified`;
  $("visReviewProgress").textContent = `${reviewedCount} / ${allQs.length} reviewed`;
  $("visTotalStatsChip").textContent = `${metrics.total.questions} questions · ${metrics.total.golden_quotes} golden quotes`;
}

function renderVisSplitStats() {
  const metrics = computeSplitMetrics();
  const container = $("visDatasetStats");
  if (!container) return;

  const fragment = document.createDocumentFragment();
  const grid = node("div", "split-card-grid");

  // Dev Split Card
  const devCard = node("div", `split-card dev-theme clickable ${state.filters.split === "dev" ? "active-split-card" : ""}`);
  devCard.append(
    node("div", "split-card-head", "Dev Split"),
    node("div", "split-metric-main", `${metrics.dev.questions} questions`),
    node("div", "split-metric-detail", `${metrics.dev.golden_quotes} golden quotes · ${metrics.dev.evidence_groups} evidence groups`),
    node(
      "div",
      "split-verified-stat",
      `Answer keys: ${metrics.dev.verified} verified · ${metrics.dev.unverified} unverified`,
    ),
    node(
      "div",
      "split-categories",
      `Origin: ${metrics.dev.synthetic} synthetic | ${metrics.dev.human} human`,
    ),
  );
  devCard.addEventListener("click", () => {
    state.filters.split = state.filters.split === "dev" ? "all" : "dev";
    $("filterSplit").value = state.filters.split;
    onFiltersChanged();
  });

  // Test Split Card
  const testCard = node("div", `split-card test-theme clickable ${state.filters.split === "test" ? "active-split-card" : ""}`);
  testCard.append(
    node("div", "split-card-head", "Test Split"),
    node("div", "split-metric-main", `${metrics.test.questions} questions`),
    node("div", "split-metric-detail", `${metrics.test.golden_quotes} golden quotes · ${metrics.test.evidence_groups} evidence groups`),
    node(
      "div",
      "split-verified-stat",
      `Answer keys: ${metrics.test.verified} verified · ${metrics.test.unverified} unverified`,
    ),
    node(
      "div",
      "split-categories",
      `Origin: ${metrics.test.synthetic} synthetic | ${metrics.test.human} human`,
    ),
  );
  testCard.addEventListener("click", () => {
    state.filters.split = state.filters.split === "test" ? "all" : "test";
    $("filterSplit").value = state.filters.split;
    onFiltersChanged();
  });

  // Total Card
  const totalCard = node("div", `split-card total-theme clickable ${state.filters.split === "all" ? "active-split-card" : ""}`);
  totalCard.append(
    node("div", "split-card-head", "Entire Corpus"),
    node("div", "split-metric-main", `${metrics.total.questions} total items`),
    node("div", "split-metric-detail", `${metrics.total.golden_quotes} golden quotes across 38 PDF pages`),
    node(
      "div",
      "split-verified-stat",
      `Total: ${metrics.total.verified} verified · ${metrics.total.unverified} unverified`,
    ),
    node(
      "div",
      "split-categories",
      `All origins: ${metrics.total.synthetic} synthetic | ${metrics.total.human} human`,
    ),
  );
  totalCard.addEventListener("click", () => {
    state.filters.split = "all";
    $("filterSplit").value = "all";
    onFiltersChanged();
  });

  grid.append(devCard, testCard, totalCard);
  fragment.append(grid);
  container.replaceChildren(fragment);
}

function renderSourceFilterOptions() {
  const select = $("filterSource");
  const all = getAllQuestions();
  const counts = new Map(SOURCE_DOCUMENTS.map((doc) => [doc.file, 0]));
  all.forEach((q) => {
    questionSources(q).forEach((file) => {
      if (counts.has(file)) counts.set(file, counts.get(file) + 1);
    });
  });

  const allOption = node("option", "", `All sources (${all.length})`);
  allOption.value = "all";
  select.replaceChildren(
    allOption,
    ...SOURCE_DOCUMENTS.map((doc) => {
      const option = node("option", "", `${doc.label} (${counts.get(doc.file)})`);
      option.value = doc.file;
      return option;
    }),
  );
  select.value = state.filters.source;
}

function syncFilterControls() {
  document.querySelectorAll(".segmented").forEach((group) => {
    const value = state.filters[group.dataset.filter];
    group.querySelectorAll("button").forEach((button) => {
      const active = button.dataset.value === value;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  });
  $("filterSearch").value = state.filters.search;
  $("filterSplit").value = state.filters.split;
  $("filterSource").value = state.filters.source;

  $("clearFilters").disabled = JSON.stringify(state.filters) === JSON.stringify(defaultFilters());
}

function renderVisQuestionPicker() {
  const filtered = getFilteredQuestions();
  const picker = $("visQuestionSelect");
  picker.replaceChildren(
    ...filtered.map((q) => {
      const verificationIcon = q.verified ? "✓" : "⚠";
      const originTag = q.origin === "human" ? "[Human]" : "[AI]";
      const shortTitle = q.question.length > 70 ? `${q.question.slice(0, 67)}...` : q.question;
      const option = node("option", "", `${verificationIcon} ${q.id} ${originTag} · ${shortTitle}`);
      option.value = q.id;
      return option;
    }),
  );

  const active = activeVisQuestion();
  if (active && filtered.some((q) => q.id === active.id)) {
    picker.value = active.id;
  } else if (filtered.length > 0) {
    state.visQuestionId = filtered[0].id;
    picker.value = filtered[0].id;
  }

  renderSourceFilterOptions();
  syncFilterControls();
}

// Keeps the stepper honest: position in the filtered list, and no Prev/Next past
// either end. A focused button is released before it is disabled, because a
// disabled element can swallow the arrow keys.
function updateVisNav() {
  const filtered = getFilteredQuestions();
  const index = filtered.findIndex((q) => q.id === state.visQuestionId);
  $("visPosition").textContent = filtered.length ? `${index + 1} / ${filtered.length}` : "0 / 0";

  [
    [$("previousVisQuestion"), index <= 0],
    [$("nextVisQuestion"), index < 0 || index >= filtered.length - 1],
  ].forEach(([button, disabled]) => {
    if (disabled && document.activeElement === button) button.blur();
    button.disabled = disabled;
  });

  const saveNext = $("visSaveNext");
  if (saveNext) saveNext.disabled = $("nextVisQuestion").disabled;
}

function renderVisQuestionBadges(q) {
  const container = $("visQuestionBadges");
  if (!container) return;
  if (!q) {
    container.replaceChildren();
    return;
  }

  const badges = [];

  if (q.origin === "human") {
    badges.push(node("span", "chip origin-human", "Human-written"));
  } else {
    badges.push(node("span", "chip origin-synthetic", "AI-written"));
  }

  badges.push(node("span", "chip neutral", `${q.split.toUpperCase()} split`));
  badges.push(node("span", "chip neutral", q.category));

  if (q.is_hard_case) {
    badges.push(node("span", "chip chip-hard-case", "Hard case"));
  }

  if (q.is_edited) {
    badges.push(node("span", "chip neutral", "✎ Edited"));
  }

  container.replaceChildren(...badges);
}

function updateReview(field, value) {
  const q = activeVisQuestion();
  if (!q) return;
  state.reviews[q.id] = {
    ...(state.reviews[q.id] || {}),
    [field]: value,
    updated_at: new Date().toISOString(),
  };
  saveReviews();
  if (field === "decision") renderBadgesAndProgress();
}

// Updated in place rather than re-rendered, so annotating cannot move anything.
function setDecision(value) {
  updateReview("decision", value);
  document.querySelectorAll(".decision").forEach((label) => {
    const input = label.querySelector("input");
    input.checked = input.value === value;
    label.classList.toggle("selected", input.checked);
  });
}

// Some changes can drop the question out of the current filter, such as verifying
// under "Unverified". Carry on with the one that took its place instead of jumping
// back to the start. Returns true if it moved.
function changeKeepingPlace(questionId, change) {
  const index = getFilteredQuestions().findIndex((q) => q.id === questionId);
  change();

  const remaining = getFilteredQuestions();
  if (!remaining.length || remaining.some((q) => q.id === questionId)) return false;
  state.visQuestionId = remaining[Math.min(Math.max(index, 0), remaining.length - 1)].id;
  state.activeEvidenceIndex = 0;
  return true;
}

function setAnswerKeyVerification(questionId, isVerified) {
  changeKeepingPlace(questionId, () => {
    state.verifications[questionId] = isVerified;
    saveVerifications();
  });

  renderVisSplitStats();
  renderBadgesAndProgress();
  renderVisQuestionPicker();
  renderVisContent();
}

function renderVisContent() {
  if (state.editor) {
    renderQuestionEditor();
    return;
  }

  const content = $("visContent");
  const filtered = getFilteredQuestions();
  const q = activeVisQuestion();

  if (!q || !filtered.length) {
    content.replaceChildren(
      node(
        "div",
        "empty-filter-state",
        "No questions match your current filters. Clear filters or add a new question.",
      ),
    );
    const source = state.filters.source === "all" ? "topic1" : state.filters.source;
    const syncKey = `empty:${source}`;
    if (syncKey !== state.pdfSyncKey) {
      state.pdfSyncKey = syncKey;
      showEvidence(null, source);
    }
    updateVisNav();
    return;
  }

  // Flatten all evidence items for this question
  const allEvidence = (q.evidence_groups || []).flatMap((g) =>
    (g.alternatives || []).map((alt) => ({
      groupId: g.id,
      documentId: alt.document_id,
      page: alt.pdf_page,
      quote: alt.quote,
    })),
  );

  // Ensure activeEvidenceIndex is valid, default to first (index 0)
  if (state.activeEvidenceIndex == null || state.activeEvidenceIndex >= allEvidence.length) {
    state.activeEvidenceIndex = 0;
  }

  // Move the PDF only when the question or evidence actually changed. Annotating
  // re-renders this column and must not reset a page the reviewer turned to.
  const syncKey = `${q.id}:${state.activeEvidenceIndex}`;
  if (syncKey !== state.pdfSyncKey) {
    state.pdfSyncKey = syncKey;
    showEvidence(allEvidence[state.activeEvidenceIndex] || null, q.source_document || "topic1");
  }

  const container = node("div", "vis-left-col");

  // 1. Question Card
  const questionCard = node("section", "review-card question-display-card");
  const qHead = node("div", "card-header-row");
  const badgeStrip = node("div", "question-badge-strip");
  badgeStrip.id = "visQuestionBadges";
  const editBtn = node("button", "btn-secondary btn-sm card-edit-btn", "✎ Edit");
  editBtn.type = "button";
  editBtn.title = "Edit the question, answer key, evidence and scoring facts (E)";
  editBtn.addEventListener("click", () => openQuestionEditor(q));
  qHead.append(node("span", "q-id-pill", q.id), badgeStrip, editBtn);
  questionCard.append(qHead, node("p", "question-title-text vis-scroll", q.question));
  container.append(questionCard);

  // 2. Answer Key Card (Verification & Editing)
  const answerCard = node("section", `review-card answer-key-card ${q.verified ? "card-verified" : "card-unverified"}`);
  const aHead = node("div", "card-header-row");
  const aTitle = node("div", "a-title-group");
  aTitle.append(
    node("p", "eyebrow", "Answer key"),
    node(
      "span",
      `status-indicator ${q.verified ? "verified" : "unverified"}`,
      q.verified ? "✓ Verified" : "⚠ Unverified",
    ),
  );
  const aActions = node("div", "card-action-group");
  const verifyBtn = node(
    "button",
    `${q.verified ? "btn-subtle" : "btn-primary"} btn-sm btn-verify`,
    q.verified ? "Unverify" : "Verify",
  );
  verifyBtn.type = "button";
  verifyBtn.title = `Mark as ${q.verified ? "unverified" : "verified"} (V)`;
  verifyBtn.addEventListener("click", () => setAnswerKeyVerification(q.id, !q.verified));
  aActions.append(verifyBtn);

  aHead.append(aTitle, aActions);
  answerCard.append(
    aHead,
    node("p", "answer-value-text vis-scroll", q.reference_answer || "(No answer key provided)"),
  );
  container.append(answerCard);

  // 3. Gold Evidence & Supporting Context Cards (Clickable cards referring to PDF & page)
  const detailsCard = node("section", "review-card evidence-details-card");
  const evHead = node("div", "card-header-row");
  evHead.append(
    node("p", "eyebrow", "Gold evidence & supporting context"),
    node("span", "evidence-instruction", "Click a quote to show it in the PDF"),
  );
  detailsCard.append(evHead);

  const detailsBody = node("div", "vis-scroll evidence-scroll");

  const evList = node("ul", "evidence-item-list");
  if (allEvidence.length === 0) {
    evList.append(node("li", "empty-item", "No gold quotes recorded for this question."));
  } else {
    allEvidence.forEach((ev, index) => {
      const isSelected = index === state.activeEvidenceIndex;
      const item = node("li", `evidence-item clickable ${isSelected ? "active-evidence-card" : ""}`);
      const itemTop = node("div", "evidence-item-top");
      itemTop.append(
        node("span", "doc-badge", `${ev.documentId} · Page ${ev.page}`),
        node("span", `evidence-jump-pill ${isSelected ? "active-pill" : ""}`, isSelected ? "● In PDF" : "Show"),
      );
      item.append(itemTop, node("blockquote", "quote-text", `"${ev.quote}"`));

      item.addEventListener("click", () => {
        state.activeEvidenceIndex = index;
        state.pdfSyncKey = `${q.id}:${index}`;
        document.querySelectorAll(".evidence-item").forEach((el, i) => {
          const active = i === index;
          el.classList.toggle("active-evidence-card", active);
          const pill = el.querySelector(".evidence-jump-pill");
          if (pill) {
            pill.textContent = active ? "● In PDF" : "Show";
            pill.classList.toggle("active-pill", active);
          }
        });
        showEvidence(ev);
      });

      evList.append(item);
    });
  }
  detailsBody.append(evList);

  if (q.required_facts && q.required_facts.length > 0) {
    detailsBody.append(node("p", "eyebrow fact-heading", "Required scoring facts"));
    const factsList = node("ul", "fact-item-list");
    q.required_facts.forEach((fact) => factsList.append(node("li", "", fact)));
    detailsBody.append(factsList);
  }

  // Model generation trace if available
  const runTrace = q.traces ? (q.traces[state.runId] || Object.values(q.traces)[0]) : null;
  if (runTrace && runTrace.generation) {
    detailsBody.append(node("p", "eyebrow fact-heading", "Model generated answer (latest run)"));
    const genBox = node("div", "model-gen-box");
    genBox.append(node("p", "model-gen-text", runTrace.generation.answer || JSON.stringify(runTrace.generation)));
    if (runTrace.assistant_review) {
      const rev = runTrace.assistant_review;
      const scoreRow = node("div", "assistant-scores");
      scoreRow.append(
        node("span", "chip neutral", `Faithfulness: ${rev.faithfulness ?? "—"}/2`),
        node("span", "chip neutral", `Correctness: ${rev.correctness ?? "—"}/2`),
        node("span", "chip neutral", `Completeness: ${rev.completeness ?? "—"}/2`),
        node("span", "chip neutral", `Citations: ${rev.citation_support ?? "—"}/2`),
      );
      genBox.append(scoreRow);
    }
    detailsBody.append(genBox);
  }

  detailsCard.append(detailsBody);
  container.append(detailsCard);

  // 4. Human Annotation Form
  const review = state.reviews[q.id] || {};
  const formCard = node("section", "annotation-card");

  const decisions = node("div", "decision-row");
  [
    ["1", "approve", "Approve"],
    ["2", "needs_revision", "Needs revision"],
    ["3", "reject", "Reject"],
  ].forEach(([key, val, label]) => {
    const choice = node("label", `decision ${review.decision === val ? "selected" : ""}`);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "vis-review-decision";
    input.value = val;
    input.checked = review.decision === val;
    input.addEventListener("change", () => setDecision(val));
    choice.append(input, node("kbd", "", key), document.createTextNode(label));
    decisions.append(choice);
  });

  const annotationTop = node("div", "annotation-top");
  annotationTop.append(node("h3", "", "Human annotation"), decisions);
  formCard.append(annotationTop);

  const checks = node("div", "review-checks");
  [
    ["question_clear", "Question clear", Boolean(review.question_clear)],
    ["answer_correct", "Answer correct", Boolean(review.answer_correct)],
    ["evidence_supports", "Evidence supports", Boolean(review.evidence_supports)],
    ["hard_case", "Hard case", q.is_hard_case],
  ].forEach(([field, label, checked]) => {
    const choice = node("label", "check-row");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `review-${field}`;
    input.checked = checked;
    input.addEventListener("change", () => {
      if (field !== "hard_case") {
        updateReview(field, input.checked);
        return;
      }
      const moved = changeKeepingPlace(q.id, () => updateReview(field, input.checked));
      if (moved) {
        renderVisQuestionPicker();
        renderVisContent();
      } else {
        renderVisQuestionBadges(activeVisQuestion());
        updateVisNav();
      }
    });
    choice.append(input, document.createTextNode(label));
    checks.append(choice);
  });
  formCard.append(checks);

  const notesRow = node("div", "annotation-notes-row");
  const notes = document.createElement("textarea");
  notes.id = "visNotes";
  notes.rows = 2;
  notes.placeholder = "Human notes / corrections...";
  notes.setAttribute("aria-label", "Human notes or corrections");
  notes.value = review.notes || "";
  notes.addEventListener("input", () => updateReview("notes", notes.value));

  const navNextBtn = node("button", "btn-primary", "Save & next →");
  navNextBtn.id = "visSaveNext";
  navNextBtn.type = "button";
  navNextBtn.addEventListener("click", () => moveVisQuestion(1));
  notesRow.append(notes, navNextBtn);
  formCard.append(notesRow);

  formCard.append(
    node(
      "p",
      "shortcut-hint",
      "← → move · 1 2 3 decide · V verify · E edit · H hard case · N notes · Esc leave a field",
    ),
  );

  container.append(formCard);
  content.replaceChildren(container);
  renderVisQuestionBadges(q);
  updateVisNav();
}

// Shortcuts stay out of the way of anything that takes text or arrow keys itself.
function onVisKeydown(event) {
  if (!document.body.classList.contains("vis-mode")) return;
  if (state.editor || $("exportDialog").open) return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;

  const target = event.target;
  const isField = target.matches?.("textarea, select, input:not([type=radio]):not([type=checkbox])");
  if (isField) {
    if (event.key === "Escape") target.blur();
    return;
  }

  const q = activeVisQuestion();
  const hasQuestion = q && getFilteredQuestions().length > 0;
  const actions = {
    ArrowLeft: () => moveVisQuestion(-1),
    ArrowRight: () => moveVisQuestion(1),
    1: () => hasQuestion && setDecision("approve"),
    2: () => hasQuestion && setDecision("needs_revision"),
    3: () => hasQuestion && setDecision("reject"),
    v: () => hasQuestion && setAnswerKeyVerification(q.id, !q.verified),
    e: () => hasQuestion && openQuestionEditor(q),
    h: () => $("review-hard_case")?.click(),
    n: () => $("visNotes")?.focus(),
  };

  const action = actions[event.key.length === 1 ? event.key.toLowerCase() : event.key];
  if (action) {
    event.preventDefault();
    action();
  }
}

function moveVisQuestion(offset) {
  const filtered = getFilteredQuestions();
  if (!filtered.length) return;
  const currentIndex = filtered.findIndex((q) => q.id === state.visQuestionId);
  const nextIndex = Math.max(0, Math.min(filtered.length - 1, (currentIndex >= 0 ? currentIndex : 0) + offset));
  state.visQuestionId = filtered[nextIndex].id;
  state.activeEvidenceIndex = 0; // reset to first evidence on question switch
  $("visQuestionSelect").value = state.visQuestionId;
  renderVisContent();
}

function moveTraceQuestion(offset) {
  const questions = state.data.questions || [];
  if (!questions.length) return;
  const currentIndex = questions.findIndex((q) => q.id === state.questionId);
  const nextIndex = Math.max(0, Math.min(questions.length - 1, (currentIndex >= 0 ? currentIndex : 0) + offset));
  state.questionId = questions[nextIndex].id;
  $("questionSelect").value = state.questionId;
  renderTrace();
}

function onFiltersChanged() {
  state.activeEvidenceIndex = 0;
  renderVisSplitStats();
  renderVisQuestionPicker();
  renderVisContent();
}

function clearFilters() {
  state.filters = defaultFilters();
  onFiltersChanged();
}

function renderExportList() {
  const questions = getFilteredQuestions();
  const list = $("exportList");
  list.replaceChildren(
    ...questions.map((q) => {
      const row = node("li", "export-row");
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = state.exportSelection.has(q.id);
      input.disabled = state.exportHumanOnly && q.origin !== "human";
      input.addEventListener("change", () => {
        if (input.checked) state.exportSelection.add(q.id);
        else state.exportSelection.delete(q.id);
        updateExportCount();
      });
      label.append(input, node("span", "q-id-pill", q.id));
      if (q.origin === "human") label.append(node("span", "chip origin-human", "Human"));
      if (q.is_hard_case) label.append(node("span", "chip chip-hard-case", "Hard"));
      label.append(node("span", "export-question", q.question));
      row.append(label);
      return row;
    }),
  );
  updateExportCount();
}

function updateExportCount() {
  const count = state.exportSelection.size;
  $("exportSelectionCount").textContent = `${count} selected`;
  $("exportConfirmBtn").textContent = `Export ${count} question${count === 1 ? "" : "s"}`;
  $("exportConfirmBtn").disabled = count === 0;
}

// Starts from whatever the filters show, so "Human" + "Hard" then Export is the
// quick way to share new hard cases; anything can still be unticked.
function openExportDialog() {
  state.exportSelection = new Set(getFilteredQuestions().map((q) => q.id));
  state.exportHumanOnly = false;
  state.exportSelectionBeforeHumanOnly = null;
  $("exportHumanOnly").checked = false;
  $("visMenu").open = false;
  renderExportList();
  $("exportDialog").showModal();
}

function setExportSelection(selectAll) {
  const eligible = getFilteredQuestions().filter((q) => !state.exportHumanOnly || q.origin === "human");
  state.exportSelection = new Set(selectAll ? eligible.map((q) => q.id) : []);
  renderExportList();
}

// Turning this on unticks every question that is not human-written and keeps them
// unticked; turning it off puts back the ticks it took away.
function setExportHumanOnly(on) {
  state.exportHumanOnly = on;
  $("exportHumanOnly").checked = on;
  if (on) {
    state.exportSelectionBeforeHumanOnly = new Set(state.exportSelection);
    const human = new Set(getAllQuestions().filter((q) => q.origin === "human").map((q) => q.id));
    state.exportSelection = new Set([...state.exportSelection].filter((id) => human.has(id)));
  } else if (state.exportSelectionBeforeHumanOnly) {
    state.exportSelection = state.exportSelectionBeforeHumanOnly;
    state.exportSelectionBeforeHumanOnly = null;
  }
  renderExportList();
}

function exportDataset() {
  const allQs = getAllQuestions().filter(
    (q) => state.exportSelection.has(q.id) && (!state.exportHumanOnly || q.origin === "human"),
  );
  const metrics = computeSplitMetrics();
  const payload = {
    dataset: state.data.dataset.name,
    exported_at: new Date().toISOString(),
    metrics_summary: metrics,
    questions: allQs.map((q) => ({
      id: q.id,
      question: q.question,
      reference_answer: q.reference_answer,
      category: q.category,
      split: q.split,
      origin: q.origin,
      is_hard_case: q.is_hard_case,
      verified: q.verified,
      is_edited_by_human: q.is_edited,
      source_document: q.source_document,
      evidence_groups: q.evidence_groups,
      required_facts: q.required_facts,
      human_review: state.reviews[q.id] || null,
    })),
  };

  const link = document.createElement("a");
  link.href = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
  );
  link.download = `ntbc_evaluation_dataset_${new Date().toISOString().slice(0, 10)}_${allQs.length}q.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  $("exportDialog").close();
}

function importDataset(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      if (!data || !Array.isArray(data.questions)) {
        alert("Invalid format: expected a JSON file with a 'questions' array.");
        return;
      }
      let count = 0;
      data.questions.forEach((incoming) => {
        if (!incoming.id) return;
        count++;
        const q = { ...incoming };

        // Older human ids were a per-browser counter, so a teammate's human-001 is
        // not this browser's human-001 unless the text says so.
        const existing = state.customQuestions.find((cq) => cq.id === q.id);
        const clashes =
          existing &&
          /^human-\d{3}$/.test(q.id) &&
          resolveQuestion(existing, "human").question !== q.question;
        if (clashes) q.id = newHumanId();

        if (!originalQuestion(q.id)) {
          const { human_review, is_edited_by_human, ...stored } = q;
          state.customQuestions.push(stored);
        } else {
          storeQuestionChanges(q.id, {
            question: q.question,
            category: q.category,
            split: q.split,
            required_facts: q.required_facts,
            evidence_groups: q.evidence_groups,
            source_document: q.source_document,
            reference_answer: q.reference_answer,
          });
        }
        if (q.verified !== undefined) {
          state.verifications[q.id] = Boolean(q.verified);
        }
        if (q.human_review) {
          state.reviews[q.id] = q.human_review;
        }
      });
      saveCustomQuestions();
      saveAnswerEdits();
      saveVerifications();
      saveReviews();
      render();
      alert(`Import complete: updated ${count} questions and annotations.`);
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    }
  };
  reader.readAsText(file);
}

// Text the reviewer has selected in the PDF, ready to become the gold quote.
function selectedPdfText() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return "";
  if (!$("pdfTextLayer")?.contains(selection.anchorNode)) return "";
  return selection.toString().replace(/\s+/g, " ").trim();
}

function currentSourceId() {
  const file = pdfViewerState.currentFilename || getDocumentPdf(state.currentPdfState.docId);
  return SOURCE_DOCUMENTS.find((doc) => doc.file === file)?.id || "topic1";
}

function newHumanId() {
  const stamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 6);
  return `human-${stamp}-${random}`;
}

function blankEvidenceGroup(quote = "") {
  return {
    alternatives: [{ document_id: currentSourceId(), pdf_page: pdfViewerState.currentPage || 1, quote }],
  };
}

// The workbench stays put and the PDF stays usable: the editor takes over the left
// column only, because picking evidence means reading the source while typing.
function showQuestionEditor(editor) {
  state.editor = editor;
  document.querySelector(".vis-toolbar").inert = true;
  document.querySelector(".vis-nav").inert = true;
  $("visMenu").open = false;
  renderQuestionEditor();
  document.querySelector(".q-editor textarea")?.focus();
}

function closeQuestionEditor() {
  state.editor = null;
  state.pdfSyncKey = null; // back to the question's own evidence
  state.activeEvidenceIndex = 0;
  document.querySelector(".vis-toolbar").inert = false;
  document.querySelector(".vis-nav").inert = false;
}

function openQuestionEditor(q) {
  showQuestionEditor({
    mode: "edit",
    id: q.id,
    message: "",
    draft: {
      question: q.question,
      reference_answer: q.reference_answer,
      split: q.split,
      category: q.category,
      is_hard_case: q.is_hard_case,
      verified: q.verified,
      source_document: q.source_document,
      facts_text: q.required_facts.join("\n"),
      evidence_groups: structuredClone(q.evidence_groups),
    },
  });
}

function openAddQuestion(isHardCase = false) {
  showQuestionEditor({
    mode: "new",
    id: null,
    isHardCase,
    message: "",
    draft: {
      question: "",
      reference_answer: "",
      split: "test",
      category: isHardCase ? "hard_case" : "definition",
      is_hard_case: isHardCase,
      verified: true,
      source_document: currentSourceId(),
      facts_text: "",
      evidence_groups: [blankEvidenceGroup(selectedPdfText())],
    },
  });
}

function editorField(label, control, className = "") {
  const field = node("label", `q-field ${className}`);
  field.append(node("span", "", label), control);
  return field;
}

function editorTextarea(value, rows, placeholder, onInput) {
  const textarea = document.createElement("textarea");
  textarea.rows = rows;
  textarea.placeholder = placeholder;
  textarea.value = value;
  textarea.addEventListener("input", () => onInput(textarea.value));
  return textarea;
}

function editorSelect(options, value, onChange) {
  const select = document.createElement("select");
  options.forEach(([optionValue, label]) => {
    const option = node("option", "", label);
    option.value = optionValue;
    select.append(option);
  });
  select.value = value;
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function editorButton(label, className, onClick, title = "") {
  const button = node("button", `btn-sm ${className}`, label);
  button.type = "button";
  if (title) button.title = title;
  button.addEventListener("click", onClick);
  return button;
}

function renderEditorEvidence(groups) {
  const wrap = node("div", "q-evidence");

  groups.forEach((group, groupIndex) => {
    const block = node("div", "q-evidence-group");
    const head = node("div", "q-evidence-head");
    head.append(
      node("span", "q-evidence-title", `Required evidence ${groupIndex + 1}`),
      editorButton("+ Alternative", "btn-subtle", () => {
        group.alternatives.push(blankEvidenceGroup().alternatives[0]);
        renderQuestionEditor();
      }, "Another quote that would satisfy this same requirement"),
      editorButton("Remove", "btn-subtle q-remove", () => {
        groups.splice(groupIndex, 1);
        renderQuestionEditor();
      }),
    );
    block.append(head);

    group.alternatives.forEach((alt, altIndex) => {
      const row = node("div", "q-evidence-row");
      const controls = node("div", "q-evidence-controls");

      const file = getDocumentPdf(alt.document_id);
      const docId = SOURCE_DOCUMENTS.find((doc) => doc.file === file)?.id || alt.document_id;
      const docSelect = editorSelect(
        SOURCE_DOCUMENTS.map((doc) => [doc.id, doc.label]),
        docId,
        (value) => { alt.document_id = value; },
      );
      docSelect.setAttribute("aria-label", "Source document");

      const pageInput = document.createElement("input");
      pageInput.type = "number";
      pageInput.min = "1";
      pageInput.value = alt.pdf_page;
      pageInput.setAttribute("aria-label", "PDF page");
      pageInput.addEventListener("input", () => {
        alt.pdf_page = Math.max(1, parseInt(pageInput.value, 10) || 1);
      });

      const useSelection = editorButton("Use PDF selection", "btn-secondary", () => {
        const text = selectedPdfText();
        if (!text) {
          state.editor.message = "Select the quote in the PDF first, then press Use PDF selection.";
        } else {
          alt.quote = text;
          alt.document_id = currentSourceId();
          alt.pdf_page = pdfViewerState.currentPage;
          state.editor.message = "";
        }
        renderQuestionEditor();
      }, "Fill this quote, document and page from the text selected in the PDF");
      // Pressing a button must not clear the selection it is about to read.
      useSelection.addEventListener("mousedown", (event) => event.preventDefault());

      const check = editorButton("Check in PDF", "btn-subtle", () => {
        showEvidence({ documentId: alt.document_id, page: alt.pdf_page, quote: alt.quote.trim() });
      }, "Open this page and highlight the quote. A warning appears if the text does not match.");

      controls.append(
        node("span", "q-or", altIndex > 0 ? "or" : ""),
        docSelect,
        pageInput,
        useSelection,
        check,
      );
      if (group.alternatives.length > 1) {
        controls.append(
          editorButton("×", "btn-subtle q-remove", () => {
            group.alternatives.splice(altIndex, 1);
            renderQuestionEditor();
          }, "Remove this alternative"),
        );
      }

      const quote = editorTextarea(alt.quote, 2, "Exact quote from the PDF...", (value) => { alt.quote = value; });
      quote.setAttribute("aria-label", "Gold evidence quote");
      row.append(controls, quote);
      block.append(row);
    });

    wrap.append(block);
  });

  wrap.append(
    editorButton("+ Add required evidence", "btn-secondary q-add-evidence", () => {
      groups.push(blankEvidenceGroup());
      renderQuestionEditor();
    }),
  );
  return wrap;
}

function renderQuestionEditor() {
  const editor = state.editor;
  const { draft } = editor;
  const content = $("visContent");
  const previousScroll = content.querySelector(".q-editor-body")?.scrollTop || 0;

  const shell = node("section", "q-editor");

  const head = node("div", "q-editor-head");
  const title = node("div", "q-editor-title");
  const heading =
    editor.mode === "edit"
      ? `Edit ${editor.id}`
      : editor.isHardCase
        ? "New hard case"
        : "New question";
  title.append(node("h3", "", heading));
  if (editor.message) title.append(node("p", "q-editor-message", editor.message));
  head.append(
    title,
    editorButton("Cancel", "btn-subtle", () => {
      closeQuestionEditor();
      renderVisContent();
    }),
    editorButton("Save", "btn-primary", saveQuestionEditor),
  );

  const body = node("div", "q-editor-body");
  body.append(
    editorField(
      "Question",
      editorTextarea(draft.question, 2, "Write the question...", (value) => { draft.question = value; }),
    ),
    editorField(
      "Answer key",
      editorTextarea(draft.reference_answer, 2, "Write the expected answer...", (value) => { draft.reference_answer = value; }),
    ),
  );

  const meta = node("div", "q-editor-meta");
  meta.append(
    editorField(
      "Split",
      editorSelect([["test", "Test"], ["dev", "Dev"]], draft.split, (value) => { draft.split = value; }),
    ),
    editorField(
      "Category",
      editorSelect(
        ["definition", "exact", "paraphrase", "relationship", "multi_evidence", "hard_case"].map((c) => [c, c]),
        draft.category,
        (value) => { draft.category = value; },
      ),
    ),
  );
  [
    ["is_hard_case", "Hard case"],
    ["verified", "Answer key verified"],
  ].forEach(([field, label]) => {
    const choice = node("label", "check-row");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = draft[field];
    input.addEventListener("change", () => { draft[field] = input.checked; });
    choice.append(input, document.createTextNode(label));
    meta.append(choice);
  });
  body.append(meta);

  body.append(
    node("p", "q-section-label", "Gold evidence & supporting context"),
    node("p", "q-section-hint", "Every required evidence must be found. Alternatives inside one are either/or."),
    renderEditorEvidence(draft.evidence_groups),
  );

  body.append(
    editorField(
      "Required scoring facts (one per line)",
      editorTextarea(draft.facts_text, 3, "One fact a good answer must contain, per line...", (value) => { draft.facts_text = value; }),
    ),
  );

  shell.append(head, body);
  content.replaceChildren(shell);
  body.scrollTop = previousScroll;
}

function saveQuestionEditor() {
  const editor = state.editor;
  const { draft } = editor;

  const question = draft.question.trim();
  const referenceAnswer = draft.reference_answer.trim();
  if (!question || !referenceAnswer) {
    editor.message = question ? "Enter an answer key." : "Enter a question.";
    renderQuestionEditor();
    return;
  }

  const id = editor.mode === "edit" ? editor.id : newHumanId();

  // Empty quotes are unfinished rows, not evidence.
  const groups = draft.evidence_groups
    .map((group) => ({
      id: group.id,
      alternatives: group.alternatives
        .map((alt) => ({ document_id: alt.document_id, pdf_page: alt.pdf_page, quote: alt.quote.trim() }))
        .filter((alt) => alt.quote),
    }))
    .filter((group) => group.alternatives.length > 0);

  const usedIds = new Set(groups.map((group) => group.id));
  let next = 1;
  groups.forEach((group) => {
    if (group.id) return;
    while (usedIds.has(`${id}-e${next}`)) next++;
    group.id = `${id}-e${next}`;
    usedIds.add(group.id);
  });

  const firstDocument = groups[0]?.alternatives[0]?.document_id;
  const values = {
    question,
    reference_answer: referenceAnswer,
    split: draft.split,
    category: draft.category,
    required_facts: draft.facts_text.split("\n").map((line) => line.trim()).filter(Boolean),
    evidence_groups: groups,
    // Originals are sourced by their evidence alone, so they never gain this field.
    source_document: draft.source_document ? firstDocument || draft.source_document : undefined,
  };

  if (editor.mode === "new") {
    state.customQuestions.push({ id, origin: "human", ...values, is_hard_case: draft.is_hard_case, traces: {} });
    saveCustomQuestions();
  } else {
    storeQuestionChanges(id, values);
    state.reviews[id] = { ...(state.reviews[id] || {}), hard_case: draft.is_hard_case };
    saveReviews();
  }

  state.verifications[id] = draft.verified;
  saveVerifications();

  closeQuestionEditor();
  state.visQuestionId = id;

  // Land on what was just written, even if the current filters would hide it.
  if (!getFilteredQuestions().some((q) => q.id === id)) {
    state.filters = defaultFilters();
  }

  render();
}

function render() {
  renderHeader();
  renderPhases();
  renderDashboardGrid();
  renderRetrieval();
  renderRunSplitStats();
  renderHistory();
  renderTrace();
  renderVisSplitStats();
  renderBadgesAndProgress();
  renderVisQuestionPicker();
  renderVisContent();
}

function initialize(data) {
  state.data = data;
  state.runId = data.selected_run_id;
  state.questionId = data.questions[0].id;

  try {
    state.reviews = JSON.parse(localStorage.getItem(REVIEW_KEY) || "{}");
  } catch {
    state.reviews = {};
  }
  try {
    state.verifications = JSON.parse(localStorage.getItem(VERIFICATION_KEY) || "{}");
  } catch {
    state.verifications = {};
  }
  try {
    state.answerEdits = JSON.parse(localStorage.getItem(ANSWER_EDITS_KEY) || "{}");
  } catch {
    state.answerEdits = {};
  }
  try {
    state.questionEdits = JSON.parse(localStorage.getItem(QUESTION_EDITS_KEY) || "{}");
  } catch {
    state.questionEdits = {};
  }
  try {
    state.customQuestions = JSON.parse(localStorage.getItem(CUSTOM_QUESTIONS_KEY) || "[]");
  } catch {
    state.customQuestions = [];
  }

  state.visQuestionId = data.questions[0].id;

  // Run Select
  $("runSelect").replaceChildren(
    ...data.runs.map((run) => {
      const option = node("option", "", `${runShort(run.id)} · ${run.mode}`);
      option.value = run.id;
      return option;
    }),
  );
  $("runSelect").value = state.runId;

  // Trace Question Select
  $("questionSelect").replaceChildren(
    ...data.questions.map((question) => {
      const option = node("option", "", `${question.id} · ${question.question}`);
      option.value = question.id;
      return option;
    }),
  );

  // Tabs
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });

  // Run page events
  $("runSelect").addEventListener("change", (e) => {
    state.runId = e.target.value;
    render();
  });
  $("questionSelect").addEventListener("change", (e) => {
    state.questionId = e.target.value;
    renderTrace();
  });
  $("prevTraceQuestion").addEventListener("click", () => moveTraceQuestion(-1));
  $("nextTraceQuestion").addEventListener("click", () => moveTraceQuestion(1));

  // Visualization page events
  $("pdfDocSelect").replaceChildren(
    ...SOURCE_DOCUMENTS.map((doc) => {
      const option = node("option", "", doc.label);
      option.value = doc.file;
      return option;
    }),
  );

    $("filterSearch").addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    onFiltersChanged();
  });
  $("filterSplit").addEventListener("change", (e) => {
    state.filters.split = e.target.value;
    onFiltersChanged();
  });
  $("filterSource").addEventListener("change", (e) => {
    state.filters.source = e.target.value;
    onFiltersChanged();
  });
  document.querySelectorAll(".segmented").forEach((group) => {
    group.addEventListener("click", (e) => {
      const button = e.target.closest("button");
      if (!button) return;
      state.filters[group.dataset.filter] = button.dataset.value;
      onFiltersChanged();
    });
  });
  $("clearFilters").addEventListener("click", clearFilters);

  // A focused <select> keeps the arrow keys, so hand them back after each choice.
  document.querySelector('[data-panel="visualization"]').addEventListener("change", (e) => {
    if (e.target.matches("select") && !e.target.closest("dialog")) e.target.blur();
  });
  document.addEventListener("keydown", onVisKeydown);

  // The menu is an overlay; close it on any click outside it.
  document.addEventListener("click", (e) => {
    if ($("visMenu").open && !e.target.closest("#visMenu")) $("visMenu").open = false;
  });

  $("visQuestionSelect").addEventListener("change", (e) => {
    state.visQuestionId = e.target.value;
    state.activeEvidenceIndex = 0;
    renderVisContent();
  });

  // Next and Previous buttons grouped together
  $("previousVisQuestion").addEventListener("click", () => moveVisQuestion(-1));
  $("nextVisQuestion").addEventListener("click", () => moveVisQuestion(1));

  // PDF Controls (Page jump, doc switch, zoom, highlight locate)
  $("pdfPrevPage").addEventListener("click", () => changePdfPage(-1));
  $("pdfNextPage").addEventListener("click", () => changePdfPage(1));
  if ($("pdfPageInput")) {
    $("pdfPageInput").addEventListener("change", (e) => {
      const p = parseInt(e.target.value, 10);
      if (p >= 1) updatePdfViewer(state.currentPdfState.docId, p, state.currentPdfState.quoteText);
    });
  }
  if ($("pdfDocSelect")) {
    $("pdfDocSelect").addEventListener("change", (e) => {
      updatePdfViewer(e.target.value, 1, "");
    });
  }
  if ($("pdfZoomIn")) $("pdfZoomIn").addEventListener("click", () => setPdfZoom(0.15));
  if ($("pdfZoomOut")) $("pdfZoomOut").addEventListener("click", () => setPdfZoom(-0.15));
  if ($("pdfZoomReset")) $("pdfZoomReset").addEventListener("click", () => setPdfZoom(0));
  if ($("pdfHighlightBtn")) $("pdfHighlightBtn").addEventListener("click", locateCurrentQuote);
  if ($("pdfRetryBtn")) {
    $("pdfRetryBtn").addEventListener("click", () => {
      const cur = state.currentPdfState || { docId: "topic1", page: 1, quoteText: "" };
      updatePdfViewer(cur.docId, cur.page, cur.quoteText);
    });
  }

  // Responsive resize observer on PDF viewer container
  const viewerWrap = $("pdfViewerWrap");
  if (viewerWrap && window.ResizeObserver) {
    let resizeTimer = null;
    const ro = new ResizeObserver(() => {
      const newWidth = $("pdfViewport").clientWidth;
      if (newWidth && Math.abs(newWidth - pdfViewerState.lastRenderWidth) > 20) {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
          if (pdfViewerState.currentDoc && pdfViewerState.currentPage) {
            renderPdfPage(pdfViewerState.currentPage, pdfViewerState.currentQuote);
          }
        }, 120);
      }
    });
    ro.observe(viewerWrap);
  }

  // A press here must not clear a PDF selection: it becomes the new gold quote.
  ["btnToggleAddQuestion", "btnToggleAddHardCase"].forEach((id) => {
    $(id).addEventListener("mousedown", (event) => event.preventDefault());
  });
  $("btnToggleAddQuestion").addEventListener("click", () => openAddQuestion(false));
  $("btnToggleAddHardCase").addEventListener("click", () => openAddQuestion(true));

  // Import / Export
  if ($("importDatasetBtn")) {
    $("importDatasetBtn").addEventListener("click", () => $("importDatasetFile").click());
  }
  if ($("importDatasetFile")) {
    $("importDatasetFile").addEventListener("change", (e) => {
      if (e.target.files.length) importDataset(e.target.files[0]);
      e.target.value = ""; // so the same file can be imported again
    });
  }
  $("exportDatasetBtn").addEventListener("click", openExportDialog);
  $("exportConfirmBtn").addEventListener("click", exportDataset);
  $("exportCancelBtn").addEventListener("click", () => $("exportDialog").close());
  $("exportSelectAll").addEventListener("click", () => setExportSelection(true));
  $("exportSelectNone").addEventListener("click", () => setExportSelection(false));
  $("exportHumanOnly").addEventListener("change", (e) => setExportHumanOnly(e.target.checked));

  render();
}

fetch("dashboard_data.json")
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(initialize)
  .catch((error) => {
    document.body.replaceChildren(
      node("div", "load-error", "Dashboard data could not be loaded."),
    );
    const box = document.querySelector(".load-error");
    box.append(node("code", "", "python -m http.server 8766 --directory evaluation"));
    box.append(node("p", "", error.message));
  });
