import { useId } from "react"

import { Button } from "@workspace/ui/components/button"
import { concernsHelp } from "@/lib/help"
import { runShort } from "@/lib/format"
import type { Concern, ConcernSeverity, ConcernStatus, Concerns } from "@/types"
import { Chip, Eyebrow, HelpButton, Panel } from "./bits"

const SEVERITY_ORDER: Record<ConcernSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
  unknown: 3,
}

const SEVERITY_TEXT: Record<ConcernSeverity, string> = {
  high: "High concern",
  medium: "Medium concern",
  low: "Low concern",
  unknown: "Severity not known",
}

const SEVERITY_TONE = {
  high: "danger",
  medium: "warn",
  low: "neutral",
  unknown: "neutral",
} as const

const STATUS_TEXT: Record<ConcernStatus, string> = {
  measured: "Measured",
  partly_measured: "Partly measured",
  not_measured: "Not measured yet",
}

const STATUS_TONE = {
  measured: "ok",
  partly_measured: "warn",
  not_measured: "neutral",
} as const

/** Highest severity first; ties keep the order they came in. */
function sortConcerns(items: Concern[]): Concern[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort(
      (a, b) =>
        (SEVERITY_ORDER[a.item.severity] ?? 3) -
          (SEVERITY_ORDER[b.item.severity] ?? 3) || a.index - b.index
    )
    .map(({ item }) => item)
}

function ConcernCard({
  concern,
  knownQuestions,
  onOpenQuestion,
}: {
  concern: Concern
  knownQuestions: ReadonlySet<string>
  onOpenQuestion: (id: string) => void
}) {
  const severity =
    concern.severity in SEVERITY_ORDER ? concern.severity : "unknown"
  const status = concern.status in STATUS_TEXT ? concern.status : "not_measured"
  const metrics = concern.metrics ?? []
  const examples = concern.examples ?? []
  return (
    <article
      data-severity={severity}
      data-status={status}
      className="flex min-w-0 flex-col gap-2 rounded-lg border border-(--line) bg-(--bg-raise) p-3"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip tone={SEVERITY_TONE[severity]}>{SEVERITY_TEXT[severity]}</Chip>
        <Chip tone={STATUS_TONE[status]}>{STATUS_TEXT[status]}</Chip>
      </div>
      <h3 className="text-base font-semibold">{concern.title}</h3>
      <p className="text-sm text-muted-foreground">{concern.feels_like}</p>
      <p className="text-sm font-semibold text-(--tx-strong)">
        {concern.headline}
      </p>

      {metrics.length > 0 && (
        <dl className="grid gap-1.5 text-sm">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-md bg-(--bg-canvas) px-2 py-1.5"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <dt className="text-muted-foreground">{metric.label}</dt>
                <dd className="font-semibold">{metric.value}</dd>
              </div>
              {metric.note && (
                <p className="text-xs text-muted-foreground">{metric.note}</p>
              )}
            </div>
          ))}
        </dl>
      )}

      {examples.length > 0 && (
        <div className="grid gap-1">
          <Eyebrow>Examples</Eyebrow>
          <ul className="grid gap-1">
            {examples.map((example) => {
              const known = knownQuestions.has(example.question_id)
              return (
                <li key={example.question_id} className="flex flex-col gap-0.5">
                  {known ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-fit font-mono"
                      title="Open this question in the Visualization tab"
                      onClick={() => onOpenQuestion(example.question_id)}
                    >
                      {example.question_id}
                    </Button>
                  ) : (
                    <span
                      className="w-fit font-mono text-sm text-muted-foreground"
                      title="This question is not in the current question set"
                    >
                      {example.question_id} (not in this question set)
                    </span>
                  )}
                  {example.note && (
                    <span className="text-xs text-muted-foreground">
                      {example.note}
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {concern.how_measured && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            How this was measured
          </summary>
          <p className="mt-1 text-muted-foreground">{concern.how_measured}</p>
        </details>
      )}
    </article>
  )
}

export function ConcernsSection({
  concerns,
  selectedRunId,
  questionIds,
  onOpenQuestion,
}: {
  concerns: Concerns | undefined
  selectedRunId: string
  questionIds: ReadonlySet<string>
  onOpenQuestion: (id: string) => void
}) {
  const titleId = useId()
  const items = concerns?.items ?? []
  const sorted = sortConcerns(items)

  return (
    <Panel aria-labelledby={titleId} data-testid="concerns-section">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <Eyebrow>What students would notice</Eyebrow>
          <div className="flex items-center gap-2">
            <h2 id={titleId} className="text-lg font-semibold tracking-tight">
              Concerns
            </h2>
            <HelpButton
              label="Concerns: what is this section?"
              lines={concernsHelp}
              align="start"
            />
          </div>
        </div>
        {concerns?.run_id && (
          <Chip tone="neutral" title={`Measured on run ${concerns.run_id}`}>
            From run {runShort(concerns.run_id)}
            {concerns.run_id !== selectedRunId && " (not the run selected now)"}
          </Chip>
        )}
      </div>

      {sorted.length === 0 ? (
        <p className="rounded-lg border border-dashed border-(--line) p-4 text-sm text-muted-foreground">
          {concerns
            ? "No concerns are listed for this run."
            : "No concerns have been recorded yet. They appear here once the evaluation data includes them."}
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sorted.map((concern) => (
            <ConcernCard
              key={concern.id}
              concern={concern}
              knownQuestions={questionIds}
              onOpenQuestion={onOpenQuestion}
            />
          ))}
        </div>
      )}
    </Panel>
  )
}
