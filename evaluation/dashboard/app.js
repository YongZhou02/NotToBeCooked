const state = { data: null, runId: null, questionId: null };
const $ = (id) => document.getElementById(id);

const percent = (value) => (value == null ? "—" : `${(value * 100).toFixed(1)}%`);
const scoreValue = (value) => (value == null ? "—" : `${value.toFixed(1)}`);
const methodLabel = (method) => ({ vector: "Vector", keyword: "Keyword", hybrid_rrf: "Hybrid + RRF" })[method] || method;
const runShort = (id) => `${id.slice(0, 8)} · ${id.slice(9, 15)}`;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text;
  return element;
}

function currentRun() {
  return state.data.runs.find((run) => run.id === state.runId);
}

function currentQuestion() {
  return state.data.questions.find((question) => question.id === state.questionId);
}

function renderHeader() {
  const run = currentRun();
  $("datasetName").textContent = state.data.dataset.name;
  $("summaryMeta").replaceChildren(
    node("span", "", `${state.data.dataset.questions} questions · ${state.data.dataset.evidence_groups} evidence · `),
    node("strong", "", `${run.same_source_run_count} runs on this source`),
  );
}

function renderPhases() {
  const fragment = document.createDocumentFragment();
  currentRun().phases.forEach((phase) => {
    const card = node("article", "phase-card");
    card.append(node("span", "phase-number", phase.number), node("h3", "", phase.label));
    const score = node("p", "score", scoreValue(phase.value));
    if (phase.value != null) score.append(node("small", "", " / 100"));
    card.append(score, node("p", "metric", phase.metric));
    const bar = node("div", "bar");
    const fill = node("span");
    fill.style.width = `${Math.max(0, Math.min(100, phase.value || 0))}%`;
    bar.append(fill);
    card.append(bar, node("p", "secondary", phase.secondary));
    fragment.append(card);
  });
  $("phaseGrid").replaceChildren(fragment);
}

function renderRetrieval() {
  const body = $("retrievalBody");
  const methods = currentRun().retrieval_methods;
  if (!Object.keys(methods).length) {
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

function renderHistory() {
  $("runCount").textContent = `${state.data.runs.length} total`;
  const fragment = document.createDocumentFragment();
  state.data.runs.forEach((run) => {
    const extraction = run.phases.find((phase) => phase.id === "extraction");
    const retrieval = run.phases.find((phase) => phase.id === "retrieval");
    const row = node("tr", run.id === state.runId ? "selected-row" : "");
    row.append(
      node("td", "method-name", runShort(run.id)),
      node("td", "", run.mode),
      node("td", "", `${run.same_source_run_count} runs`),
      node("td", "", extraction.value == null ? "—" : `${extraction.value.toFixed(1)}`),
      node("td", "", retrieval.value == null ? "—" : `${retrieval.value.toFixed(1)}`),
      node("td", "", run.generation_answers),
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
  const exact = groups.filter((group) => group.extraction.exact).length;
  const intact = groups.filter((group) => group.chunking.intact).length;
  const retrieved = groups.filter((group) => group.retrieval.hybrid_rrf?.found).length;
  const total = groups.length;
  return [
    statusStep(1, "Extraction", total ? exact === total : null, total ? `${exact}/${total} exact` : "not run"),
    statusStep(2, "Chunking", total ? intact === total : null, total ? `${intact}/${total} intact` : "not run"),
    statusStep(3, "Retrieval", trace?.context.metrics != null ? retrieved === total : null, trace?.context.metrics != null ? `${retrieved}/${total} hybrid` : "not run"),
    statusStep(4, "Context", trace?.context.metrics != null ? trace.context.metrics["complete_evidence@5"] === 1 : null, trace?.context.metrics != null ? `${trace.context.chunks.length} chunks` : "not run"),
    statusStep(5, "Citation", trace?.generation != null ? trace.citation.length > 0 : null, trace?.generation != null ? `${trace.citation.length} citations` : "not run"),
    statusStep(6, "Generation", trace?.generation == null ? null : trace.generation.grounded, trace?.generation != null ? (trace.generation.grounded ? "grounded" : "not grounded") : "not run"),
  ];
}

function evidenceBlock(title, content) {
  const block = node("div", "evidence-block");
  block.append(node("h3", "", title));
  const pre = node("pre");
  pre.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
  block.append(pre);
  return block;
}

function renderTrace() {
  const question = currentQuestion();
  const trace = question.traces[state.runId];
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
    const extractionStatus = group.extraction.exact
      ? "exact"
      : group.extraction.fuzzy_pass
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
      evidenceBlock("Citation + generation", { citations: trace.citation, answer: trace.generation, review: trace.assistant_review }),
    );
    details.append(body);
    fragment.append(details);
  });
  content.replaceChildren(fragment);
}

function render() {
  renderHeader();
  renderPhases();
  renderRetrieval();
  renderHistory();
  renderTrace();
}

function initialize(data) {
  state.data = data;
  state.runId = data.selected_run_id;
  state.questionId = data.questions[0].id;
  $("runSelect").replaceChildren(
    ...data.runs.map((run) => {
      const option = node("option", "", `${runShort(run.id)} · ${run.mode}`);
      option.value = run.id;
      return option;
    }),
  );
  $("runSelect").value = state.runId;
  $("questionSelect").replaceChildren(
    ...data.questions.map((question) => {
      const option = node("option", "", `${question.id} · ${question.question}`);
      option.value = question.id;
      return option;
    }),
  );
  $("runSelect").addEventListener("change", (event) => {
    state.runId = event.target.value;
    render();
  });
  $("questionSelect").addEventListener("change", (event) => {
    state.questionId = event.target.value;
    renderTrace();
  });
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
    box.append(node("code", "", "python -m http.server 8768 --directory evaluation/dashboard"));
    box.append(node("p", "", error.message));
  });
