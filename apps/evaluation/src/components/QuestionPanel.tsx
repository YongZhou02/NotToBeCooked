import type { RefObject } from "react"

import { Button } from "@workspace/ui/components/button"
import { Textarea } from "@workspace/ui/components/textarea"
import { cn } from "@workspace/ui/lib/utils"
import type { ResolvedQuestion } from "@/lib/questions"
import type { Decision, HumanReview } from "@/types"
import { Chip } from "./bits"
import type { EvidenceItem } from "@/lib/evidence"

const DECISIONS: [string, Decision, string][] = [
  ["1", "approve", "Approve"],
  ["2", "needs_revision", "Needs revision"],
  ["3", "reject", "Reject"],
]

const CHECKS = [
  ["question_clear", "Question clear"],
  ["answer_correct", "Answer correct"],
  ["evidence_supports", "Evidence supports"],
] as const

function Card({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "flex min-h-0 min-w-0 flex-col gap-1 overflow-hidden rounded-lg border border-(--line) bg-(--bg-canvas) px-2.5 py-1.5",
        className
      )}
      {...props}
    />
  )
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold tracking-widest text-(--tx-dim) uppercase">
      {children}
    </p>
  )
}

export function QuestionPanel({
  q,
  runId,
  review,
  evidence,
  activeEvidence,
  notesRef,
  canNext,
  onEdit,
  onVerify,
  onDecision,
  onCheck,
  onHardCase,
  onNotes,
  onSelectEvidence,
  onSaveNext,
}: {
  q: ResolvedQuestion
  runId: string
  review: HumanReview
  evidence: EvidenceItem[]
  activeEvidence: number
  notesRef: RefObject<HTMLTextAreaElement | null>
  canNext: boolean
  onEdit: () => void
  onVerify: () => void
  onDecision: (decision: Decision) => void
  onCheck: (
    field: "question_clear" | "answer_correct" | "evidence_supports",
    value: boolean
  ) => void
  onHardCase: (value: boolean) => void
  onNotes: (value: string) => void
  onSelectEvidence: (index: number, item: EvidenceItem) => void
  onSaveNext: () => void
}) {
  const trace = q.traces[runId] ?? Object.values(q.traces)[0]
  const generation = trace?.generation
  const assistant = trace?.assistant_review

  return (
    <div className="grid h-full min-h-0 grid-rows-[clamp(68px,12vh,104px)_clamp(84px,15vh,136px)_minmax(0,1fr)_auto] gap-1.5">
      <Card data-testid="question-card">
        <div className="flex min-w-0 flex-none items-center gap-2">
          <span className="flex-none rounded border border-(--line) bg-(--bg-raise) px-1.5 font-mono text-xs font-bold text-(--tx-dim)">
            {q.id}
          </span>
          <div className="flex min-w-0 items-center gap-1 overflow-hidden">
            <Chip tone={q.origin === "human" ? "accent" : "neutral"}>
              {q.origin === "human" ? "Human-written" : "AI-written"}
            </Chip>
            <Chip>{q.split.toUpperCase()} split</Chip>
            <Chip>{q.category}</Chip>
            {q.is_hard_case && <Chip tone="warn">Hard case</Chip>}
            {q.is_edited && <Chip>✎ Edited</Chip>}
          </div>
          <Button
            type="button"
            variant="secondary"
            size="xs"
            className="ml-auto"
            title="Edit the question, answer key, evidence and scoring facts (E)"
            onClick={onEdit}
          >
            ✎ Edit
          </Button>
        </div>
        <p className="min-h-0 flex-1 overflow-y-auto text-[15px] leading-snug font-semibold [overflow-wrap:anywhere]">
          {q.question}
        </p>
      </Card>

      <Card
        data-testid="answer-card"
        data-verified={q.verified}
        className={cn(q.verified ? "border-(--ok)/50" : "border-(--cite-line)")}
      >
        <div className="flex flex-none items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Eyebrow>Answer key</Eyebrow>
            <span
              className={cn(
                "text-xs font-semibold",
                q.verified ? "text-(--ok)" : "text-(--cite)"
              )}
            >
              {q.verified ? "✓ Verified" : "⚠ Unverified"}
            </span>
          </div>
          <Button
            type="button"
            size="xs"
            variant={q.verified ? "ghost" : "default"}
            title={`Mark as ${q.verified ? "unverified" : "verified"} (V)`}
            onClick={onVerify}
          >
            {q.verified ? "Unverify" : "Verify"}
          </Button>
        </div>
        <p className="min-h-0 flex-1 overflow-y-auto text-sm [overflow-wrap:anywhere]">
          {q.reference_answer || "(No answer key provided)"}
        </p>
      </Card>

      <Card data-testid="evidence-card">
        <div className="flex flex-none flex-wrap items-center justify-between gap-x-2">
          <Eyebrow>Gold evidence &amp; supporting context</Eyebrow>
          <span className="text-xs text-muted-foreground">
            Click a quote to show it in the PDF
          </span>
        </div>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 [overflow-wrap:anywhere]">
          <ul className="grid gap-1.5">
            {evidence.length === 0 && (
              <li className="text-sm text-muted-foreground">
                No gold quotes recorded for this question.
              </li>
            )}
            {evidence.map((item, index) => {
              const active = index === activeEvidence
              return (
                <li key={`${item.documentId}-${item.page}-${index}`}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => onSelectEvidence(index, item)}
                    className={cn(
                      "w-full rounded-md border p-2 text-left transition-colors",
                      active
                        ? "border-(--cite-line) bg-(--cite-bg)"
                        : "border-(--line) hover:bg-(--bg-hover)"
                    )}
                  >
                    <span className="flex items-center justify-between gap-2 text-xs">
                      <span className="rounded bg-(--bg-raise) px-1.5 py-0.5 font-medium">
                        {item.documentId} · Page {item.page}
                      </span>
                      <span
                        className={
                          active
                            ? "font-semibold text-(--cite)"
                            : "text-(--tx-dim)"
                        }
                      >
                        {active ? "● In PDF" : "Show"}
                      </span>
                    </span>
                    <blockquote className="mt-1 text-sm">
                      &quot;{item.quote}&quot;
                    </blockquote>
                  </button>
                </li>
              )
            })}
          </ul>

          {q.required_facts.length > 0 && (
            <div>
              <Eyebrow>Required scoring facts</Eyebrow>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
                {q.required_facts.map((fact, i) => (
                  <li key={i}>{fact}</li>
                ))}
              </ul>
            </div>
          )}

          {generation && (
            <div>
              <Eyebrow>Model generated answer (latest run)</Eyebrow>
              <div className="mt-1 rounded-md bg-(--bg-raise) p-2">
                <p className="text-sm">
                  {generation.answer || JSON.stringify(generation)}
                </p>
                {assistant && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    <Chip>Faithfulness: {assistant.faithfulness ?? "—"}/2</Chip>
                    <Chip>Correctness: {assistant.correctness ?? "—"}/2</Chip>
                    <Chip>Completeness: {assistant.completeness ?? "—"}/2</Chip>
                    <Chip>
                      Citations: {assistant.citation_support ?? "—"}/2
                    </Chip>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </Card>

      <section
        data-testid="annotation-card"
        className="grid min-w-0 gap-1.5 rounded-lg border border-(--line) bg-(--bg-canvas) px-2.5 py-1.5"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Human annotation</h3>
          <div
            role="radiogroup"
            aria-label="Decision"
            className="flex flex-wrap gap-1"
          >
            {DECISIONS.map(([key, value, label]) => {
              const selected = review.decision === value
              return (
                <label
                  key={value}
                  className={cn(
                    "flex cursor-pointer items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
                    selected
                      ? "border-(--acc) bg-primary/15"
                      : "border-(--line) hover:bg-(--bg-hover)"
                  )}
                >
                  <input
                    type="radio"
                    name="vis-review-decision"
                    value={value}
                    checked={selected}
                    onChange={() => onDecision(value)}
                    className="accent-(--acc)"
                  />
                  <kbd className="rounded border border-(--line) bg-(--bg-raise) px-1 font-mono text-[10px]">
                    {key}
                  </kbd>
                  {label}
                </label>
              )
            })}
          </div>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {CHECKS.map(([field, label]) => (
            <label key={field} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                id={`review-${field}`}
                checked={Boolean(review[field])}
                onChange={(e) => onCheck(field, e.target.checked)}
                className="accent-(--acc)"
              />
              {label}
            </label>
          ))}
          <label className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              id="review-hard_case"
              checked={q.is_hard_case}
              onChange={(e) => onHardCase(e.target.checked)}
              className="accent-(--acc)"
            />
            Hard case
          </label>
        </div>

        <div className="flex items-stretch gap-2">
          <Textarea
            ref={notesRef}
            id="visNotes"
            rows={2}
            placeholder="Human notes / corrections..."
            aria-label="Human notes or corrections"
            value={review.notes ?? ""}
            onChange={(e) => onNotes(e.target.value)}
            className="field-sizing-fixed h-14 min-h-0 flex-1 resize-none py-1 md:text-sm"
          />
          <Button
            type="button"
            id="visSaveNext"
            disabled={!canNext}
            onClick={onSaveNext}
            className="h-auto"
          >
            Save &amp; next →
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          ← → move · 1 2 3 decide · V verify · E edit · H hard case · N notes ·
          Esc leave a field
        </p>
      </section>
    </div>
  )
}
