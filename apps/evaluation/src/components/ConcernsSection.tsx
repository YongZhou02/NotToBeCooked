import { useId, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"
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
  high: "High",
  medium: "Medium",
  low: "Low",
  unknown: "Not known",
}

const SEVERITY_TITLE: Record<ConcernSeverity, string> = {
  high: "High concern",
  medium: "Medium concern",
  low: "Low concern",
  unknown: "How serious this is is not known yet",
}

const SEVERITY_TONE = {
  high: "danger",
  medium: "warn",
  low: "neutral",
  unknown: "neutral",
} as const

const STATUS_TEXT: Record<ConcernStatus, string> = {
  measured: "Measured",
  partly_measured: "Partially",
  not_measured: "Not measured",
}

const STATUS_TITLE: Record<ConcernStatus, string> = {
  measured: "We have a number for this",
  partly_measured: "We have a number for part of this",
  not_measured: "We know it matters but have no number yet",
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

function severityOf(concern: Concern): ConcernSeverity {
  return concern.severity in SEVERITY_ORDER ? concern.severity : "unknown"
}

function statusOf(concern: Concern): ConcernStatus {
  return concern.status in STATUS_TEXT ? concern.status : "not_measured"
}

function Tags({ concern }: { concern: Concern }) {
  const severity = severityOf(concern)
  const status = statusOf(concern)
  return (
    <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
      <Chip tone={SEVERITY_TONE[severity]} title={SEVERITY_TITLE[severity]}>
        {SEVERITY_TEXT[severity]}
      </Chip>
      <Chip tone={STATUS_TONE[status]} title={STATUS_TITLE[status]}>
        {STATUS_TEXT[status]}
      </Chip>
    </div>
  )
}

/** One row in the list: tags, title, description and the main number only. */
function ConcernListItem({
  concern,
  selected,
  onSelect,
}: {
  concern: Concern
  selected: boolean
  onSelect: () => void
}) {
  return (
    <li>
      <button
        type="button"
        aria-pressed={selected}
        data-severity={severityOf(concern)}
        data-status={statusOf(concern)}
        onClick={onSelect}
        className={cn(
          "flex w-full min-w-0 flex-col gap-1.5 rounded-lg border bg-(--bg-raise) p-3 text-left transition-colors hover:border-(--acc) focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
          selected
            ? "border-(--acc) ring-1 ring-(--acc)"
            : "border-(--line)"
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-base font-semibold">{concern.title}</h3>
          <Tags concern={concern} />
        </div>
        <p className="text-sm text-muted-foreground">{concern.feels_like}</p>
        <p className="text-sm font-semibold text-(--tx-strong)">
          {concern.headline}
        </p>
      </button>
    </li>
  )
}

/** The full story for the selected concern: every number, examples, method. */
function ConcernDetail({
  concern,
  knownQuestions,
  onOpenQuestion,
}: {
  concern: Concern
  knownQuestions: ReadonlySet<string>
  onOpenQuestion: (id: string) => void
}) {
  const metrics = concern.metrics ?? []
  const examples = concern.examples ?? []
  return (
    <article
      aria-label={`Details: ${concern.title}`}
      data-testid="concern-detail"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-(--line) bg-(--bg-raise) p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 text-lg font-semibold">{concern.title}</h3>
        <Tags concern={concern} />
      </div>
      <p className="text-sm text-muted-foreground">{concern.feels_like}</p>
      <p className="text-sm font-semibold text-(--tx-strong)">
        {concern.headline}
      </p>

      {metrics.length > 0 && (
        <div className="grid gap-1.5">
          <Eyebrow>Numbers</Eyebrow>
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
        </div>
      )}

      <div className="grid gap-1.5">
        <Eyebrow>Examples</Eyebrow>
        {examples.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No example questions for this concern yet.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Click a question to read it next to its PDF.
            </p>
            <ul className="grid gap-2">
              {examples.map((example, index) => {
                const known = knownQuestions.has(example.question_id)
                // Some examples are chunks, not questions, and carry no id.
                const hasId = Boolean(example.question_id)
                return (
                  <li
                    key={example.question_id || `example-${index}`}
                    className="flex flex-col gap-0.5"
                  >
                    {!hasId ? null : known ? (
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
          </>
        )}
      </div>

      {concern.how_measured && (
        <div className="grid gap-1">
          <Eyebrow>How this was measured</Eyebrow>
          <p className="text-sm text-muted-foreground">
            {concern.how_measured}
          </p>
        </div>
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
  const [pickedId, setPickedId] = useState<string | null>(null)
  // Fall back to the first card if nothing is picked or the pick is gone.
  const selected = sorted.find((c) => c.id === pickedId) ?? sorted[0]

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

      {!selected ? (
        <p className="rounded-lg border border-dashed border-(--line) p-4 text-sm text-muted-foreground">
          {concerns
            ? "No concerns are listed for this run."
            : "No concerns have been recorded yet. They appear here once the evaluation data includes them."}
        </p>
      ) : (
        <div className="grid items-start gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          {/* Roughly three cards tall; the rest scroll inside the list. */}
          <ul
            className="grid max-h-[27rem] gap-2 overflow-y-auto pr-1"
            aria-label="Concerns"
            tabIndex={0}
          >
            {sorted.map((concern) => (
              <ConcernListItem
                key={concern.id}
                concern={concern}
                selected={concern.id === selected.id}
                onSelect={() => setPickedId(concern.id)}
              />
            ))}
          </ul>
          <div className="md:sticky md:top-2">
            <ConcernDetail
              key={selected.id}
              concern={selected}
              knownQuestions={questionIds}
              onOpenQuestion={onOpenQuestion}
            />
          </div>
        </div>
      )}
    </Panel>
  )
}
