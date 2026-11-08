import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"
import { traceHelp } from "@/lib/help"
import { runShort } from "@/lib/format"
import type { AllMetrics } from "@/lib/questions"
import type { SourceDocument } from "@/lib/documents"
import type { DashboardData, Question, RunTrace } from "@/types"
import {
  Chip,
  Eyebrow,
  HelpButton,
  Panel,
  ScrollTable,
  SectionHead,
} from "./bits"

interface Step {
  number: number
  label: string
  pass: boolean | null
  detail: string
}

function traceSteps(trace: RunTrace | undefined): Step[] {
  const groups = trace?.groups ?? []
  const exact = groups.filter((g) => g.extraction?.exact).length
  const intact = groups.filter((g) => g.chunking?.intact).length
  const retrieved = groups.filter((g) => g.retrieval?.hybrid_rrf?.found).length
  const total = groups.length
  const hasContext = trace?.context?.metrics != null
  const citations = trace?.citation?.length ?? 0
  return [
    {
      number: 1,
      label: "Extraction",
      pass: total ? exact === total : null,
      detail: total ? `${exact}/${total} exact` : "not run",
    },
    {
      number: 2,
      label: "Chunking",
      pass: total ? intact === total : null,
      detail: total ? `${intact}/${total} intact` : "not run",
    },
    {
      number: 3,
      label: "Retrieval",
      pass: hasContext ? retrieved === total : null,
      detail: hasContext ? `${retrieved}/${total} hybrid` : "not run",
    },
    {
      number: 4,
      label: "Context",
      pass: hasContext
        ? trace?.context?.metrics?.["complete_evidence@5"] === 1
        : null,
      detail: hasContext
        ? `${trace?.context?.chunks.length ?? 0} chunks`
        : "not run",
    },
    {
      number: 5,
      label: "Citation",
      pass: trace?.generation != null ? citations > 0 : null,
      detail: trace?.generation != null ? `${citations} citations` : "not run",
    },
    {
      number: 6,
      label: "Generation",
      pass:
        trace?.generation == null ? null : Boolean(trace.generation.grounded),
      detail:
        trace?.generation != null
          ? trace.generation.grounded
            ? "grounded"
            : "not grounded"
          : "not run",
    },
  ]
}

function EvidenceBlock({
  title,
  content,
}: {
  title: string
  content: unknown
}) {
  const help = traceHelp[title] ?? ["Trace data for this stage."]
  return (
    <div className="grid min-w-0 gap-1">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold">{title}</h4>
        <HelpButton
          label={`${title}: what does this section mean?`}
          lines={help}
          align="start"
        />
      </div>
      {traceHelp[title]?.[0] && (
        <p className="text-xs text-muted-foreground">{traceHelp[title][0]}</p>
      )}
      <pre className="max-h-64 overflow-auto rounded-md bg-(--bg-raise) p-2 text-xs">
        {typeof content === "string"
          ? content
          : (JSON.stringify(content, null, 2) ?? "null")}
      </pre>
    </div>
  )
}

export function RunsTab({
  data,
  runId,
  onSelectRun,
  traceQuestionId,
  onSelectTraceQuestion,
  metrics,
  registry,
}: {
  data: DashboardData
  runId: string
  onSelectRun: (id: string) => void
  traceQuestionId: string
  onSelectTraceQuestion: (id: string) => void
  metrics: AllMetrics
  registry: readonly SourceDocument[]
}) {
  const questions = data.questions
  const index = Math.max(
    0,
    questions.findIndex((q) => q.id === traceQuestionId)
  )
  const question: Question | undefined = questions[index]
  const trace = question?.traces?.[runId]
  const pages = registry.reduce((sum, d) => sum + (d.pages ?? 0), 0)
  const listed = data.dataset.documents ?? []

  const move = (offset: number) => {
    const next =
      questions[Math.max(0, Math.min(questions.length - 1, index + offset))]
    if (next) onSelectTraceQuestion(next.id)
  }

  return (
    <div className="mx-auto grid w-full max-w-[1440px] grid-cols-[minmax(0,1fr)] gap-4 p-4">
      <section className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Execution and benchmarking</Eyebrow>
          <h2 className="text-xl font-semibold tracking-tight">
            Run evaluations
          </h2>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs text-muted-foreground">
            <span>Selected run</span>
            <select
              aria-label="Select evaluation run"
              value={runId}
              onChange={(e) => onSelectRun(e.target.value)}
              className="h-9 max-w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
            >
              {data.runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {runShort(r.id)} · {r.mode}
                </option>
              ))}
            </select>
          </label>
          <Button
            type="button"
            disabled
            title="This is a read-only viewer. Runs are started from the command line with: uv run --project apps/api python evaluation/run_eval.py"
          >
            Run evaluation
          </Button>
        </div>
      </section>

      <Panel aria-labelledby="runSplitTitle">
        <SectionHead
          eyebrow="Dataset split composition"
          title="Dev and test split metrics"
          titleId="runSplitTitle"
          right={
            <Chip>
              Corpus: {listed.length || registry.length} source PDF
              {(listed.length || registry.length) === 1 ? "" : "s"}
              {pages ? ` (${pages} pages)` : ""}
            </Chip>
          }
        />
        <div className="grid gap-3 min-[900px]:grid-cols-3">
          {(
            [
              [
                "Dev split",
                metrics.dev,
                "Used for prompt writing and development checks.",
              ],
              [
                "Test split (scored benchmark)",
                metrics.test,
                "The official split scored for Recall@5, MRR@5, Hit@1 and Complete@5.",
              ],
            ] as const
          ).map(([title, part, description]) => (
            <div
              key={title}
              className="rounded-lg border border-(--line) bg-(--bg-raise) p-3"
            >
              <p className="text-xs font-semibold text-muted-foreground uppercase">
                {title}
              </p>
              <p className="text-lg font-semibold">
                {part.questions} questions
              </p>
              <p className="text-xs text-muted-foreground">
                {part.golden_quotes} golden quotes · {part.evidence_groups}{" "}
                evidence groups
              </p>
              <p className="mt-1 text-xs break-words text-muted-foreground">
                {Object.entries(part.categories)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" | ")}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {description}
              </p>
            </div>
          ))}
          <div className="rounded-lg border border-(--line) bg-(--bg-raise) p-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase">
              Corpus overview
            </p>
            <p className="text-lg font-semibold">
              {metrics.total.questions} total items
            </p>
            <p className="text-xs text-muted-foreground">
              {metrics.total.golden_quotes} golden quotes across{" "}
              {(listed.length || registry.length) === 1
                ? "one PDF"
                : `${listed.length || registry.length} PDFs`}
              {pages ? ` (${pages} pages)` : ""}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              AI-written: {metrics.total.synthetic} · Human-written:{" "}
              {metrics.total.human}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {(listed.length ? listed.map((d) => d.id) : []).join(", ")}
            </p>
          </div>
        </div>
      </Panel>

      <Panel aria-labelledby="historyTitle">
        <SectionHead
          eyebrow="Runs"
          title="Run history and comparison"
          titleId="historyTitle"
          right={<Chip>{data.runs.length} total</Chip>}
        />
        <ScrollTable>
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                {[
                  "Run ID",
                  "Mode",
                  "Source count",
                  "Extraction exact",
                  "Retrieval recall",
                  "Generated answers",
                ].map((h) => (
                  <th key={h} className="px-2 py-1.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.runs.map((r) => {
                const extraction = r.phases.find((p) => p.id === "extraction")
                const retrieval = r.phases.find((p) => p.id === "retrieval")
                const selected = r.id === runId
                return (
                  <tr
                    key={r.id}
                    onClick={() => onSelectRun(r.id)}
                    aria-selected={selected}
                    className={cn(
                      "cursor-pointer border-t border-(--line-soft) hover:bg-(--bg-hover)",
                      selected && "bg-(--bg-raise)"
                    )}
                  >
                    <td className="px-2 py-1.5">
                      <button
                        type="button"
                        className="font-medium underline-offset-2 hover:underline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectRun(r.id)
                        }}
                      >
                        {runShort(r.id)}
                      </button>
                    </td>
                    <td className="px-2 py-1.5">{r.mode}</td>
                    <td className="px-2 py-1.5">
                      {r.same_source_run_count} runs
                    </td>
                    <td className="px-2 py-1.5">
                      {extraction?.value == null
                        ? "—"
                        : extraction.value.toFixed(1)}
                    </td>
                    <td className="px-2 py-1.5">
                      {retrieval?.value == null
                        ? "—"
                        : retrieval.value.toFixed(1)}
                    </td>
                    <td className="px-2 py-1.5">{r.generation_answers}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </ScrollTable>
      </Panel>

      <Panel aria-labelledby="traceTitle">
        <SectionHead
          eyebrow="Evidence and trace"
          title="Run drill-down"
          titleId="traceTitle"
          right={
            <div className="flex w-full flex-wrap items-end gap-2 min-[700px]:w-auto">
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  title="Previous question"
                  disabled={index <= 0}
                  onClick={() => move(-1)}
                >
                  ← Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  title="Next question"
                  disabled={index >= questions.length - 1}
                  onClick={() => move(1)}
                >
                  Next →
                </Button>
              </div>
              <label className="grid min-w-0 flex-1 gap-1 text-xs text-muted-foreground min-[700px]:w-80 min-[700px]:flex-none">
                <span>Question</span>
                <select
                  aria-label="Select evidence question"
                  value={question?.id ?? ""}
                  onChange={(e) => onSelectTraceQuestion(e.target.value)}
                  className="h-8 w-full min-w-0 rounded-md border border-input bg-background px-2 text-sm text-foreground"
                >
                  {questions.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.id} · {q.question}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          }
        />
        {question && (
          <>
            <div className="mb-3 rounded-lg bg-(--bg-raise) p-3">
              <h3 className="text-sm font-semibold">
                {question.id} · {question.question}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {question.reference_answer}
              </p>
            </div>
            <div className="mb-3 grid grid-cols-2 gap-2 min-[700px]:grid-cols-3 min-[1100px]:grid-cols-6">
              {traceSteps(trace).map((step) => (
                <div
                  key={step.number}
                  data-state={
                    step.pass == null ? "na" : step.pass ? "pass" : "fail"
                  }
                  className={cn(
                    "flex min-w-0 flex-col rounded-lg border p-2 text-xs",
                    step.pass == null &&
                      "border-(--line) bg-(--bg-raise) text-muted-foreground",
                    step.pass === true &&
                      "border-(--ok)/50 bg-(--ok)/10 text-(--ok)",
                    step.pass === false &&
                      "border-destructive/50 bg-destructive/10 text-(--danger-tx)"
                  )}
                >
                  <strong>
                    {step.number}. {step.label}
                  </strong>
                  <span>{step.detail}</span>
                </div>
              ))}
            </div>
            <div className="grid gap-2">
              {(trace?.groups ?? []).map((group) => {
                const extractionStatus = group.extraction?.exact
                  ? "exact"
                  : group.extraction?.fuzzy_pass
                    ? `fuzzy ${(group.extraction.fuzzy_score ?? 0).toFixed(2)}`
                    : "missing"
                return (
                  <details
                    key={group.id}
                    className="rounded-lg border border-(--line)"
                  >
                    <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                      {group.id} · {extractionStatus}
                    </summary>
                    <div className="grid gap-3 border-t border-(--line-soft) p-3 min-[900px]:grid-cols-2">
                      <EvidenceBlock
                        title="Gold evidence"
                        content={group.alternatives}
                      />
                      <EvidenceBlock
                        title="Extraction"
                        content={group.extraction}
                      />
                      <EvidenceBlock
                        title="Chunking"
                        content={group.chunking}
                      />
                      <EvidenceBlock
                        title="Retrieval ranks"
                        content={group.retrieval}
                      />
                      <EvidenceBlock title="Context" content={trace?.context} />
                      <EvidenceBlock
                        title="Citation + generation"
                        content={{
                          citations: trace?.citation,
                          answer: trace?.generation,
                          review: trace?.assistant_review,
                        }}
                      />
                    </div>
                  </details>
                )
              })}
              {(trace?.groups ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">
                  This run has no trace for this question.
                </p>
              )}
            </div>
          </>
        )}
      </Panel>
    </div>
  )
}
