const REVIEW_KEY = "ntbc-evaluation-human-reviews-v1";
const VERIFICATION_KEY = "ntbc-evaluation-answer-verifications-v1";
const ANSWER_EDITS_KEY = "ntbc-evaluation-answer-edits-v1";
const CUSTOM_QUESTIONS_KEY = "ntbc-evaluation-custom-questions-v1";

const state = {
  data: null,
  runId: null,
  questionId: null,
  visQuestionId: null,
  reviews: {},
  verifications: {},
  answerEdits: {},
  customQuestions: [],
  filters: {
    search: "",
    split: "all",
    origin: "all",
    verification: "all", // Show all questions by default
  },
  editingAnswerKey: false,
  activeEvidenceIndex: 0,
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

function getAllQuestions() {
  const baselineQuestions = (state.data?.questions || []).map((q) => {
    const isEdited = Object.prototype.hasOwnProperty.call(state.answerEdits, q.id);
    const hasVerification = Object.prototype.hasOwnProperty.call(state.verifications, q.id);
    return {
      ...q,
      origin: q.origin || "synthetic",
      is_hard_case: Boolean(q.is_hard_case),
      reference_answer: isEdited ? state.answerEdits[q.id] : q.reference_answer,
      is_edited: isEdited,
      verified: hasVerification ? Boolean(state.verifications[q.id]) : Boolean(q.verified),
      evidence_groups: q.evidence_groups || [],
      required_facts: q.required_facts || [],
      traces: q.traces || {},
    };
  });

  const custom = state.customQuestions.map((q) => {
    const isEdited = Object.prototype.hasOwnProperty.call(state.answerEdits, q.id);
    const hasVerification = Object.prototype.hasOwnProperty.call(state.verifications, q.id);
    return {
      ...q,
      origin: q.origin || "human",
      is_hard_case: Boolean(q.is_hard_case),
      reference_answer: isEdited ? state.answerEdits[q.id] : q.reference_answer,
      is_edited: isEdited,
      verified: hasVerification ? Boolean(state.verifications[q.id]) : Boolean(q.verified),
      evidence_groups: q.evidence_groups || [],
      required_facts: q.required_facts || [],
      traces: q.traces || {},
    };
  });

  return [...baselineQuestions, ...custom];
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

function saveCustomQuestions() {
  localStorage.setItem(CUSTOM_QUESTIONS_KEY, JSON.stringify(state.customQuestions));
}

function setTab(name) {
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
    const cached = pdfViewerState.docCache.get(filename);
    pdfViewerState.currentDoc = cached;
    pdfViewerState.currentFilename = filename;
    pdfViewerState.totalPages = cached.numPages;
    return cached;
  }

  showPdfLoading(`Opening ${filename}...`);
  const lib = await getPdfLib();
  const loadingTask = lib.getDocument({
    url: `../datasets/cpt316/documents/${filename}`,
  });

  const doc = await loadingTask.promise;
  pdfViewerState.docCache.set(filename, doc);
  pdfViewerState.currentDoc = doc;
  pdfViewerState.currentFilename = filename;
  pdfViewerState.totalPages = doc.numPages;
  return doc;
}

async function renderPdfPage(pageNumber, quoteText) {
  if (!pdfViewerState.currentDoc) return;
  const doc = pdfViewerState.currentDoc;
  const targetPage = Math.max(1, Math.min(doc.numPages, parseInt(pageNumber, 10) || 1));
  pdfViewerState.currentPage = targetPage;
  pdfViewerState.currentQuote = quoteText || "";

  // Cancel any running render task
  if (pdfViewerState.renderTask) {
    try { pdfViewerState.renderTask.cancel(); } catch (_) {}
    pdfViewerState.renderTask = null;
  }
  if (pdfViewerState.textLayerTask) {
    try { pdfViewerState.textLayerTask.cancel(); } catch (_) {}
    pdfViewerState.textLayerTask = null;
  }

  showPdfLoading(`Rendering page ${targetPage}...`);

  try {
    const page = await doc.getPage(targetPage);
    const canvas = $("pdfCanvas");
    const viewportBox = $("pdfViewport");
    const pageWrapper = $("pdfPageWrapper");
    const textLayerDiv = $("pdfTextLayer");

    if (!canvas || !viewportBox || !pageWrapper) return;

    // Viewport width calculation
    const containerWidth = Math.max(260, viewportBox.clientWidth - 36);
    pdfViewerState.lastRenderWidth = containerWidth;
    const baseViewport = page.getViewport({ scale: 1.0 });
    const fitScale = containerWidth / baseViewport.width;
    const effectiveScale = fitScale * pdfViewerState.zoomLevel;
    const viewport = page.getViewport({ scale: effectiveScale });

    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    canvas.width = Math.floor(viewport.width * dpr);
    canvas.height = Math.floor(viewport.height * dpr);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;

    pageWrapper.style.width = `${Math.floor(viewport.width)}px`;
    pageWrapper.style.height = `${Math.floor(viewport.height)}px`;
    pageWrapper.style.setProperty("--scale-factor", String(viewport.scale));

    const ctx = canvas.getContext("2d", { alpha: false });
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

    // Render text layer for selection and gold evidence highlight
    if (textLayerDiv && pdfViewerState.lib?.TextLayer) {
      textLayerDiv.replaceChildren();
      textLayerDiv.style.width = `${Math.floor(viewport.width)}px`;
      textLayerDiv.style.height = `${Math.floor(viewport.height)}px`;

      const textContent = await page.getTextContent();
      const textLayer = new pdfViewerState.lib.TextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport,
      });
      pdfViewerState.textLayerTask = textLayer;
      await textLayer.render();
      pdfViewerState.textLayerTask = null;

      applyQuoteHighlight(textLayer, quoteText);
    }

    hidePdfLoading();
  } catch (err) {
    if (err?.name === "RenderingCancelledException") {
      return;
    }
    console.error("PDF render failed:", err);
    showPdfError(`Could not render page ${targetPage}: ${err.message}`);
  }
}

function applyQuoteHighlight(textLayer, quoteText) {
  if (!textLayer || !quoteText || !quoteText.trim()) return;
  const items = textLayer.textContentItemsStr;
  const divs = textLayer.textDivs;
  if (!items || !divs || !items.length) return;

  const hits = quoteItemIndices(items, quoteText);
  if (hits.length > 0) {
    hits.forEach((idx) => {
      if (divs[idx]) {
        divs[idx].classList.add("ntbc-quote");
      }
    });
    const firstIdx = Math.min(...hits);
    if (divs[firstIdx]) {
      divs[firstIdx].scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
}

function locateCurrentQuote() {
  const textLayerDiv = $("pdfTextLayer");
  if (!textLayerDiv) return;
  const highlighted = textLayerDiv.querySelector(".ntbc-quote");
  if (highlighted) {
    highlighted.scrollIntoView({ behavior: "smooth", block: "center" });
    highlighted.classList.remove("ntbc-quote");
    void highlighted.offsetWidth;
    highlighted.classList.add("ntbc-quote");
  } else if (pdfViewerState.currentQuote && pdfViewerState.currentPage) {
    renderPdfPage(pdfViewerState.currentPage, pdfViewerState.currentQuote);
  }
}

async function updatePdfViewer(docId, pageNumber, quoteText) {
  const filename = getDocumentPdf(docId);
  const page = Math.max(1, parseInt(pageNumber, 10) || 1);
  const pdfUrl = `../datasets/cpt316/documents/${filename}#page=${page}&view=FitH`;

  // Synchronize UI labels
  if ($("pdfDocSelect")) $("pdfDocSelect").value = filename;
  if ($("pdfDocName")) $("pdfDocName").textContent = filename;
  if ($("pdfPageInput")) $("pdfPageInput").value = page;
  if ($("pdfOpenTab")) $("pdfOpenTab").href = pdfUrl;
  if ($("pdfQuoteTargetTag")) $("pdfQuoteTargetTag").textContent = `Referenced Gold Evidence · Page ${page}`;
  if ($("pdfQuoteTargetText")) $("pdfQuoteTargetText").textContent = quoteText ? `"${quoteText}"` : "(No direct quote recorded)";

  // Update fallback iframe
  const frame = $("pdfFrame");
  if (frame && frame.src !== new URL(pdfUrl, window.location.href).href) {
    frame.src = pdfUrl;
  }

  state.currentPdfState = {
    docId: docId || "topic1",
    page,
    quoteText: quoteText || "",
  };

  try {
    const doc = await loadPdfDocument(filename);
    const total = doc.numPages;
    if ($("pdfTotalPages")) $("pdfTotalPages").textContent = `/ ${total}`;
    if ($("pdfPageInput")) $("pdfPageInput").max = total;
    if ($("pdfPageIndicator")) $("pdfPageIndicator").textContent = `Page ${page} / ${total}`;

    await renderPdfPage(page, quoteText);
  } catch (err) {
    console.error("Failed to load PDF:", err);
    showPdfError(`Could not load ${filename}: ${err.message}`);
    if (frame) frame.style.display = "block";
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

function renderVisQuestionPicker() {
  const filtered = getFilteredQuestions();
  const picker = $("visQuestionSelect");
  picker.replaceChildren(
    ...filtered.map((q) => {
      const verificationIcon = q.verified ? "✓" : "⚠";
      const originTag = q.origin === "human" ? "[Human]" : "[AI]";
      const shortTitle = q.question.length > 55 ? `${q.question.slice(0, 52)}...` : q.question;
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

  const allCount = getAllQuestions().length;
  $("pickerLabel").textContent = `Questions (${filtered.length} of ${allCount} shown)`;
  $("previousVisQuestion").disabled = filtered.length <= 1;
  $("nextVisQuestion").disabled = filtered.length <= 1;
}

function renderVisQuestionBadges(q) {
  const container = $("visQuestionBadges");
  if (!q) {
    container.replaceChildren();
    return;
  }

  const badges = [];

  if (q.origin === "human") {
    badges.push(node("span", "chip origin-human", "Human-written"));
  } else {
    badges.push(node("span", "chip origin-synthetic", "Synthetic (AI-written)"));
  }

  if (q.is_hard_case) {
    badges.push(node("span", "chip chip-hard-case", "Very hard case"));
  }

  badges.push(node("span", "chip neutral", `${q.split.toUpperCase()} split`));
  badges.push(node("span", "chip neutral", q.category));

  if (q.verified) {
    badges.push(node("span", "chip status-verified", "✓ Verified Answer Key"));
  } else {
    badges.push(node("span", "chip status-unverified", "⚠ Unverified Answer Key"));
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
}

function setAnswerKeyVerification(questionId, isVerified) {
  state.verifications[questionId] = isVerified;
  saveVerifications();
  renderVisSplitStats();
  renderBadgesAndProgress();
  renderVisQuestionPicker();
  renderVisContent();
}

function saveAnswerKeyEdit(questionId, newAnswer, andVerify = false) {
  state.answerEdits[questionId] = newAnswer;
  saveAnswerEdits();
  if (andVerify) {
    state.verifications[questionId] = true;
    saveVerifications();
  }
  state.editingAnswerKey = false;
  renderVisSplitStats();
  renderBadgesAndProgress();
  renderVisQuestionPicker();
  renderVisContent();
}

function renderVisContent() {
  const content = $("visContent");
  const filtered = getFilteredQuestions();
  const q = activeVisQuestion();

  if (!q || !filtered.length) {
    renderVisQuestionBadges(null);
    content.replaceChildren(
      node(
        "div",
        "empty-filter-state",
        "No questions match your current filters. Clear filters or add a new question.",
      ),
    );
    updatePdfViewer("topic1", 1, "");
    return;
  }

  renderVisQuestionBadges(q);

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

  // Update right-hand PDF viewer with active or first evidence item
  if (allEvidence.length > 0) {
    const activeEv = allEvidence[state.activeEvidenceIndex] || allEvidence[0];
    updatePdfViewer(activeEv.documentId, activeEv.page, activeEv.quote);
  } else {
    updatePdfViewer("topic1", 1, "");
  }

  const container = node("div", "vis-left-col");

  // 1. Question Card
  const questionCard = node("section", "review-card question-display-card");
  const qHead = node("div", "card-header-row");
  qHead.append(
    node("p", "eyebrow", q.origin === "human" ? "Human-written question" : "AI-written question"),
    node("span", "q-id-pill", q.id),
  );
  questionCard.append(qHead, node("p", "question-title-text", q.question));
  container.append(questionCard);

  // 2. Answer Key Card (Verification & Editing)
  const answerCard = node("section", `review-card answer-key-card ${q.verified ? "card-verified" : "card-unverified"}`);
  const aHead = node("div", "card-header-row");
  const aTitle = node("div", "a-title-group");
  aTitle.append(
    node("p", "eyebrow", "Answer key (Reference answer)"),
    node(
      "span",
      `status-indicator ${q.verified ? "verified" : "unverified"}`,
      q.verified ? "✓ Verified" : "⚠ Unverified",
    ),
  );

  const aActions = node("div", "card-action-group");
  if (!state.editingAnswerKey) {
    const editBtn = node("button", "btn-secondary btn-sm", "Edit answer key");
    editBtn.type = "button";
    editBtn.addEventListener("click", () => {
      state.editingAnswerKey = true;
      renderVisContent();
    });
    aActions.append(editBtn);

    if (q.verified) {
      const unverifyBtn = node("button", "btn-subtle btn-sm", "Mark as unverified");
      unverifyBtn.type = "button";
      unverifyBtn.addEventListener("click", () => setAnswerKeyVerification(q.id, false));
      aActions.append(unverifyBtn);
    } else {
      const verifyBtn = node("button", "btn-primary btn-sm btn-verify", "Mark as verified");
      verifyBtn.type = "button";
      verifyBtn.addEventListener("click", () => setAnswerKeyVerification(q.id, true));
      aActions.append(verifyBtn);
    }
  }

  aHead.append(aTitle, aActions);
  answerCard.append(aHead);

  if (state.editingAnswerKey) {
    const editBox = node("div", "answer-edit-box");
    const textarea = node("textarea", "answer-textarea");
    textarea.rows = 4;
    textarea.value = q.reference_answer;
    editBox.append(textarea);

    const btnRow = node("div", "button-row");
    const saveBtn = node("button", "btn-secondary", "Save changes");
    saveBtn.type = "button";
    saveBtn.addEventListener("click", () => saveAnswerKeyEdit(q.id, textarea.value.trim(), false));

    const saveAndVerifyBtn = node("button", "btn-primary", "Save & Mark as verified");
    saveAndVerifyBtn.type = "button";
    saveAndVerifyBtn.addEventListener("click", () => saveAnswerKeyEdit(q.id, textarea.value.trim(), true));

    const cancelBtn = node("button", "btn-subtle", "Cancel");
    cancelBtn.type = "button";
    cancelBtn.addEventListener("click", () => {
      state.editingAnswerKey = false;
      renderVisContent();
    });

    btnRow.append(saveAndVerifyBtn, saveBtn, cancelBtn);
    editBox.append(btnRow);
    answerCard.append(editBox);
  } else {
    const aText = node("p", "answer-value-text", q.reference_answer || "(No answer key provided)");
    answerCard.append(aText);
    if (q.is_edited) {
      answerCard.append(node("p", "edited-flag", "✎ Edited by human reviewer"));
    }
  }
  container.append(answerCard);

  // 3. Gold Evidence & Supporting Context Cards (Clickable cards referring to PDF & page)
  const detailsCard = node("section", "review-card evidence-details-card");
  const evHead = node("div", "card-header-row");
  evHead.append(
    node("p", "eyebrow", "Gold evidence & supporting context"),
    node("span", "evidence-instruction", "Tap a card below to jump to that PDF page"),
  );
  detailsCard.append(evHead);

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
        node("span", `evidence-jump-pill ${isSelected ? "active-pill" : ""}`, isSelected ? "● Showing in PDF" : "Tap to view page 📄"),
      );
      item.append(itemTop, node("blockquote", "quote-text", `"${ev.quote}"`));

      item.addEventListener("click", () => {
        state.activeEvidenceIndex = index;
        document.querySelectorAll(".evidence-item").forEach((el, i) => {
          const active = i === index;
          el.classList.toggle("active-evidence-card", active);
          const pill = el.querySelector(".evidence-jump-pill");
          if (pill) {
            pill.textContent = active ? "● Showing in PDF" : "Tap to view page 📄";
            pill.classList.toggle("active-pill", active);
          }
        });
        updatePdfViewer(ev.documentId, ev.page, ev.quote);
      });

      evList.append(item);
    });
  }
  detailsCard.append(evList);

  if (q.required_facts && q.required_facts.length > 0) {
    detailsCard.append(node("p", "eyebrow fact-heading", "Required scoring facts"));
    const factsList = node("ul", "fact-item-list");
    q.required_facts.forEach((fact) => factsList.append(node("li", "", fact)));
    detailsCard.append(factsList);
  }

  // Model generation trace if available
  const runTrace = q.traces ? (q.traces[state.runId] || Object.values(q.traces)[0]) : null;
  if (runTrace && runTrace.generation) {
    detailsCard.append(node("p", "eyebrow fact-heading", "Model generated answer (latest run)"));
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
    detailsCard.append(genBox);
  }

  container.append(detailsCard);

  // 4. Human Annotation Form
  const review = state.reviews[q.id] || {};
  const formCard = node("section", "annotation-card");
  formCard.append(node("h3", "", "Human annotation"));

  const decisions = node("div", "decision-row");
  ["Approve", "Needs revision", "Reject"].forEach((label) => {
    const val = label.toLowerCase().replace(" ", "_");
    const choice = node("label", `decision ${review.decision === val ? "selected" : ""}`);
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "vis-review-decision";
    input.value = val;
    input.checked = review.decision === val;
    input.addEventListener("change", () => {
      updateReview("decision", val);
      renderVisContent();
    });
    choice.append(input, document.createTextNode(label));
    decisions.append(choice);
  });
  formCard.append(decisions);

  const checks = node("div", "review-checks");
  [
    ["question_clear", "Question is clear and unambiguous"],
    ["answer_correct", "Answer key is correct and complete"],
    ["evidence_supports", "Gold quote evidence supports answer"],
  ].forEach(([field, label]) => {
    const choice = node("label", "check-row");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(review[field]);
    input.addEventListener("change", () => updateReview(field, input.checked));
    choice.append(input, document.createTextNode(label));
    checks.append(choice);
  });
  formCard.append(checks);

  const notesLabel = node("label", "notes-field");
  notesLabel.append(node("span", "", "Human notes / corrections"));
  const notes = document.createElement("textarea");
  notes.rows = 3;
  notes.placeholder = "Enter any notes, corrections, or edge-case context...";
  notes.value = review.notes || "";
  notes.addEventListener("input", () => updateReview("notes", notes.value));
  notesLabel.append(notes);
  formCard.append(notesLabel);

  const navNextBtn = node("button", "btn-secondary full-width", "Save & Go to next question →");
  navNextBtn.type = "button";
  navNextBtn.addEventListener("click", () => moveVisQuestion(1));
  formCard.append(navNextBtn);

  container.append(formCard);
  content.replaceChildren(container);
}

function moveVisQuestion(offset) {
  const filtered = getFilteredQuestions();
  if (!filtered.length) return;
  const currentIndex = filtered.findIndex((q) => q.id === state.visQuestionId);
  const nextIndex = Math.max(0, Math.min(filtered.length - 1, (currentIndex >= 0 ? currentIndex : 0) + offset));
  state.visQuestionId = filtered[nextIndex].id;
  state.editingAnswerKey = false;
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
  state.editingAnswerKey = false;
  state.activeEvidenceIndex = 0;
  renderVisQuestionPicker();
  renderVisContent();
}

function exportDataset() {
  const allQs = getAllQuestions();
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
      evidence_groups: q.evidence_groups,
      required_facts: q.required_facts,
      human_review: state.reviews[q.id] || null,
    })),
  };

  const link = document.createElement("a");
  link.href = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
  );
  link.download = `ntbc_evaluation_dataset_${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
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
      data.questions.forEach((q) => {
        if (!q.id) return;
        count++;
        if (q.origin === "human" && !state.customQuestions.some((cq) => cq.id === q.id)) {
          state.customQuestions.push(q);
        }
        if (q.reference_answer) {
          state.answerEdits[q.id] = q.reference_answer;
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

function openAddQuestion(isHardCase = false) {
  const panel = $("addQuestionPanel");
  panel.hidden = false;
  $("newIsHardCase").checked = isHardCase;
  $("addQuestionTitle").textContent = isHardCase ? "Add very hard case (human-authored)" : "Add human-written question";
  $("addQuestionEyebrow").textContent = isHardCase ? "Challenging edge case" : "Human-authored question";
  $("newQuestion").focus();
}

function closeAddQuestion() {
  $("addQuestionPanel").hidden = true;
  $("newQuestion").value = "";
  $("newAnswer").value = "";
  $("newEvidence").value = "";
  $("newFacts").value = "";
  $("newIsHardCase").checked = false;
}

function saveNewHumanQuestion() {
  const questionText = $("newQuestion").value.trim();
  const answerKey = $("newAnswer").value.trim();
  const evidenceText = $("newEvidence").value.trim();
  const docId = $("newDocId").value.trim() || "topic1";
  const page = parseInt($("newPage").value, 10) || 1;
  const split = $("newSplit").value || "test";
  const category = $("newCategory").value || "definition";
  const isHardCase = $("newIsHardCase").checked;
  const isVerified = $("newIsVerified").checked;
  const factsRaw = $("newFacts").value.trim();
  const requiredFacts = factsRaw ? factsRaw.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean) : [];

  if (!questionText) {
    alert("Please enter a question.");
    $("newQuestion").focus();
    return;
  }
  if (!answerKey) {
    alert("Please enter an answer key.");
    $("newAnswer").focus();
    return;
  }

  const existingCount = state.customQuestions.length + 1;
  const newId = `human-${String(existingCount).padStart(3, "0")}`;

  const evidenceGroup = evidenceText
    ? [
        {
          id: `${newId}-e1`,
          alternatives: [
            {
              document_id: docId,
              pdf_page: page,
              quote: evidenceText,
            },
          ],
        },
      ]
    : [];

  const newQuestionObj = {
    id: newId,
    question: questionText,
    reference_answer: answerKey,
    category,
    split,
    origin: "human",
    is_hard_case: isHardCase,
    verified: isVerified,
    required_facts: requiredFacts,
    evidence_groups: evidenceGroup,
    traces: {},
  };

  state.customQuestions.push(newQuestionObj);
  saveCustomQuestions();

  if (isVerified) {
    state.verifications[newId] = true;
    saveVerifications();
  }

  closeAddQuestion();
  state.visQuestionId = newId;
  state.activeEvidenceIndex = 0;

  render();
  renderRunSplitStats();
  renderVisSplitStats();
  renderBadgesAndProgress();
  renderVisQuestionPicker();
  renderVisContent();
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
  $("filterSearch").addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    onFiltersChanged();
  });
  $("filterSplit").addEventListener("change", (e) => {
    state.filters.split = e.target.value;
    onFiltersChanged();
  });
  $("filterOrigin").addEventListener("change", (e) => {
    state.filters.origin = e.target.value;
    onFiltersChanged();
  });
  $("filterVerification").addEventListener("change", (e) => {
    state.filters.verification = e.target.value;
    onFiltersChanged();
  });

  $("visQuestionSelect").addEventListener("change", (e) => {
    state.visQuestionId = e.target.value;
    state.editingAnswerKey = false;
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
    const ro = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const newWidth = Math.floor(entry.contentRect.width);
      if (Math.abs(newWidth - pdfViewerState.lastRenderWidth) > 20) {
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

  // Add question modal controls
  $("btnToggleAddQuestion").addEventListener("click", () => openAddQuestion(false));
  $("btnToggleAddHardCase").addEventListener("click", () => openAddQuestion(true));
  $("cancelHumanQuestion").addEventListener("click", closeAddQuestion);
  $("cancelHumanQuestionBtn").addEventListener("click", closeAddQuestion);
  $("saveHumanQuestion").addEventListener("click", saveNewHumanQuestion);

  // Import / Export
  if ($("importDatasetBtn")) {
    $("importDatasetBtn").addEventListener("click", () => $("importDatasetFile").click());
  }
  if ($("importDatasetFile")) {
    $("importDatasetFile").addEventListener("change", (e) => {
      if (e.target.files.length) importDataset(e.target.files[0]);
    });
  }
  $("exportDatasetBtn").addEventListener("click", exportDataset);

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
    box.append(node("code", "", "python -m http.server 8769 --directory evaluation/dashboard"));
    box.append(node("p", "", error.message));
  });
