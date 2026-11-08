import { phaseHelp } from "@/lib/help"
import { methodLabel, percent, scoreValue } from "@/lib/format"
import type { AllMetrics } from "@/lib/questions"
import type { DashboardData, Run } from "@/types"
import { cn } from "@workspace/ui/lib/utils"
import { ConcernsSection } from "./ConcernsSection"
import {
  Chip,
  Eyebrow,
  HelpButton,
  Panel,
  ScrollTable,
  SectionHead,
} from "./bits"

export function DashboardTab({
  data,
  run,
  metrics,
  onOpenQuestion,
}: {
  data: DashboardData
  run: Run
  metrics: AllMetrics
  onOpenQuestion: (id: string) => void
}) {
  const questionIds = new Set(data.questions.map((q) => q.id))
  const methods = run.retrieval_methods ?? {}
  const methodNames = ["vector", "keyword", "hybrid_rrf"].filter(
    (name) => methods[name]
  )

  return (
    <div className="mx-auto grid w-full max-w-[1440px] grid-cols-[minmax(0,1fr)] gap-4 p-4">
      <section
        aria-labelledby="summaryTitle"
        className="flex flex-wrap items-end justify-between gap-2"
      >
        <div>
          <Eyebrow>{data.dataset.name}</Eyebrow>
          <h2
            id="summaryTitle"
            className="text-xl font-semibold tracking-tight"
          >
            Pipeline scorecard and overview
          </h2>
        </div>
        <p className="text-sm text-muted-foreground">
          {metrics.total.questions} questions ({metrics.dev.questions} dev ·{" "}
          {metrics.test.questions} test) · {metrics.total.golden_quotes} golden
          quotes ·{" "}
          <strong className="text-foreground">
            {run.same_source_run_count} runs on this source
          </strong>
        </p>
      </section>

      <section
        aria-label="Pipeline phase scores"
        className="grid grid-cols-2 gap-3 min-[700px]:grid-cols-3 min-[1100px]:grid-cols-6"
      >
        {run.phases.map((phase) => (
          <article
            key={phase.id}
            className="flex min-w-0 flex-col gap-1 rounded-xl border border-(--line) bg-(--bg-canvas) p-3"
          >
            <div className="flex items-center justify-between">
              <span className="flex size-6 items-center justify-center rounded-full bg-(--bg-raise) text-xs font-semibold text-(--tx-dim)">
                {phase.number}
              </span>
              <HelpButton
                label={`${phase.label}: what does this score mean?`}
                lines={
                  phaseHelp[phase.id] ?? ["Score explanation is not available."]
                }
              />
            </div>
            <h3 className="text-sm font-semibold">{phase.label}</h3>
            <p className="text-2xl font-semibold tabular-nums">
              {scoreValue(phase.value)}
              {phase.value != null && (
                <small className="text-sm font-normal text-muted-foreground">
                  {" "}
                  / 100
                </small>
              )}
            </p>
            <p className="text-xs text-muted-foreground">{phase.metric}</p>
            <p
              className={cn(
                "text-xs font-medium",
                phase.status === "measured" ? "text-(--ok)" : "text-(--cite)"
              )}
            >
              {phase.status === "measured"
                ? "from run artifacts"
                : "not available for this run"}
            </p>
            <div
              className="mt-1 h-1.5 overflow-hidden rounded-full bg-(--bar-track)"
              role="presentation"
            >
              <span
                className="block h-full rounded-full bg-(--acc)"
                style={{
                  width: `${Math.max(0, Math.min(100, phase.value || 0))}%`,
                }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{phase.secondary}</p>
          </article>
        ))}
      </section>

      <ConcernsSection
        concerns={data.concerns}
        selectedRunId={run.id}
        questionIds={questionIds}
        onOpenQuestion={onOpenQuestion}
      />

      <div className="grid gap-4 min-[900px]:grid-cols-2">
        <Panel aria-labelledby="activeRunTitle">
          <SectionHead
            eyebrow="Execution"
            title="Active run overview"
            titleId="activeRunTitle"
            right={<Chip tone="accent">Latest run</Chip>}
          />
          <div className="grid gap-1 text-sm break-words">
            <p>Run ID: {run.id}</p>
            <p>Execution mode: {run.mode}</p>
            <p>Created at: {run.created_at || "Recorded artifact"}</p>
            <p>Questions evaluated in retrieval: {run.questions_evaluated}</p>
            <p>Generated answers: {run.generation_answers}</p>
          </div>
        </Panel>

        <Panel aria-labelledby="corpusSummaryTitle">
          <SectionHead
            eyebrow="Corpus and splits"
            title="Dataset composition"
            titleId="corpusSummaryTitle"
            right={<Chip>Dev + Test</Chip>}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                [
                  "Dev split",
                  metrics.dev,
                  "Purpose: trying out prompts and tuning locally",
                ],
                [
                  "Test split",
                  metrics.test,
                  "Purpose: the formal benchmark (Recall@5 and MRR)",
                ],
              ] as const
            ).map(([title, part, purpose]) => (
              <div
                key={title}
                className="rounded-lg border border-(--line) bg-(--bg-raise) p-3"
              >
                <h4 className="text-sm font-semibold">{title}</h4>
                <p className="text-lg font-semibold">
                  {part.questions} questions
                </p>
                <p className="text-xs text-muted-foreground">
                  {part.golden_quotes} golden quotes · {part.evidence_groups}{" "}
                  evidence groups
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{purpose}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel aria-labelledby="retrievalTitle">
        <SectionHead
          eyebrow="Phase 3"
          title="Retrieval benchmark"
          titleId="retrievalTitle"
          right={<Chip>test split</Chip>}
        />
        <ScrollTable>
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                {[
                  "Method",
                  "Recall@5",
                  "MRR@5",
                  "Hit@1",
                  "Complete@5",
                  "Median latency",
                ].map((h) => (
                  <th key={h} className="px-2 py-1.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {methodNames.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-2 py-3 text-muted-foreground">
                    Not available for this run.
                  </td>
                </tr>
              ) : (
                methodNames.map((name) => {
                  const item = methods[name]!
                  return (
                    <tr
                      key={name}
                      className={cn(
                        "border-t border-(--line-soft)",
                        name === "hybrid_rrf" && "bg-(--bg-raise)"
                      )}
                    >
                      <td className="px-2 py-1.5 font-medium">
                        {methodLabel(name)}
                      </td>
                      <td className="px-2 py-1.5">
                        {percent(item["evidence_recall@5"])}
                      </td>
                      <td className="px-2 py-1.5">
                        {item["mrr@5"].toFixed(3)}
                      </td>
                      <td className="px-2 py-1.5">{percent(item["hit@1"])}</td>
                      <td className="px-2 py-1.5">
                        {percent(item["complete_evidence@5"])}
                      </td>
                      <td className="px-2 py-1.5">
                        {item.median_retrieval_ms.toFixed(1)} ms
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </ScrollTable>
      </Panel>
    </div>
  )
}
