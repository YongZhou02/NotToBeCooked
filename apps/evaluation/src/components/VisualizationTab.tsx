import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { resolveDocument, type SourceDocument } from "@/lib/documents"
import {
  computeSplitMetrics,
  defaultFilters,
  filterQuestions,
  getAllQuestions,
  questionSources,
  type Filters,
  type ResolvedQuestion,
} from "@/lib/questions"
import type { EvalStore } from "@/lib/use-eval-store"
import type { DashboardData, Decision, HumanReview } from "@/types"
import type { FocusRequest } from "@/App"
import { FilterBar } from "./FilterBar"
import { PdfPane, type PdfView } from "./PdfPane"
import { QuestionPanel } from "./QuestionPanel"
import { flattenEvidence, type EvidenceItem } from "@/lib/evidence"

const FIELD_SELECTOR =
  "textarea, select, input:not([type=radio]):not([type=checkbox])"

export function VisualizationTab({
  data,
  registry,
  store,
  all,
  runId,
  focus,
  isActive,
}: {
  data: DashboardData
  registry: readonly SourceDocument[]
  store: EvalStore
  all: ResolvedQuestion[]
  runId: string
  focus: FocusRequest | null
  isActive: boolean
}) {
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [visQuestionId, setVisQuestionId] = useState<string | null>(null)
  const [evState, setEvState] = useState({ qid: "", index: 0 })
  const [pdfView, setPdfView] = useState<PdfView | null>(null)
  const [evidenceView, setEvidenceView] = useState<PdfView | null>(null)
  const [syncedKey, setSyncedKey] = useState<string | null>(null)
  const [handledNonce, setHandledNonce] = useState(0)
  const paneRef = useRef<HTMLDivElement>(null)
  const notesRef = useRef<HTMLTextAreaElement>(null)

  const filtered = useMemo(
    () => filterQuestions(all, filters, registry),
    [all, filters, registry]
  )
  // The question on screen: the one chosen, if the filters still show it.
  const active =
    filtered.find((q) => q.id === visQuestionId) ?? filtered[0] ?? null
  const activeIndex = active ? filtered.indexOf(active) : -1
  const evidenceItems = useMemo(
    () => (active ? flattenEvidence(active) : []),
    [active]
  )
  const evIndex =
    active && evState.qid === active.id && evState.index < evidenceItems.length
      ? evState.index
      : 0

  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>()
    all.forEach((q) =>
      questionSources(registry, q).forEach((id) =>
        counts.set(id, (counts.get(id) ?? 0) + 1)
      )
    )
    return counts
  }, [all, registry])
  const metrics = useMemo(() => computeSplitMetrics(all), [all])
  const reviewedCount = Object.values(store.state.reviews).filter(
    (r) => r.decision
  ).length

  // Points the PDF at a piece of gold evidence, or at a plain first page.
  const showEvidence = (item: EvidenceItem | null, fallbackDocId?: string) => {
    if (item) {
      const docId =
        resolveDocument(registry, item.documentId)?.id ?? item.documentId
      const view = { docId, page: item.page, quote: item.quote }
      setEvidenceView(view)
      setPdfView(view)
    } else {
      const doc = resolveDocument(registry, fallbackDocId)
      setEvidenceView(null)
      setPdfView(doc ? { docId: doc.id, page: 1, quote: "" } : null)
    }
  }

  // Move the PDF only when the question or evidence really changed, so
  // annotating cannot reset a page the reviewer turned to.
  const syncKey = active ? `${active.id}:${evIndex}` : `empty:${filters.source}`
  if (registry.length > 0 && syncKey !== syncedKey) {
    setSyncedKey(syncKey)
    if (active) {
      showEvidence(
        evidenceItems[evIndex] ?? null,
        active.source_document ?? undefined
      )
    } else {
      showEvidence(null, filters.source === "all" ? undefined : filters.source)
    }
  }

  // A request from another tab to show one question.
  if (focus && focus.nonce !== handledNonce) {
    setHandledNonce(focus.nonce)
    setVisQuestionId(focus.id)
    setEvState({ qid: focus.id, index: 0 })
    if (!filtered.some((q) => q.id === focus.id)) setFilters(defaultFilters())
  }

  const changeFilters = (next: Filters) => {
    setFilters(next)
    setEvState({ qid: "", index: 0 })
  }

  const select = (id: string) => {
    setVisQuestionId(id)
    setEvState({ qid: id, index: 0 })
  }

  const move = (offset: number) => {
    if (!filtered.length) return
    const current = activeIndex >= 0 ? activeIndex : 0
    const next =
      filtered[Math.max(0, Math.min(filtered.length - 1, current + offset))]
    if (next) select(next.id)
  }

  // Some changes can drop the question out of the current filter, such as
  // verifying under "Unverified". Carry on with the one that took its place
  // instead of jumping back to the start.
  const changeKeepingPlace = (
    questionId: string,
    change: Parameters<EvalStore["update"]>[0]
  ) => {
    const index = filtered.findIndex((q) => q.id === questionId)
    const next = store.update(change)
    const remaining = filterQuestions(
      getAllQuestions(next, data),
      filters,
      registry
    )
    if (remaining.length && !remaining.some((q) => q.id === questionId)) {
      select(remaining[Math.min(Math.max(index, 0), remaining.length - 1)]!.id)
    }
  }

  const updateReview = (
    id: string,
    patch: Partial<HumanReview>,
    keepPlace = false
  ) => {
    const change: Parameters<EvalStore["update"]>[0] = (p) => ({
      ...p,
      reviews: {
        ...p.reviews,
        [id]: {
          ...(p.reviews[id] ?? {}),
          ...patch,
          updated_at: new Date().toISOString(),
        },
      },
    })
    if (keepPlace) changeKeepingPlace(id, change)
    else store.update(change)
  }

  const setVerified = (id: string, value: boolean) =>
    changeKeepingPlace(id, (p) => ({
      ...p,
      verifications: { ...p.verifications, [id]: value },
    }))

  const setDecision = (decision: Decision) => {
    if (active) updateReview(active.id, { decision })
  }

  // Shortcuts stay out of the way of anything that takes text or arrow keys.
  const onKey = (event: KeyboardEvent) => {
    if (!isActive) return
    if (event.ctrlKey || event.metaKey || event.altKey) return
    const target = event.target as HTMLElement | null
    if (target?.matches?.(FIELD_SELECTOR)) {
      if (event.key === "Escape") target.blur()
      return
    }
    const hasQuestion = Boolean(active)
    const actions: Record<string, () => void> = {
      ArrowLeft: () => move(-1),
      ArrowRight: () => move(1),
      "1": () => hasQuestion && setDecision("approve"),
      "2": () => hasQuestion && setDecision("needs_revision"),
      "3": () => hasQuestion && setDecision("reject"),
      v: () => active && setVerified(active.id, !active.verified),
      h: () =>
        active &&
        updateReview(active.id, { hard_case: !active.is_hard_case }, true),
      n: () => notesRef.current?.focus(),
    }
    const action =
      actions[event.key.length === 1 ? event.key.toLowerCase() : event.key]
    if (action) {
      event.preventDefault()
      action()
    }
  }
  const keyHandler = useRef(onKey)
  useEffect(() => {
    keyHandler.current = onKey
  })
  useEffect(() => {
    const listener = (event: KeyboardEvent) => keyHandler.current(event)
    document.addEventListener("keydown", listener)
    return () => document.removeEventListener("keydown", listener)
  }, [])

  const review = (active && store.state.reviews[active.id]) || {}

  return (
    <div
      data-testid="workbench"
      className="flex flex-col gap-1.5 p-2 min-[1000px]:h-full min-[1000px]:min-h-[540px]"
    >
      <FilterBar
        filters={filters}
        onChange={changeFilters}
        registry={registry}
        sourceCounts={sourceCounts}
        totalCount={all.length}
        verified={metrics.total.verified}
        reviewed={reviewedCount}
        total={all.length}
        inert={false}
      />

      <section
        aria-label="Question navigation"
        className="flex flex-wrap items-center gap-2 rounded-lg border border-(--line) bg-(--bg-canvas) px-2.5 py-1.5"
      >
        <div className="flex items-center gap-1">
          <Button
            type="button"
            id="previousVisQuestion"
            variant="outline"
            size="sm"
            title="Previous question (Left arrow)"
            disabled={activeIndex <= 0}
            onClick={() => move(-1)}
          >
            ← Prev
          </Button>
          <span
            aria-live="polite"
            data-testid="position"
            className="min-w-14 text-center text-sm tabular-nums"
          >
            {filtered.length
              ? `${activeIndex + 1} / ${filtered.length}`
              : "0 / 0"}
          </span>
          <Button
            type="button"
            id="nextVisQuestion"
            variant="outline"
            size="sm"
            title="Next question (Right arrow)"
            disabled={activeIndex < 0 || activeIndex >= filtered.length - 1}
            onClick={() => move(1)}
          >
            Next →
          </Button>
        </div>

        <select
          aria-label="Select question to view and annotate"
          value={active?.id ?? ""}
          onChange={(e) => {
            select(e.target.value)
            e.target.blur()
          }}
          className="h-8 min-w-0 flex-1 basis-48 rounded-md border border-input bg-background px-2 text-sm"
        >
          {filtered.map((q) => (
            <option key={q.id} value={q.id}>
              {q.verified ? "✓" : "⚠"} {q.id}{" "}
              {q.origin === "human" ? "[Human]" : "[AI]"} ·{" "}
              {q.question.length > 70
                ? `${q.question.slice(0, 67)}...`
                : q.question}
            </option>
          ))}
        </select>
      </section>

      <div className="grid min-h-0 gap-2 min-[1000px]:flex-1 min-[1000px]:grid-cols-2 min-[1000px]:grid-rows-[minmax(0,1fr)]">
        <div className="h-[640px] min-h-0 min-w-0 min-[1000px]:h-auto">
          {active ? (
            <QuestionPanel
              q={active}
              runId={runId}
              review={review}
              evidence={evidenceItems}
              activeEvidence={evIndex}
              notesRef={notesRef}
              canNext={activeIndex >= 0 && activeIndex < filtered.length - 1}
              onEdit={() => undefined}
              onVerify={() => setVerified(active.id, !active.verified)}
              onDecision={setDecision}
              onCheck={(field, value) =>
                updateReview(active.id, { [field]: value })
              }
              onHardCase={(value) =>
                updateReview(active.id, { hard_case: value }, true)
              }
              onNotes={(value) => updateReview(active.id, { notes: value })}
              onSelectEvidence={(index, item) => {
                setEvState({ qid: active.id, index })
                setSyncedKey(`${active.id}:${index}`)
                showEvidence(item)
              }}
              onSaveNext={() => move(1)}
            />
          ) : (
            <p className="rounded-lg border border-dashed border-(--line) p-4 text-sm text-muted-foreground">
              No questions match your current filters. Clear the filters or add
              a new question.
            </p>
          )}
        </div>

        <div className="h-[560px] min-h-0 min-w-0 min-[1000px]:h-auto">
          <PdfPane
            registry={registry}
            view={pdfView}
            evidence={evidenceView}
            onView={setPdfView}
            paneRef={paneRef}
          />
        </div>
      </div>
    </div>
  )
}
